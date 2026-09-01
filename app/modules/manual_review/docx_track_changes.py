"""Word Track Changes(<w:ins>/<w:del>/<w:moveFrom>/<w:moveTo>) 구조화 추출.

document_parser.py와 동일하게 python-docx 없이 zipfile+ElementTree로 word/document.xml만
읽는다 (신규 의존성 추가는 OPEN_QUESTIONS.md에서 사용자 결정을 기다린다). 단순 서식/페이지
번호 등 NON_FUNCTIONAL_CHANGE 필터링, section/heading 매핑, Word Comment 삽입(쓰기)은
이후 단계 범위이며 이 모듈은 순수 추출만 담당한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

_KIND_BY_TAG = {
    f"{W_NS}ins": "insertion",
    f"{W_NS}del": "deletion",
    f"{W_NS}moveFrom": "move_from",
    f"{W_NS}moveTo": "move_to",
}
# 최종 승인본(plain_text)에 남는 종류 — 삽입과 이동 도착지만 포함하고, 삭제와 이동 출발지는 제외한다.
_KEPT_IN_PLAIN_TEXT = {"insertion", "move_to"}


@dataclass
class TrackedChange:
    kind: str  # insertion | deletion | move_from | move_to
    author: str
    date: str
    text: str
    paragraph_index: int


@dataclass
class TrackChangesResult:
    changes: list[TrackedChange] = field(default_factory=list)
    plain_text: str = ""


def _text_of(element: ET.Element) -> str:
    """<w:r> 하위의 <w:t>/<w:delText>를 문서 순서대로 이어붙인다."""
    return "".join(node.text or "" for node in element.iter() if node.tag in (f"{W_NS}t", f"{W_NS}delText"))


def extract_track_changes_from_xml(xml_bytes: bytes) -> TrackChangesResult:
    root = ET.fromstring(xml_bytes)
    result = TrackChangesResult()
    plain_lines: list[str] = []
    for paragraph_index, paragraph in enumerate(root.iter(f"{W_NS}p")):
        paragraph_plain: list[str] = []
        for child in paragraph:
            kind = _KIND_BY_TAG.get(child.tag)
            if kind:
                text = _text_of(child)
                result.changes.append(
                    TrackedChange(
                        kind=kind,
                        author=child.get(f"{W_NS}author", ""),
                        date=child.get(f"{W_NS}date", ""),
                        text=text,
                        paragraph_index=paragraph_index,
                    )
                )
                if kind in _KEPT_IN_PLAIN_TEXT:
                    paragraph_plain.append(text)
            elif child.tag == f"{W_NS}r":
                paragraph_plain.append(_text_of(child))
        line = "".join(paragraph_plain).strip()
        if line:
            plain_lines.append(line)
    result.plain_text = "\n".join(plain_lines)
    return result


def extract_track_changes(path: Path) -> TrackChangesResult:
    with ZipFile(path) as archive:
        xml_bytes = archive.read("word/document.xml")
    return extract_track_changes_from_xml(xml_bytes)
