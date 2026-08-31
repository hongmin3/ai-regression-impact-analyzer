from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree

from app.core.schemas import SpecificationChunk
from app.parsers.pdf_parser import extract_pdf_text, parse_specification

WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_docx_text(path: Path) -> str:
    """Extract paragraphs and table cell text from a DOCX in document order."""
    try:
        with zipfile.ZipFile(path) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
        lines: list[str] = []
        for paragraph in root.iter(f"{WORD_NS}p"):
            text = "".join(node.text or "" for node in paragraph.iter(f"{WORD_NS}t")).strip()
            if text:
                lines.append(text)
        return "\n".join(lines)
    except Exception as exc:
        raise ValueError(f"Word 문서를 읽을 수 없습니다: {path.name}") from exc


def extract_document_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(path)
    if suffix == ".docx":
        return extract_docx_text(path)
    raise ValueError(f"지원하지 않는 문서 형식입니다: {suffix}")


def parse_document(path: Path, document_id: str, chunk_chars: int = 1800) -> list[SpecificationChunk]:
    if path.suffix.lower() == ".pdf":
        return parse_specification(path, document_id, chunk_chars)
    text = extract_document_text(path).strip()
    if not text:
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    heading = lines[0][:160] if lines else path.stem
    return [
        SpecificationChunk(
            chunk_id=f"{document_id}-p1-{offset // chunk_chars}",
            document_id=document_id,
            page=1,
            heading=heading,
            text=text[offset : offset + chunk_chars].strip(),
        )
        for offset in range(0, len(text), chunk_chars)
    ]
