from datetime import datetime, timezone

from app.core.gemini_client import GeminiClient
from app.core.schemas import AnalysisResult, ChangeAnalysis, Impact, ImpactDecision, SpecificationChunk, TestCase
from app.core.storage import Storage
from app.reports.html_report import create_csv_export, create_html_report


def test_mock_gemini_structured_output(tmp_path):
    response = {"decisions": [{"tc_id": "TC-1", "impact": "HIGH", "confidence": .91, "direct_impact": True, "regression_needed": True, "reason": "저장 변경", "relevant_specifications": ["spec-p1-0"], "verification_points": ["재실행"], "recommended": True}]}
    client = GeminiClient(Storage(tmp_path / "test.db"), responder=lambda _: response)
    values = client.analyze(ChangeAnalysis(changed_features=["설정 저장"]), [TestCase(tc_id="TC-1")], [SpecificationChunk(chunk_id="spec-p1-0", document_id="spec", page=1, text="설정 저장")])
    assert values[0].impact is Impact.HIGH
    assert client.request_count == 1


def test_report_generation():
    result = AnalysisResult(analysis_id="unit-test", created_at=datetime.now(timezone.utc), change_file="change.pdf", specification_file="spec.pdf", testcase_file="tc.xlsx", change=ChangeAnalysis(changed_features=["설정"]), total_tc=1, candidate_tc=1, decisions=[ImpactDecision(tc_id="TC-1", impact="HIGH", confidence=.9, reason="변경 영향", recommended=True)])
    assert create_html_report(result).exists()
    assert create_csv_export(result).exists()
