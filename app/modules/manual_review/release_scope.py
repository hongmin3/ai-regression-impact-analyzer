"""Release Note / 설계검토보고서에서 이번 Release의 변경 Scope를 로컬 규칙 기반으로 추출한다
(스펙 §7). AI를 검색 엔진으로 쓰지 않는다는 원칙(스펙 §17) 때문에, 이 단계는 순수 텍스트
파싱/분류만 하고 Gemini를 호출하지 않는다.

2026-09-01 세션에서 실제 VXvue 1.1.0 Release Note(.docx)와 설계검토보고서(.pdf)로 검증하며
아래 두 가지를 실제 문서 구조에 맞게 조정했다:

- Release Note: 문서 앞부분에 담당자/버전 호환성 표 같은 메타데이터가 먼저 나오므로, 첫
  카테고리 헤더(Added/Changed/Fixed bug/Etc)를 만나기 전 줄은 전부 건너뛴다. "Etc" 헤더는
  실제로 "Etc (내부 배포용 – 대외비, 재설계, 연동 등)"처럼 괄호 부연 설명이 붙어 있어 완전
  일치가 아닌 접두 매칭으로 완화했다. "Description for Each Version" 이후는 앞선 항목을
  Before/Now 형식으로 다시 풀어쓴 절이라 중복 수집하지 않고 그 지점에서 멈춘다.
- 설계검토보고서: "변경 결과" 표는 PyMuPDF가 컬럼 구분 없이 표를 한 줄씩 풀어버려 제목/상세를
  안정적으로 분리할 수 없었다. 대신 "문제 분석" 절의 번호 매김 항목(예: "2.2.1"+제목)에서
  제목만 추출한다 — 실제 문서로 대조한 결과 이 제목이 "변경 결과" 표의 "변경 항목" 값과
  동일해 대체 가능함을 확인했다. 페이지마다 반복되는 문서 header/footer 잡음(Doc. No./
  Template No./Page N / M/회사명)은 걸러낸다.

실제 문서 서식은 회사·문서마다 다를 수 있어, 이 파서는 위 관찰을 반영한 최선의 휴리스틱이다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.retrieval.bm25_retriever import BM25Retriever

_CATEGORY_HEADER_PATTERNS: dict[str, re.Pattern] = {
    "Added": re.compile(r"^(added|추가(\s*기능)?)\s*(\(.*\))?\s*[:：]?\s*$", re.IGNORECASE),
    "Changed": re.compile(r"^(changed|변경|개선(\s*사항)?)\s*(\(.*\))?\s*[:：]?\s*$", re.IGNORECASE),
    "Fixed bug": re.compile(r"^(fixed\s*bug|버그\s*수정|결함\s*수정)\s*(\(.*\))?\s*[:：]?\s*$", re.IGNORECASE),
    "Etc": re.compile(r"^(etc|기타)\s*(\(.*\))?\s*[:：]?\s*$", re.IGNORECASE),
}
_RELEASE_NOTE_STOP_PATTERNS = (
    re.compile(r"^description\s+for\s+each\s+version", re.IGNORECASE),
    re.compile(r"^버전별\s*(상세)?\s*설명"),
)
_LEADING_NUMBER_RE = re.compile(r"^\d{1,3}\s+(?=\S)")

_PROBLEM_ANALYSIS_HEADER_RE = re.compile(r"^\d+\.\s*문제\s*분석")
# "N. 제목" 형태의 대분류 절 헤더 — 첫 마침표 뒤가 공백이라 "2.2.1 제목"(소분류 항목) 과
# 구별된다. 목표 절(문제 분석)에 들어간 뒤 이 패턴의 다른 절을 만나면(3. 설계변경 검토 등)
# 그 절도 같은 N.N.N 번호 매김을 재사용해 항목이 중복 수집되므로, 여기서 벗어난다.
_TOP_LEVEL_SECTION_RE = re.compile(r"^\d+\.\s+\S")
_SUBSECTION_ITEM_RE = re.compile(r"^(\d+\.\d+\.\d+)\.?\s*(.*)$")
_PAGE_FURNITURE_RE = re.compile(r"^(vieworks|doc\.\s*no\.|template\s*no\.|page\s*\d+\s*/\s*\d+)", re.IGNORECASE)
# 목차(TOC) 항목은 실제 섹션 헤더와 문구가 동일하고 점선 리더+페이지 번호로만 구분되므로,
# 점선 리더가 보이면 헤더/본문 판정 없이 그 줄 전체를 건너뛴다 (안 그러면 TOC에서 조기 종료됨).
_TOC_LEADER_RE = re.compile(r"\.{3,}")


@dataclass
class ReleaseChange:
    source_document: str
    category: str
    title: str


def extract_release_note_changes(text: str, source_document: str) -> list[ReleaseChange]:
    """카테고리 헤더 줄(Added/Changed/Fixed bug/Etc, 국문 병기 포함)을 만나면 이후 줄들을
    그 카테고리로 분류한다. 첫 헤더를 만나기 전 줄(문서 메타데이터 등)은 수집하지 않는다."""
    changes: list[ReleaseChange] = []
    current_category: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip(" -•\t")
        if not line:
            continue
        if any(pattern.match(line) for pattern in _RELEASE_NOTE_STOP_PATTERNS):
            break
        matched_category = next((category for category, pattern in _CATEGORY_HEADER_PATTERNS.items() if pattern.match(line)), None)
        if matched_category:
            current_category = matched_category
            continue
        if current_category is None:
            continue
        title = _LEADING_NUMBER_RE.sub("", line)
        changes.append(ReleaseChange(source_document=source_document, category=current_category, title=title[:200]))
    return changes


def extract_design_review_changes(text: str, source_document: str) -> list[ReleaseChange]:
    """'문제 분석' 절의 번호 매김 항목(예: "2.2.1" 또는 "2.2.10 제목")에서 제목만 추출한다.
    번호가 단독 줄이면 다음 비어있지 않은(페이지 잡음 제외) 줄을 제목으로 쓰고, 번호와 제목이
    한 줄이면 그대로 쓴다. 다른 대분류 절로 넘어가면(예: "3. 설계변경 검토") 수집을 멈춘다 —
    그 절들이 같은 N.N.N 번호 매김을 재사용해 항목이 중복 수집되는 것을 막기 위함이다."""
    changes: list[ReleaseChange] = []
    in_target_section = False
    pending_number = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or _PAGE_FURNITURE_RE.match(line) or _TOC_LEADER_RE.search(line):
            continue
        if _TOP_LEVEL_SECTION_RE.match(line):
            in_target_section = bool(_PROBLEM_ANALYSIS_HEADER_RE.match(line))
            pending_number = False
            continue
        if not in_target_section:
            continue
        match = _SUBSECTION_ITEM_RE.match(line)
        if match:
            title_on_same_line = match.group(2).strip()
            if title_on_same_line:
                changes.append(ReleaseChange(source_document=source_document, category="Changed", title=title_on_same_line[:200]))
                pending_number = False
            else:
                pending_number = True
            continue
        if pending_number:
            changes.append(ReleaseChange(source_document=source_document, category="Changed", title=line[:200]))
            pending_number = False
        # else: 설명 본문 줄 — 제목만 추출하므로 건너뜀
    return changes


def match_release_changes(release_changes: list[ReleaseChange], functional_changes: list[tuple[int, str]]) -> list[tuple[ReleaseChange, int | None]]:
    """release_change마다 이번 리비전의 functional manual change(change_id, text) 중 BM25로
    가장 관련 있는 것을 찾는다. 매칭되면 (release_change, change_id)를, 매칭되는 게 없으면
    (release_change, None)을 반환한다 — None은 "누락 의심"(MISSING_SUSPECTED) 후보다.

    주의: rank-bm25의 IDF 계산 특성상 functional_changes가 아주 적으면(예: 2건 이하) 실제로
    관련 있는 항목도 점수가 0으로 나와 "누락 의심"으로 오판될 수 있다. 이 함수의 결과는 항상
    "의심" 신호일 뿐 확정 판정이 아니므로, 화면에서도 QA 확인이 필요한 참고 정보로만 표시한다."""
    if not functional_changes or not release_changes:
        return [(rc, None) for rc in release_changes]
    retriever = BM25Retriever(functional_changes, lambda item: item[1])
    results: list[tuple[ReleaseChange, int | None]] = []
    for release_change in release_changes:
        matches = retriever.search(release_change.title, 1)
        if matches and matches[0][1] > 0:
            results.append((release_change, matches[0][0][0]))
        else:
            results.append((release_change, None))
    return results
