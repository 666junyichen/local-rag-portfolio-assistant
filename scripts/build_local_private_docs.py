from __future__ import annotations

import csv
import html
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]

SOURCE_ROOTS = [
    {
        "name": "project_activity_root",
        "path": "C:\\\u7b80\u5386\u6295\u9012\\Company-resume\\\u6700\u8fd1\u7684project \u548c\u6d3b\u52a8\u6765\u4e00\u76f4\u66f4\u65b0",
        "description": "Local project and activity materials",
    },
    {
        "name": "resume_root",
        "path": "C:\\\u7b80\u5386\u6295\u9012\\Company-resume\\resumes",
        "description": "Local resume drafts and master resumes",
    },
    {
        "name": "ranking_jobs_skill",
        "path": r"C:\Users\20430\.agents\skills\ranking-jobs-from-resume",
        "description": "Local ranking-jobs-from-resume skill notes and evidence inventory",
    },
]

TEXT_EXTENSIONS = {".csv", ".html", ".htm", ".js", ".json", ".md", ".py", ".txt", ".ts", ".tsx"}
DOCX_EXTENSIONS = {".docx"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

SKIP_DIRS = {
    ".git",
    ".next",
    ".venv",
    ".vercel",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}
SKIP_FILE_NAMES = {
    ".env",
    "local_private_docs.json",
    "local_private_docs.summary.json",
    "package-lock.json",
    "uv.lock",
}

MAX_FILE_BYTES = 900_000
MAX_BODY_CHARS = 12_000


def clean_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"<script[\s\S]*?</script>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<style[\s\S]*?</style>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def read_text_file(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def read_docx(path: Path) -> str:
    namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    with zipfile.ZipFile(path) as archive:
        xml_bytes = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml_bytes)
    for paragraph in root.findall(".//w:p", namespaces):
        pieces = [node.text or "" for node in paragraph.findall(".//w:t", namespaces)]
        text = "".join(pieces).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def should_skip(path: Path) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    if path.name in SKIP_FILE_NAMES or path.name.startswith(".env"):
        return True
    try:
        limit = 20_000_000 if path.suffix.lower() in IMAGE_EXTENSIONS | PDF_EXTENSIONS else MAX_FILE_BYTES
        return path.stat().st_size > limit
    except OSError:
        return True


def iter_source_files(source_root: Path) -> list[Path]:
    if not source_root.exists():
        return []

    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(source_root):
        dirnames[:] = [dirname for dirname in dirnames if dirname not in SKIP_DIRS]
        current_dir = Path(dirpath)
        for filename in filenames:
            path = current_dir / filename
            if should_skip(path):
                continue
            suffix = path.suffix.lower()
            if suffix in TEXT_EXTENSIONS or suffix in DOCX_EXTENSIONS or suffix in PDF_EXTENSIONS or suffix in IMAGE_EXTENSIONS:
                files.append(path)
    return sorted(files)


def read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    return "\n\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)


def build_doc(path: Path, source_name: str, source_description: str, base: Path) -> dict[str, str | int] | None:
    suffix = path.suffix.lower()
    parse_status = "ready"
    parse_message = ""
    try:
        if suffix in IMAGE_EXTENSIONS:
            text = f"Image file {path.name}. OCR not enabled."
            parse_status = "needs_ocr"
            parse_message = "OCR not enabled"
        elif suffix in PDF_EXTENSIONS:
            text = read_pdf(path)
            if len(clean_text(text)) < 80:
                text = f"Scanned PDF {path.name}. OCR not enabled."
                parse_status = "needs_ocr"
                parse_message = "PDF contains no extractable text"
        else:
            text = read_docx(path) if suffix in DOCX_EXTENSIONS else read_text_file(path)
    except Exception as error:
        text = f"Could not parse {path.name}: {type(error).__name__}."
        parse_status = "parse_error"
        parse_message = str(error)[:500]

    body = clean_text(text)
    if len(body) < 80 and parse_status == "ready":
        return None

    try:
        relative_path = str(path.relative_to(base))
    except ValueError:
        relative_path = str(path)

    stat = path.stat()
    return {
        "title": f"{source_description}: {path.stem}",
        "category": "local_private_source",
        "source": source_name,
        "path": str(path),
        "relative_path": relative_path,
        "body": body[:MAX_BODY_CHARS],
        "file_type": suffix.lstrip("."),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "parse_status": parse_status,
        "parse_message": parse_message,
    }


def main() -> None:
    docs: list[dict[str, str]] = []
    summary_rows: list[dict[str, str | int]] = []

    for source in SOURCE_ROOTS:
        base = Path(source["path"])
        files = iter_source_files(base)
        kept = 0
        for path in files:
            doc = build_doc(path, source["name"], source["description"], base)
            if doc:
                docs.append(doc)
                kept += 1
        summary_rows.append(
            {
                "source": source["name"],
                "path": str(base),
                "candidate_files": len(files),
                "included_docs": kept,
            }
        )

    output_path = ROOT / "data" / "local_private_docs.json"
    summary_path = ROOT / "data" / "local_private_docs.summary.json"
    output_path.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(summary_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    sys.path.insert(0, str(ROOT))
    from src.local_catalog import LocalCatalog

    catalog = LocalCatalog(ROOT / "data" / "local_catalog.sqlite3")
    catalog.upsert_documents(docs)

    print(f"Wrote private docs: {len(docs)}")
    print(f"Output: {output_path}")
    print(f"Summary: {summary_path}")
    print(f"SQLite catalog: {catalog.path} ({catalog.count()} records)")
    writer = csv.DictWriter(sys.stdout, fieldnames=["source", "candidate_files", "included_docs", "path"])
    writer.writeheader()
    writer.writerows(summary_rows)


if __name__ == "__main__":
    main()
