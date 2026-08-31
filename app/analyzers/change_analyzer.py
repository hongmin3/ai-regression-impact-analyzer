from __future__ import annotations

import re

from app.core.schemas import ChangeAnalysis

RISK_WORDS = ("저장", "설정", "호환", "마이그레이션", "DICOM", "인터페이스", "삭제", "변환", "workflow", "database", "UI")


def analyze_change_rules(text: str) -> ChangeAnalysis:
    lines = [line.strip(" -\t") for line in text.splitlines() if len(line.strip()) > 2]
    keywords = [word for word in RISK_WORDS if word.lower() in text.lower()]
    features = []
    for line in lines:
        if re.search(r"변경|추가|개선|수정|지원", line, re.I):
            features.append(line[:200])
    return ChangeAnalysis(
        changed_features=features[:20], purpose="; ".join(features[:3]),
        ui_changes=[line for line in lines if re.search(r"UI|화면|버튼|표시", line, re.I)][:10],
        interface_changes=[line for line in lines if re.search(r"API|interface|연동", line, re.I)][:10],
        dicom_changes=[line for line in lines if "dicom" in line.lower()][:10],
        workflow_changes=[line for line in lines if re.search(r"workflow|흐름|절차", line, re.I)][:10],
        configuration_changes=[line for line in lines if re.search(r"설정|config", line, re.I)][:10],
        stored_data_changes=[line for line in lines if re.search(r"저장|database|DB", line, re.I)][:10],
        compatibility_changes=[line for line in lines if re.search(r"호환|compatib", line, re.I)][:10],
        risk_keywords=keywords,
    )
