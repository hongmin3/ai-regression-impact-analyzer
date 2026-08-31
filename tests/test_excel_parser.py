from openpyxl import Workbook

from app.parsers.excel_parser import detect_columns, parse_testcases


def test_detect_localized_columns():
    columns = detect_columns(["TC 번호", "기능명", "사전 조건", "시험 절차", "기대 결과"])
    assert columns["tc_id"] == 0
    assert columns["expected_result"] == 4


def test_parse_and_deduplicate(tmp_path):
    path = tmp_path / "tc.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["TC ID", "Feature", "Step", "Expected Result"])
    ws.append(["TC-1", "설정", "저장", "유지"])
    ws.append(["TC-1", "설정", "반복", "유지"])
    wb.save(path)
    cases = parse_testcases(path)
    assert len(cases) == 1
    assert cases[0].tc_id == "TC-1"
