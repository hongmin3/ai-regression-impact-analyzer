from __future__ import annotations

import re

from app.core.schemas import ChangeAnalysis

RISK_WORDS = ("저장", "설정", "호환", "마이그레이션", "DICOM", "인터페이스", "삭제", "변환", "workflow", "database", "UI")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _new_or_changed_lines(text: str, baseline_text: str) -> list[str]:
    """기준 사양서 텍스트에 없는(신규 또는 변경된) 줄만 남긴다.

    줄 단위 exact match 대신 공백을 제거한 값이 기준본 전체에 부분 문자열로
    존재하는지 확인한다. PDF/Word 추출 시 줄바꿈 위치가 리비전마다 달라질 수
    있어, 순서를 고려하는 diff보다 이 방식이 오탐을 줄인다.
    """
    baseline_blob = _normalize(baseline_text)
    result = []
    for raw_line in text.splitlines():
        line = raw_line.strip(" -\t")
        if len(line) <= 2:
            continue
        key = _normalize(line)
        if key and key in baseline_blob:
            continue
        result.append(line)
    return result


def analyze_change_rules(text: str, baseline_text: str | None = None, user_notes: str = "") -> ChangeAnalysis:
    if not text:
        lines = []
    elif baseline_text:
        lines = _new_or_changed_lines(text, baseline_text)
    else:
        lines = [line.strip(" -\t") for line in text.splitlines() if len(line.strip()) > 2]
    note_lines = [line.strip(" -\t") for line in user_notes.splitlines() if len(line.strip()) > 2]
    combined_lines = note_lines + lines
    keyword_source = "\n".join(combined_lines) if (baseline_text or note_lines) else text
    keywords = [word for word in RISK_WORDS if word.lower() in keyword_source.lower()]
    # 사용자가 직접 입력한 요청은 이미 변경사항으로 명시된 것이므로 키워드 필터 없이 그대로 포함한다.
    features = list(note_lines)
    for line in lines:
        if re.search(r"변경|추가|개선|수정|지원", line, re.I):
            features.append(line[:200])
    return ChangeAnalysis(
        user_notes=user_notes,
        changed_features=features[:20], purpose="; ".join(features[:3]),
        ui_changes=[line for line in combined_lines if re.search(r"UI|화면|버튼|표시", line, re.I)][:10],
        interface_changes=[line for line in combined_lines if re.search(r"API|interface|연동", line, re.I)][:10],
        dicom_changes=[line for line in combined_lines if "dicom" in line.lower()][:10],
        workflow_changes=[line for line in combined_lines if re.search(r"workflow|흐름|절차", line, re.I)][:10],
        configuration_changes=[line for line in combined_lines if re.search(r"설정|config", line, re.I)][:10],
        stored_data_changes=[line for line in combined_lines if re.search(r"저장|database|DB", line, re.I)][:10],
        compatibility_changes=[line for line in combined_lines if re.search(r"호환|compatib", line, re.I)][:10],
        risk_keywords=keywords,
    )
