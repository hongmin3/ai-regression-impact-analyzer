from app.modules.impact_analyzer.change_analyzer import analyze_change_rules, trim_by_relevance
from app.modules.impact_analyzer.tc_candidate_selector import select_candidates
from app.modules.impact_analyzer.validation import attach_specification_references, classify_confidence, validate_decisions, validate_draft_test_cases
from app.modules.impact_analyzer.schemas import DraftTestCase, EvidenceLevel, Impact, ImpactDecision, RevisionMark, SpecificationChunk, TestCase


def decision(confidence: float) -> ImpactDecision:
    return ImpactDecision(tc_id="TC-1", impact=Impact.HIGH, confidence=confidence, direct_impact=True, regression_needed=True, reason="설정 저장 변경", relevant_specifications=["spec-p1-0"], verification_points=["재실행"], recommended=True)


def test_trim_by_relevance_keeps_short_text_untouched():
    text = "로그인 화면 변경\nDICOM 전송 변경"
    assert trim_by_relevance(text, "로그인", top_k=60) == text


def test_trim_by_relevance_shrinks_large_text_to_relevant_lines():
    unrelated = [f"관련 없는 설정 항목 {i}" for i in range(100)]
    text = "\n".join(unrelated + ["로그인 화면에 지문 인증 옵션을 추가한다."])
    trimmed = trim_by_relevance(text, "지문 인증 로그인", top_k=10)
    assert "지문 인증 옵션" in trimmed
    assert len(trimmed.splitlines()) <= 10


def test_trim_by_relevance_no_query_returns_original():
    text = "\n".join(f"line {i}" for i in range(100))
    assert trim_by_relevance(text, "", top_k=10) == text


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


def test_change_rules_ignore_lines_present_in_baseline():
    baseline = "로그인 화면에 아이디를 입력한다.\n비밀번호를 입력하고 로그인 버튼을 누른다."
    change = "로그인 화면에 아이디를 입력한다.\nDisplay 설정 저장 방식을 변경한다."
    result = analyze_change_rules(change, baseline_text=baseline)
    assert result.changed_features == ["Display 설정 저장 방식을 변경한다."]


def test_change_rules_without_baseline_uses_all_lines():
    change = "로그인 화면에 아이디를 입력한다.\nDisplay 설정 저장 방식을 변경한다."
    result = analyze_change_rules(change)
    assert len(result.changed_features) == 1
    assert "변경한다" in result.changed_features[0]


def test_draft_test_cases_drop_unknown_chunk_ids():
    drafts = [DraftTestCase(changed_feature="신규 기능", evidence_chunk_ids=["spec-p1-0", "fake-chunk"])]
    chunks = [SpecificationChunk(chunk_id="spec-p1-0", document_id="spec", page=1, text="설정")]
    result = validate_draft_test_cases(drafts, chunks)
    assert result[0].evidence_chunk_ids == ["spec-p1-0"]


def test_draft_test_cases_capped_at_limit():
    drafts = [DraftTestCase(changed_feature=f"기능{i}") for i in range(30)]
    assert len(validate_draft_test_cases(drafts, [], limit=20)) == 20


def test_explicit_evidence_level_downgraded_without_relevant_specs():
    claim = decision(.9).model_copy(update={"relevant_specifications": ["missing-chunk"], "evidence_level": EvidenceLevel.EXPLICIT})
    result = validate_decisions([claim], [TestCase(tc_id="TC-1")], [])
    assert result[0].evidence_level is EvidenceLevel.INFERRED
    assert result[0].manual_review_required


def test_user_notes_included_as_changed_feature_without_keyword_match():
    result = analyze_change_rules("", user_notes="지문 인증 옵션을 추가해줘")
    assert "지문 인증 옵션을 추가해줘" in result.changed_features
    assert result.user_notes == "지문 인증 옵션을 추가해줘"


def test_user_notes_take_priority_position_over_document_lines():
    change = "Display 설정 저장 방식을 변경한다."
    result = analyze_change_rules(change, user_notes="로그인 기능만 집중 확인")
    assert result.changed_features[0] == "로그인 기능만 집중 확인"


def test_attach_specification_references_builds_human_readable_label():
    chunks = [SpecificationChunk(chunk_id="abc123-p348-0", document_id="abc123", page=348, heading="DAP Communication", text="...")]
    doc_labels = {"abc123": "VXvue 사양서3"}
    decisions = [decision(.9).model_copy(update={"relevant_specifications": ["abc123-p348-0"]})]

    result = attach_specification_references(decisions, chunks, doc_labels)

    assert result[0].specification_reference == "VXvue 사양서3 · DAP Communication · p.348"


def test_attach_specification_references_blank_when_no_match():
    decisions = [decision(.9).model_copy(update={"relevant_specifications": []})]
    result = attach_specification_references(decisions, [], {})
    assert result[0].specification_reference == ""


def test_evidence_level_and_revision_mark_defaults():
    decision_default = ImpactDecision(tc_id="TC-1", impact=Impact.LOW, confidence=.5, reason="확인 필요")
    assert decision_default.evidence_level is EvidenceLevel.INFERRED
    assert decision_default.revision_mark is RevisionMark.UNVERIFIED
