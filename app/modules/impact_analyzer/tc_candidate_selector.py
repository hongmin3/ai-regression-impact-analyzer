from app.modules.impact_analyzer.schemas import ChangeAnalysis, TestCase
from app.retrieval.bm25_retriever import BM25Retriever


def select_candidates(change: ChangeAnalysis, cases: list[TestCase], limit: int = 150) -> list[TestCase]:
    return [case for case, _ in select_candidates_with_scores(change, cases, limit)]


def select_candidates_with_scores(change: ChangeAnalysis, cases: list[TestCase], limit: int = 150) -> list[tuple[TestCase, float]]:
    query = " ".join(change.changed_features + change.risk_keywords + [change.purpose])
    if not query.strip():
        return [(case, 0.0) for case in cases[:limit]]
    retriever = BM25Retriever(cases, lambda case: case.searchable_text())
    return retriever.search(query, limit)
