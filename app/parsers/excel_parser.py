from __future__ import annotations

import re
from pathlib import Path

from openpyxl import load_workbook

from app.core.schemas import TestCase

ALIASES = {
    "tc_id": ["tcid", "testcaseid", "testid", "oldid", "id", "tcno", "테스트케이스id", "tc번호"],
    "category": ["category", "stccategory", "분류", "구분"],
    "feature": ["feature", "function", "title", "testitem", "기능", "기능명", "requirement"],
    "precondition": ["precondition", "pre-condition", "pre_condition", "사전조건", "전제조건"],
    "step": ["step", "steps", "teststep", "stepdescription", "절차", "시험절차"],
    "expected_result": ["expectedresult", "expectedtestresult", "expectedreuslt", "expected", "기대결과", "예상결과"],
    "result": ["result", "testresult", "finalresult", "최종result", "결과"],
    "remark": ["remark", "remarks", "comment", "comments", "description", "비고", "note"],
}


def _normalize(value: object) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", str(value or "").lower())


def detect_columns(headers: list[object], mapping: dict[str, str] | None = None) -> dict[str, int]:
    normalized = {_normalize(value): index for index, value in enumerate(headers)}
    result: dict[str, int] = {}
    for field, aliases in ALIASES.items():
        configured = (mapping or {}).get(field)
        candidates = ([configured] if configured else []) + aliases
        for candidate in candidates:
            key = _normalize(candidate)
            if key in normalized:
                result[field] = normalized[key]
                break
    if "tc_id" not in result:
        raise ValueError("TC ID 컬럼을 찾을 수 없습니다. 컬럼 매핑을 확인하세요.")
    return result


def parse_testcases(path: Path, mapping: dict[str, str] | None = None) -> list[TestCase]:
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
        cases: list[TestCase] = []
        seen: set[str] = set()
        detected_sheet = False
        for sheet in workbook.worksheets:
            header_row = None
            columns = None
            for row_number, row in enumerate(sheet.iter_rows(min_row=1, max_row=min(sheet.max_row, 80), values_only=True), start=1):
                try:
                    candidate = detect_columns(list(row), mapping)
                except ValueError:
                    continue
                if len(candidate) >= 2:
                    header_row = row_number
                    columns = candidate
                    break
            if header_row is None or columns is None:
                continue
            detected_sheet = True
            for row in sheet.iter_rows(min_row=header_row + 1, values_only=True):
                values = {
                    field: str(row[index] or "").strip()
                    for field, index in columns.items()
                    if index < len(row)
                }
                tc_id = values.get("tc_id", "")
                if not tc_id or tc_id in seen:
                    continue
                seen.add(tc_id)
                cases.append(TestCase(**values))
        if not detected_sheet:
            raise ValueError("TC ID 컬럼을 찾을 수 없습니다. 컬럼 매핑을 확인하세요.")
        return cases
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Excel을 읽을 수 없습니다: {path.name}") from exc
