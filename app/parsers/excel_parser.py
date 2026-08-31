from __future__ import annotations

import re
from pathlib import Path

from openpyxl import load_workbook

from app.core.schemas import TestCase

ALIASES = {
    "tc_id": ["tcid", "testcaseid", "testid", "id", "tcno", "테스트케이스id", "tc번호"],
    "category": ["category", "분류", "구분"], "feature": ["feature", "기능", "기능명", "requirement"],
    "precondition": ["precondition", "사전조건", "전제조건"], "step": ["step", "steps", "teststep", "절차", "시험절차"],
    "expected_result": ["expectedresult", "expected", "기대결과", "예상결과"], "result": ["result", "결과"],
    "remark": ["remark", "remarks", "비고", "note"],
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
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=True)
        headers = list(next(rows))
        columns = detect_columns(headers, mapping)
        cases: list[TestCase] = []
        seen: set[str] = set()
        for row in rows:
            values = {field: str(row[index] or "").strip() for field, index in columns.items()}
            tc_id = values.get("tc_id", "")
            if not tc_id or tc_id in seen:
                continue
            seen.add(tc_id)
            cases.append(TestCase(**values))
        return cases
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Excel을 읽을 수 없습니다: {path.name}") from exc
