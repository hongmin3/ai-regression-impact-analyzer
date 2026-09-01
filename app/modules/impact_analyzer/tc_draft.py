from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.modules.impact_analyzer.schemas import AnalysisResult

CONFIRM_NEEDED = "확인 필요"


def _cell(value: str) -> str:
    text = (value or CONFIRM_NEEDED).strip() or CONFIRM_NEEDED
    return text.replace("|", "\\|").replace("\n", " ")


def create_tc_draft_markdown(result: AnalysisResult) -> Path | None:
    """VXvue TC 설계 가이드 Rev.1.7 §13.1 양식으로 신규 TC 초안을 만든다.

    근거 없는 필드는 Gemini가 이미 '확인 필요'로 채워서 반환하며, 여기서도 빈 값이면
    같은 문자열로 보정한다 (임의 생성 금지).
    """
    if not result.draft_test_cases:
        return None
    output = get_settings().path("storage.generated_tc_dir") / f"regression-{result.analysis_id}-draft.md"
    lines = [
        f"# 신규 TC 초안 — 분석 {result.analysis_id}",
        "",
        "상태: 초안 (실제 검증 이력 없음, QA 검토 및 보완 필요)",
        f"변경문서: {result.change_file} · 근거 사양서: {result.specification_file}",
        "",
        "| SRS No | 변경사항 | 변경사항 상세 | Title | Precondition | Test Step | Expected Result | Test Data | 근거 Chunk |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for draft in result.draft_test_cases:
        evidence = ", ".join(draft.evidence_chunk_ids) or CONFIRM_NEEDED
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(draft.srs_no),
                    _cell(draft.changed_feature[:60]),
                    _cell(draft.changed_feature),
                    _cell(draft.title),
                    _cell(draft.precondition),
                    _cell(draft.test_step),
                    _cell(draft.expected_result),
                    _cell(draft.test_data),
                    evidence,
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("근거가 없는 필드는 \"확인 필요\"로 표시됩니다. QA 검토 후 실제 TC Excel에 반영하세요 (VXvue TC 설계 가이드 Rev.1.7 참고).")
    output.write_text("\n".join(lines), encoding="utf-8")
    return output
