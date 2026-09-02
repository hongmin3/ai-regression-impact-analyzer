from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class RevisionMark(str, Enum):
    """원본 PDF의 취소선/밑줄 등 개정 표시 시각 확인 결과 (Rev.1.7 §1.2.1).

    이 파이프라인은 텍스트만 추출하고 PDF 서식(취소선 등)을 분석하지 않으므로
    기본값은 UNVERIFIED이다. NONE_DETECTED는 문장 자체에 삭제/개정 관련 표현이
    없다는 뜻일 뿐, 원본을 시각적으로 확인했다는 뜻이 아니다.
    """

    NONE_DETECTED = "NONE_DETECTED"
    UNVERIFIED = "UNVERIFIED"
    STRIKETHROUGH_DETECTED = "STRIKETHROUGH_DETECTED"
    UNDERLINE_DETECTED = "UNDERLINE_DETECTED"


class TestCase(BaseModel):
    tc_id: str
    category: str = ""
    feature: str = ""
    precondition: str = ""
    step: str = ""
    expected_result: str = ""
    result: str = ""
    remark: str = ""

    @field_validator("tc_id")
    @classmethod
    def non_empty_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("TC ID가 비어 있습니다.")
        return value.strip()

    def searchable_text(self) -> str:
        return " ".join((self.tc_id, self.category, self.feature, self.precondition, self.step, self.expected_result, self.remark))


class SpecificationChunk(BaseModel):
    chunk_id: str
    document_id: str
    page: int
    heading: str = ""
    text: str
    revision_marks: list[RevisionMark] = Field(default_factory=list)
