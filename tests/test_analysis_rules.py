from app.analyzers.change_analyzer import analyze_change_rules
from app.analyzers.tc_candidate_selector import select_candidates
from app.analyzers.validation import classify_confidence, validate_decisions
from app.core.schemas import Impact, ImpactDecision, SpecificationChunk, TestCase


def decision(confidence: float) -> ImpactDecision:
    return ImpactDecision(tc_id="TC-1", impact=Impact.HIGH, confidence=confidence, direct_impact=True, regression_needed=True, reason="설정 저장 변경", relevant_specifications=["spec-p1-0"], verification_points=["재실행"], recommended=True)


def test_candidate_search():
    change = analyze_change_rules("Display 설정 저장 방식을 변경")
    cases = [TestCase(tc_id="TC-1", feature="Display 설정", step="저장"), TestCase(tc_id="TC-2", feature="로그인")]
    assert select_candidates(change, cases, 10)[0].tc_id == "TC-1"


def test_confidence_classification():
    assert classify_confidence(decision(.9)).review_status == "AI_RECOMMENDATION_ACCEPTED"
    assert classify_confidence(decision(.7)).review_status == "REVIEW_RECOMMENDED"
    assert classify_confidence(decision(.5)).manual_review_required


def test_hallucinated_id_is_discarded():
    fake = decision(.9).model_copy(update={"tc_id": "FAKE"})
    chunks = [SpecificationChunk(chunk_id="spec-p1-0", document_id="spec", page=1, text="setting")]
    assert validate_decisions([fake], [TestCase(tc_id="TC-1")], chunks) == []
