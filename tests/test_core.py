import json
from pathlib import Path
from app.agent import valid_answer
from app.errors import AppError
from app.ingestion import parse_article
from app.rag import fuse, query_info
from app.schemas import SearchInput
import pytest
from pydantic import ValidationError


def test_future_and_exact_fee_are_separate_from_general_mechanism():
    assert query_info("What exact fee will I pay tomorrow for a USDT TRC-20 transfer?")["future"]
    assert query_info("How much TRX is a USDT TRC-20 transfer?")["exactAmount"]
    info = query_info("How can I reduce USDT TRC-20 transaction fees?")
    assert info["supported"] and not info["exactAmount"] and not info["future"]
    assert not query_info("Where can I buy USDT?")["supported"]


def test_rrf_fuses_ranks_and_deduplicates_overlapping_paths():
    items = dict(fuse([("a", .9), ("b", .8)], [("b", .7), ("c", .6)]))
    assert len(items) == 3
    assert items["b"]["rrf"] == pytest.approx(1 / 62 + 1 / 61)
    assert items["c"]["vectorRank"] is None


def test_parser_preserves_words_sections_and_rejects_empty_html():
    parts = parse_article("# Energy\n\n<p>TRON Energy supports contract execution.</p>")
    assert any("TRON Energy" in text for _, text in parts)
    long = "Energy resources " * 200
    parts = parse_article(long)
    assert all(len(text) <= 1000 for _, text in parts)
    with pytest.raises(AppError, match="нет текста"):
        parse_article("<script>ignored()</script>")


def test_parser_bounds_new_document_work():
    with pytest.raises(AppError) as error:
        parse_article("\n\n".join(["Energy " * 140] * 13))
    assert error.value.code == "CHUNK_LIMIT"


def test_schema_rejects_cross_project_unknown_filters_and_bad_date():
    with pytest.raises(ValidationError):
        SearchInput(query="TRON Energy", project_id="foreign")
    with pytest.raises(ValidationError):
        SearchInput(query="TRON Energy", filters={"date": "tomorrow"})
    with pytest.raises(ValidationError):
        SearchInput(query="TRON Energy", filters={"unsafe_sql": "1=1"})


def test_answer_citations_must_target_its_selected_evidence():
    context = {"chunks": [{"id": "c1"}]}
    answer = {"answerable": True, "paragraphs": [{"text": "Supported", "chunk_ids": ["c1"]}], "limitations": []}
    assert valid_answer(answer, context)
    answer["paragraphs"][0]["chunk_ids"] = ["not-in-context"]
    assert not valid_answer(answer, context)


def test_seed_quotes_keep_real_urls_and_vector_dimensions():
    corpus = json.loads((Path(__file__).parent.parent / "data/corpus.json").read_text())
    assert len(corpus["documents"]) == 4
    assert all(s["url"].startswith("https://") and len(s["snapshotHash"]) == 64 for s in corpus["sources"])
    assert all(len(c["embedding"]) == 256 for c in corpus["chunks"])
