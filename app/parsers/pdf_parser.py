from pathlib import Path

import fitz

from app.modules.impact_analyzer.schemas import SpecificationChunk


def extract_pdf_text(path: Path) -> str:
    try:
        with fitz.open(path) as document:
            return "\n".join(page.get_text("text") for page in document)
    except Exception as exc:
        raise ValueError(f"PDF를 읽을 수 없습니다: {path.name}") from exc


def parse_specification(path: Path, document_id: str, chunk_chars: int = 1800) -> list[SpecificationChunk]:
    chunks: list[SpecificationChunk] = []
    try:
        with fitz.open(path) as document:
            for page_number, page in enumerate(document, start=1):
                text = page.get_text("text").strip()
                if not text:
                    continue
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                heading = lines[0][:160] if lines else f"Page {page_number}"
                for offset in range(0, len(text), chunk_chars):
                    part = text[offset:offset + chunk_chars].strip()
                    chunks.append(SpecificationChunk(chunk_id=f"{document_id}-p{page_number}-{offset // chunk_chars}", document_id=document_id, page=page_number, heading=heading, text=part))
    except Exception as exc:
        raise ValueError(f"사양서 PDF를 읽을 수 없습니다: {path.name}") from exc
    return chunks
