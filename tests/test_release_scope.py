"""release_scope.py 테스트. 아래 fixture들은 실제 VXvue 1.1.0 Release Note/설계검토보고서로
파서를 검증하며 관찰한 실제 구조 패턴(문서 앞머리 메타데이터, TOC 점선 리더, 카테고리 헤더의
괄호 부연 설명, 페이지 header/footer 잡음, N.N.N 번호 매김 재사용)을 반영해 만든 합성
예시이며, 실제 회사 문서 내용을 그대로 담지 않는다."""

from app.modules.manual_review.release_scope import extract_design_review_changes, extract_release_note_changes, match_release_changes


def test_release_note_classifies_lines_under_category_headers():
    text = "\n".join(["Added", "DICOM TLS 지원", "IC 카드 로그인", "Changed", "Generator 자동 연결/초기화 개선", "Fixed bug", "로그인 실패 시 재시도 오류 수정"])

    changes = extract_release_note_changes(text, "release_note.docx")

    assert [(c.category, c.title) for c in changes] == [
        ("Added", "DICOM TLS 지원"),
        ("Added", "IC 카드 로그인"),
        ("Changed", "Generator 자동 연결/초기화 개선"),
        ("Fixed bug", "로그인 실패 시 재시도 오류 수정"),
    ]
    assert all(c.source_document == "release_note.docx" for c in changes)


def test_release_note_korean_category_headers_recognized():
    text = "\n".join(["추가", "IC 카드 로그인", "기타", "문서 오탈자 수정"])

    changes = extract_release_note_changes(text, "release_note.docx")

    assert [(c.category, c.title) for c in changes] == [("Added", "IC 카드 로그인"), ("Etc", "문서 오탈자 수정")]


def test_release_note_etc_header_with_parenthetical_suffix_recognized():
    """실제 문서에서 "Etc (내부 배포용 – 대외비, 재설계, 연동 등)"처럼 괄호 부연 설명이 붙어 있었다."""
    text = "\n".join(["Etc (내부 배포용 – 대외비, 재설계, 연동 등)", "1 사내 전용 모듈 연동"])

    changes = extract_release_note_changes(text, "release_note.docx")

    assert len(changes) == 1
    assert changes[0].category == "Etc"
    assert changes[0].title == "사내 전용 모듈 연동"


def test_release_note_strips_leading_item_numbers():
    text = "\n".join(["Fixed bug", "1 첫번째 수정", "2 두번째 수정"])

    changes = extract_release_note_changes(text, "release_note.docx")

    assert [c.title for c in changes] == ["첫번째 수정", "두번째 수정"]


def test_release_note_skips_front_matter_before_first_category_header():
    """실제 문서는 담당자/버전 호환성 표 같은 메타데이터가 먼저 나온다 — 첫 헤더 전 줄은 버려야 한다."""
    text = "\n".join(
        [
            "VXvue Revision History",
            "Purpose",
            "Software and Firmware Compatible Version",
            "VXvue",
            "1.1.0",
            "Revision History",
            "Version",
            "Release Date",
            "1.1.0",
            "2026-05-22",
            "Added",
            "실제 신규 기능",
        ]
    )

    changes = extract_release_note_changes(text, "release_note.docx")

    assert [c.title for c in changes] == ["실제 신규 기능"]


def test_release_note_stops_before_description_for_each_version_section():
    """"Description for Each Version" 이후는 앞선 항목의 Before/Now 재서술이라 중복 수집하지 않는다."""
    text = "\n".join(
        [
            "Added",
            "신규 기능 A",
            "Description for Each Version",
            "V1.1.0",
            "Added",
            "Before (V1.0.11)",
            "-",
            "Now (V1.1.0)",
            "신규 기능 A 상세 설명",
        ]
    )

    changes = extract_release_note_changes(text, "release_note.docx")

    assert [c.title for c in changes] == ["신규 기능 A"]


def test_design_review_extracts_numbered_subsection_titles():
    """"2.2.N" 형태로 번호와 제목이 한 줄에 있는 경우."""
    text = "\n".join(["1. 개요", "2. 문제 분석", "2.1 결과 요약", "배경 설명", "2.2 상세 내용", "2.2.1 IC 카드 로그인 기능", "기존 방식의 문제점 설명"])

    changes = extract_design_review_changes(text, "design_review.pdf")

    assert [c.title for c in changes] == ["IC 카드 로그인 기능"]
    assert changes[0].category == "Changed"


