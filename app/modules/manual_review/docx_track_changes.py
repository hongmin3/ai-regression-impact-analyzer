"""Word Track Changes(<w:ins>/<w:del>/<w:moveFrom>/<w:moveTo>) 구조화 추출.

document_parser.py와 동일하게 python-docx 없이 zipfile+ElementTree로 word/document.xml만
읽는다 — 순수 추출(읽기)만 하는 이 모듈은 그걸로 충분하다. Word Comment 삽입(쓰기)은
python-docx가 필요해(`comment_writer.py`) 별도 의존성으로 추가돼 있다. 단순 서식/페이지
번호 등 NON_FUNCTIONAL_CHANGE 필터링, section/heading 매핑도 이 모듈 범위 밖이며 이
모듈은 순수 추출만 담당한다.
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
    source_page: int | None = None
    review_required: bool = False
    # 같은 문단(paragraph_index) 안에서 이 변경이 몇 번째 <w:ins>/<w:del>/<w:moveFrom>/<w:moveTo>
    # 인지(0부터). comment_writer.py가 문단 전체가 아니라 이 변경만 정확히 앵커링하는 데 쓴다.
    change_index_in_paragraph: int = 0


@dataclass
class TrackChangesResult:
    changes: list[TrackedChange] = field(default_factory=list)
    plain_text: str = ""


def _text_of(element: ET.Element) -> str:
    """<w:r> 하위의 <w:t>/<w:delText>를 문서 순서대로 이어붙인다."""
    return "".join(node.text or "" for node in element.iter() if node.tag in (f"{W_NS}t", f"{W_NS}delText"))


def _has_image(element: ET.Element) -> bool:
    return any(node.tag.rsplit("}", 1)[-1] in {"drawing", "pict", "blip"} for node in element.iter())


def _image_description(element: ET.Element) -> str:
    for node in element.iter():
        if node.tag.rsplit("}", 1)[-1] == "docPr":
            return node.get("descr") or node.get("name") or ""
    return ""


def extract_track_changes_from_xml(xml_bytes: bytes) -> TrackChangesResult:
    root = ET.fromstring(xml_bytes)
    result = TrackChangesResult()
    plain_lines: list[str] = []
    for paragraph_index, paragraph in enumerate(root.iter(f"{W_NS}p")):
        paragraph_plain: list[str] = []
        change_index_in_paragraph = 0
        for child in paragraph:
            kind = _KIND_BY_TAG.get(child.tag)
            if kind:
                text = _text_of(child)
                has_image = _has_image(child)
                if has_image and not text.strip():
                    description = _image_description(child)
                    text = f"이미지 변경{f' ({description})' if description else ''}"
                result.changes.append(
                    TrackedChange(
                        kind=f"image_{kind}" if has_image else kind,
                        author=child.get(f"{W_NS}author", ""),
                        date=child.get(f"{W_NS}date", ""),
                        text=text,
                        paragraph_index=paragraph_index,
                        review_required=has_image,
                        change_index_in_paragraph=change_index_in_paragraph,
                    )
                )
                change_index_in_paragraph += 1
                if kind in _KEPT_IN_PLAIN_TEXT and not has_image:
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
