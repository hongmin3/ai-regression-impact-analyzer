from app.core.schemas import ChangeAnalysis, TestCase
from app.retrieval.bm25_retriever import BM25Retriever


def select_candidates(change: ChangeAnalysis, cases: list[TestCase], limit: int = 150) -> list[TestCase]:
    query = " ".join(change.changed_features + change.risk_keywords + [change.purpose])
    if not query.strip():
        return cases[:limit]
    retriever = BM25Retriever(cases, lambda case: case.searchable_text())
    return [case for case, _ in retriever.search(query, limit)]
