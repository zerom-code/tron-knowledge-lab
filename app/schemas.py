from typing import Literal
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArticleInput(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(max_length=12000)
    url: HttpUrl
    language: Literal["EN", "RU", "UK", "TR", "ES"] = "EN"
    topic: str = Field(default="Resource model", min_length=1, max_length=120)

    @field_validator("title", "topic")
    @classmethod
    def trim(cls, value):
        if not value.strip():
            raise ValueError("Поле не должно быть пустым.")
        return value.strip()

    @field_validator("url")
    @classmethod
    def https_source(cls, value):
        if value.scheme != "https" or value.username or value.password:
            raise ValueError("Используйте HTTPS URL без пароля.")
        return value


class LiveInput(StrictModel):
    live: bool


class Filters(StrictModel):
    language: Literal["", "EN", "RU", "UK", "TR", "ES"] = ""
    source: str = Field(default="", max_length=200)
    topic: str = Field(default="", max_length=120)
    entity: str = Field(default="", max_length=100)
    document: str = Field(default="", max_length=100)
    date: str = ""
    verification: Literal["", "Verified", "Unverified", "Outdated"] = ""

    @field_validator("date")
    @classmethod
    def valid_date(cls, value):
        if value:
            date.fromisoformat(value)
        return value


class SearchInput(StrictModel):
    query: str = Field(min_length=1, max_length=1000)
    project_id: Literal["tpe"] = "tpe"
    filters: Filters = Field(default_factory=Filters)
    mode: Literal["saved", "live"] = "saved"

    @field_validator("query")
    @classmethod
    def trimmed_query(cls, value):
        if not value.strip():
            raise ValueError("Введите вопрос.")
        return value.strip()


class ContextInput(StrictModel):
    run_id: str = Field(min_length=1, max_length=80)
    selected_ids: list[str] = Field(max_length=6)


class VerificationInput(StrictModel):
    note: str = Field(min_length=15, max_length=1000)
    checked_against_source: Literal[True]
