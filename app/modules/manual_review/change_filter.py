"""단순 변경(공백, 페이지 번호, 목차 자동 갱신, Revision 번호, Copyright 연도, 문단 스타일 등)을
NON_FUNCTIONAL_CHANGE로 분류해 기본 AI 분석 대상에서 제외한다 (스펙 §8).

사용자가 "전체 변경 보기"를 선택하면 UI에는 계속 표시할 수 있도록, 이 필터는 변경을
삭제하지 않고 TrackedChange마다 True/False만 반환한다 — 실제 저장은 호출자가 결정한다.
"""

from __future__ import annotations

import re

from app.modules.manual_review.docx_track_changes import TrackedChange

_PAGE_NUMBER_RE = re.compile(r"^\s*-?\s*\d{1,4}\s*-?\s*$")
_COPYRIGHT_RE = re.compile(r"copyright|©|all rights reserved", re.IGNORECASE)
_REVISION_LABEL_RE = re.compile(r"^\s*rev(ision)?\.?\s*[:\-]?\s*[\d.]+\s*$", re.IGNORECASE)
_TOC_LEADER_RE = re.compile(r"\.{4,}")  # 목차 점선 리더 (예: "4.2 License ......... 12")


def is_functional_change(change: TrackedChange) -> bool:
    """True면 의미 있는(기능적) 변경 — AI 분석 대상. False면 NON_FUNCTIONAL_CHANGE."""
    text = change.text.strip()
    if not text:
        return False
    if _PAGE_NUMBER_RE.match(text):
        return False
    if _COPYRIGHT_RE.search(text):
        return False
    if _REVISION_LABEL_RE.match(text):
        return False
    if _TOC_LEADER_RE.search(text):
        return False
    return True
