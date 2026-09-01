"""PDF 매뉴얼의 이전/현재 리비전을 페이지 텍스트 단위로 비교한다."""

from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path

import fitz

from app.modules.manual_review.docx_track_changes import TrackChangesResult, TrackedChange


def _page_lines(path: Path) -> list[list[str]]:
    try:
        with fitz.open(path) as document:
            return [[line.strip() for line in page.get_text("text").splitlines() if line.strip()] for page in document]
    except Exception as exc:
        raise ValueError(f"PDF 매뉴얼을 읽을 수 없습니다: {path.name}") from exc


def extract_pdf_revision_diff(previous_path: Path, current_path: Path) -> TrackChangesResult:
    previous_pages = _page_lines(previous_path)
    current_pages = _page_lines(current_path)
    result = TrackChangesResult(plain_text="\n".join(line for page in current_pages for line in page))
    for page_index in range(max(len(previous_pages), len(current_pages))):
        before = previous_pages[page_index] if page_index < len(previous_pages) else []
        after = current_pages[page_index] if page_index < len(current_pages) else []
        for operation, before_start, before_end, after_start, after_end in SequenceMatcher(None, before, after, autojunk=False).get_opcodes():
            if operation == "equal":
                continue
            old_text = " ".join(before[before_start:before_end]).strip()
            new_text = " ".join(after[after_start:after_end]).strip()
            if operation == "insert":
                kind, text = "pdf_addition", new_text
            elif operation == "delete":
                kind, text = "pdf_deletion", old_text
            else:
                kind, text = "pdf_modification", f"이전: {old_text}\n현재: {new_text}"
            if text:
                result.changes.append(
                    TrackedChange(
                        kind=kind, author="", date="", text=text,
                        paragraph_index=page_index, source_page=page_index + 1,
                        review_required=True,
                    )
                )
    return result
