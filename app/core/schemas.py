from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class Impact(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class ChangeAnalysis(BaseModel):
    changed_features: list[str] = Field(default_factory=list)
    purpose: str = ""
    ui_changes: list[str] = Field(default_factory=list)
    interface_changes: list[str] = Field(default_factory=list)
    dicom_changes: list[str] = Field(default_factory=list)
    workflow_changes: list[str] = Field(default_factory=list)
    configuration_changes: list[str] = Field(default_factory=list)
    stored_data_changes: list[str] = Field(default_factory=list)
    compatibility_changes: list[str] = Field(default_factory=list)
    risk_keywords: list[str] = Field(default_factory=list)


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


class ImpactDecision(BaseModel):
    tc_id: str
    impact: Impact
    confidence: float = Field(ge=0.0, le=1.0)
    direct_impact: bool = False
    indirect_impact: bool = False
    regression_needed: bool = False
    reason: str
    relevant_specifications: list[str] = Field(default_factory=list)
    verification_points: list[str] = Field(default_factory=list)
    recommended: bool = False
    manual_review_required: bool = False
    review_status: str = ""


class AnalysisResult(BaseModel):
    analysis_id: str
    created_at: datetime
    change_file: str
    specification_file: str
    testcase_file: str
    change: ChangeAnalysis
    total_tc: int
    candidate_tc: int
    decisions: list[ImpactDecision]
    report_path: Path | None = None

    @property
    def recommended_count(self) -> int:
        return sum(item.recommended for item in self.decisions)
