"""이전 Round QA Comment와 현재 Track Changes를 로컬에서 보수적으로 대조한다.

결과는 QA 참고용 suggestion일 뿐 Comment 상태를 자동 변경하지 않는다. 짧은 한국어 문장도
비교할 수 있도록 정규화 문자열의 문자 3-gram Jaccard와 SequenceMatcher를 함께 사용한다.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher


LABELS = {
    "REFLECTED_SUSPECTED": "반영 의심",
    "NOT_REFLECTED_SUSPECTED": "미반영 의심",
    "UNABLE_TO_DETERMINE": "판단 불가",
}


def _normalize(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", (text or "").lower())


def _ngrams(text: str, size: int = 3) -> set[str]:
    normalized = _normalize(text)
    if not normalized:
        return set()
    if len(normalized) <= size:
        return {normalized}
    return {normalized[index:index + size] for index in range(len(normalized) - size + 1)}


def text_similarity(left: str, right: str) -> float:
    a, b = _normalize(left), _normalize(right)
    if not a or not b:
        return 0.0
    left_grams, right_grams = _ngrams(a), _ngrams(b)
    union = left_grams | right_grams
    jaccard = len(left_grams & right_grams) / len(union) if union else 0.0
    sequence = SequenceMatcher(None, a, b).ratio()
    return round(max(jaccard, sequence), 4)


def suggest_comment_resolution(comment: dict, current_changes: list[dict]) -> dict:
    functional = [change for change in current_changes if change.get("functional") and change.get("text")]
    if not functional:
        return _result("UNABLE_TO_DETERMINE", 0.0, None)

    query_parts = [comment.get("change_text", ""), comment.get("comment_text", "")]
    ranked = []
    for change in functional:
        score = max(text_similarity(query, change["text"]) for query in query_parts if query)
        ranked.append((score, change))
    score, candidate = max(ranked, key=lambda item: item[0])

    if score >= 0.55 and candidate.get("kind") in {"insertion", "move_to"}:
        status = "REFLECTED_SUSPECTED"
    elif score < 0.2:
        status = "NOT_REFLECTED_SUSPECTED"
    else:
        status = "UNABLE_TO_DETERMINE"
    return _result(status, score, candidate)


def suggest_prior_comments(comments: list[dict], current_changes: list[dict]) -> list[dict]:
    return [{**comment, "resolution_suggestion": suggest_comment_resolution(comment, current_changes)} for comment in comments]


def _result(status: str, score: float, candidate: dict | None) -> dict:
    return {
        "status": status,
        "label": LABELS[status],
        "confidence": score,
        "candidate_change_id": candidate.get("id") if candidate else None,
        "candidate_text": candidate.get("text", "") if candidate else "",
    }