def test_design_review_handles_number_alone_then_title_on_next_line():
    """실제 문서에서 번호가 단독 줄이고(예: "2.2.1"), 다음 줄에 제목이 오는 경우도 있었다."""
    text = "\n".join(["2. 문제 분석", "2.2.1", "IC 카드 로그인 기능", "설명 문단 첫 줄", "설명 문단 둘째 줄", "2.2.2", "Generator 자동 연결"])

    changes = extract_design_review_changes(text, "design_review.pdf")

    assert [c.title for c in changes] == ["IC 카드 로그인 기능", "Generator 자동 연결"]


def test_design_review_filters_page_furniture_between_number_and_title():
    text = "\n".join(["2. 문제 분석", "2.2.1", "Vieworks", "Doc. No.: DD-00000000_Rev.A", "Template No.: T-00-0000_r00", "Page 5 / 24", "IC 카드 로그인 기능", "설명"])

    changes = extract_design_review_changes(text, "design_review.pdf")

    assert [c.title for c in changes] == ["IC 카드 로그인 기능"]


def test_design_review_ignores_toc_entries_with_dot_leaders():
    """실제 문서 TOC는 "2. 문제 분석 (...) ..................... 4"처럼 본문 헤더와 동일한
    문구를 점선 리더+페이지 번호로만 구분한다 — TOC에서 조기 종료되면 안 된다."""
    text = "\n".join(
        [
            "1. 개요 .................................................... 3",
            "2. 문제 분석 (해당 설계변경 단계: VCR) .......... 4",
            "3. 설계변경 검토 .......................................... 9",
            "4. 설계변경 적용 결과 분석 ........................ 19",
            "2. 문제 분석 (해당 설계변경 단계: VCR)",
            "2.2.1 IC 카드 로그인 기능",
            "설명",
        ]
    )

    changes = extract_design_review_changes(text, "design_review.pdf")

    assert [c.title for c in changes] == ["IC 카드 로그인 기능"]


def test_design_review_stops_collecting_when_next_top_level_section_reuses_numbering():
    """"3. 설계변경 검토" 같은 다음 대분류 절이 같은 N.N.N 번호 매김을 재사용해도 중복
    수집하지 않는다."""
    text = "\n".join(
        [
            "2. 문제 분석",
            "2.2.1 IC 카드 로그인 기능",
            "설명",
            "3. 설계변경 검토",
            "3.2.1 IC 카드 로그인 기능",
            "설명(중복되면 안 됨)",
        ]
    )

    changes = extract_design_review_changes(text, "design_review.pdf")

    assert [c.title for c in changes] == ["IC 카드 로그인 기능"]


def test_design_review_without_problem_analysis_section_returns_empty():
    assert extract_design_review_changes("1. 개요\n어떤 내용", "design_review.pdf") == []


def _sample_functional_changes() -> list[tuple[int, str]]:
    """BM25 IDF는 아주 작은 말뭉치(2건 이하)에서 흔한 용어의 점수를 0으로 수렴시킬 수 있어
    (rank-bm25 특성), 실제 리비전과 비슷하게 여러 건을 섞어 매칭 신호가 의미 있게 나오도록 한다."""
    return [
        (1, "IC 카드를 이용한 VXvue 로그인 기능을 추가한다."),
        (2, "Display 밝기 설정 자동 저장 방식을 변경한다."),
        (3, "Query and Retrieve 화면에 검색 필터를 추가한다."),
        (4, "프린터 상/하단 레이아웃 크기를 사용자가 설정할 수 있다."),
        (5, "배터리 아이콘에 충전 상태를 표시한다."),
    ]


def test_match_release_changes_finds_matching_manual_change():
    release_changes = extract_release_note_changes("Added\nIC 카드 로그인 기능 추가", "release_note.docx")

    results = match_release_changes(release_changes, _sample_functional_changes())

    assert len(results) == 1
    release_change, matched_id = results[0]
    assert matched_id == 1


def test_match_release_changes_flags_missing_when_no_manual_change_relates():
    release_changes = extract_release_note_changes("Added\n전혀 관련 없는 새로운 스캐너 하드웨어 연동 기능", "release_note.docx")

    results = match_release_changes(release_changes, _sample_functional_changes())

    assert results[0][1] is None


def test_match_release_changes_all_missing_when_no_functional_changes():
    release_changes = extract_release_note_changes("Added\n신규 기능", "release_note.docx")

    results = match_release_changes(release_changes, [])

    assert results == [(release_changes[0], None)]
