from pathlib import Path

import fitz

from app.modules.impact_analyzer.schemas import RevisionMark, SpecificationChunk


def detect_revision_marks(page: fitz.Page) -> list[RevisionMark]:
    """텍스트 span을 가로지르는 수평 vector line을 보수적으로 취소선/밑줄로 판독한다.

    PDF에는 표준 취소선 플래그가 없으므로 선이 span 폭의 절반 이상 겹칠 때만 인정한다.
    이미지 기반 PDF와 애매한 drawing은 빈 목록으로 남겨 원본 확인 원칙을 유지한다.
    """
    drawings = page.get_cdrawings() if hasattr(page, "get_cdrawings") else page.get_drawings()
    horizontal_items = []
    def xy(point) -> tuple[float, float]:
        return (float(point.x), float(point.y)) if hasattr(point, "x") else (float(point[0]), float(point[1]))
    for drawing in drawings:
        for item in drawing.get("items", []):
            if item and item[0] == "l":
                p1, p2 = xy(item[1]), xy(item[2])
                if abs(p1[1] - p2[1]) <= 1.5:
                    horizontal_items.append((p1, p2))
    if not horizontal_items:
        return []
    # rawdict span 전체보다 words bbox가 훨씬 가볍고, 선과 글자의 위치 대조에는 충분하다.
    spans = [{"bbox": word[:4]} for word in page.get_text("words") if len(word) >= 5 and str(word[4]).strip()]
    marks: set[RevisionMark] = set()
    for p1, p2 in horizontal_items:
        x0, x1, y = min(p1[0], p2[0]), max(p1[0], p2[0]), (p1[1] + p2[1]) / 2
        for span in spans:
            sx0, sy0, sx1, sy1 = span["bbox"]
            overlap = max(0.0, min(x1, sx1) - max(x0, sx0))
            if overlap < max((sx1 - sx0) * 0.5, 4.0):
                continue
            if abs(y - ((sy0 + sy1) / 2)) <= max((sy1 - sy0) * 0.2, 2.0):
                marks.add(RevisionMark.STRIKETHROUGH_DETECTED)
            elif abs(y - sy1) <= max((sy1 - sy0) * 0.2, 2.0):
                marks.add(RevisionMark.UNDERLINE_DETECTED)
    return sorted(marks, key=lambda value: value.value)


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
                revision_marks = detect_revision_marks(page)
                for offset in range(0, len(text), chunk_chars):
                    part = text[offset:offset + chunk_chars].strip()
                    chunks.append(SpecificationChunk(chunk_id=f"{document_id}-p{page_number}-{offset // chunk_chars}", document_id=document_id, page=page_number, heading=heading, text=part, revision_marks=revision_marks))
    except Exception as exc:
        raise ValueError(f"사양서 PDF를 읽을 수 없습니다: {path.name}") from exc
    return chunks
