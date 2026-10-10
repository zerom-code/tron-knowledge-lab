import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "artifacts/release"
ROOT_FILES = ["README.md", "QA.md", "requirements.txt", "compose.yaml", "Dockerfile",
              "pytest.ini", "alembic.ini", ".env.example", ".gitignore", ".dockerignore"]
DIRECTORIES = ["app", "alembic", "data", "static", "tests", "scripts", "docs", "verification"]
PERSONAL_GUIDE = "private/MY_TEST_AND_RECORDING.ru.md"
PREFIX = "TRON-Knowledge-Lab-Python/"
PATTERN = re.compile(rb"sk-(?:proj-)?[A-Za-z0-9_-]{25,}|gh[pousr]_[A-Za-z0-9]{30,}")


def release_files():
    files = [ROOT / name for name in ROOT_FILES]
    for directory in DIRECTORIES:
        files.extend((ROOT / directory).rglob("*"))
    result = sorted({p for p in files if p.is_file() and not p.is_symlink()
                     and "__pycache__" not in p.parts and p.suffix != ".pyc"})
    missing = [name for name in ROOT_FILES if ROOT / name not in result]
    if missing:
        raise SystemExit("Missing required files: " + ", ".join(missing))
    if not (ROOT / "verification/browser-report.json").exists():
        raise SystemExit("Missing public verification reports.")
    return result


def package(name, files):
    manifest = []
    with zipfile.ZipFile(OUTPUT / name, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            relative = path.relative_to(ROOT).as_posix()
            content = path.read_bytes()
            if PATTERN.search(content):
                raise SystemExit("Credential-like value in " + relative)
            info = zipfile.ZipInfo(PREFIX + relative)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
            manifest.append({"path": relative, "bytes": len(content),
                             "sha256": hashlib.sha256(content).hexdigest()})
        archive.writestr(PREFIX + "MANIFEST.json", json.dumps(manifest, indent=2))
    with zipfile.ZipFile(OUTPUT / name) as archive:
        assert archive.testzip() is None
    checksum = hashlib.sha256((OUTPUT / name).read_bytes()).hexdigest()
    print(name, len(manifest) + 1, "files")
    return checksum + "  " + name + "\n"


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    files = release_files()
    checksums = package("TRON-Knowledge-Lab-Python-GitHub.zip", files)
    personal = ROOT / PERSONAL_GUIDE
    if personal.is_file():
        checksums += package("TRON-Knowledge-Lab-Python-complete.zip", files + [personal])
    (OUTPUT / "SHA256SUMS.txt").write_text(checksums, encoding="utf-8")
