from app.core.schemas import DraftTestCase, EvidenceLevel, ImpactDecision, SpecificationChunk, TestCase


def classify_confidence(decision: ImpactDecision, recommended: float = 0.8, review: float = 0.6) -> ImpactDecision:
    if decision.confidence >= recommended:
        decision.review_status = "AI_RECOMMENDATION_ACCEPTED"
    elif decision.confidence >= review:
        decision.review_status = "REVIEW_RECOMMENDED"
    else:
        decision.review_status = "MANUAL_REVIEW_REQUIRED"
        decision.manual_review_required = True
    return decision


def validate_decisions(decisions: list[ImpactDecision], cases: list[TestCase], chunks: list[SpecificationChunk], recommended: float = 0.8, review: float = 0.6) -> list[ImpactDecision]:
    valid_ids = {case.tc_id for case in cases}
    valid_refs = {chunk.chunk_id for chunk in chunks}
    result = []
    for decision in decisions:
        if decision.tc_id not in valid_ids:
            continue
        decision.relevant_specifications = [ref for ref in decision.relevant_specifications if ref in valid_refs]
        if not decision.relevant_specifications:
            decision.confidence = min(decision.confidence, 0.59)
            decision.manual_review_required = True
            if decision.evidence_level == EvidenceLevel.EXPLICIT:
                decision.evidence_level = EvidenceLevel.INFERRED
        result.append(classify_confidence(decision, recommended, review))
    return result


def validate_draft_test_cases(drafts: list[DraftTestCase], chunks: list[SpecificationChunk], limit: int = 20) -> list[DraftTestCase]:
    valid_refs = {chunk.chunk_id for chunk in chunks}
    for draft in drafts:
        draft.evidence_chunk_ids = [ref for ref in draft.evidence_chunk_ids if ref in valid_refs]
    return drafts[:limit]
