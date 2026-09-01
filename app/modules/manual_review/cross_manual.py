"""Release/설계 변경이 같은 제품의 다른 매뉴얼에도 관련되는지 로컬 검색한다.

결과는 확정 판정이 아니라 QA가 원문을 확인할 REVIEW_REQUIRED 후보이다. 최신 매뉴얼
리비전을 우선 사용하고, 아직 리비전이 없는 경우 Knowledge 문서명에 매뉴얼 이름이 포함된
문서를 하위 호환 소스로 사용한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.product_config import list_product_configs
from app.core.storage import Storage
from app.modules.manual_review.release_scope import ReleaseChange
from app.parsers.document_parser import extract_document_text
from app.retrieval.bm25_retriever import BM25Retriever


@dataclass
class CrossManualImpact:
    target_manual: str
    source_document: str
    release_change: ReleaseChange
    evidence_text: str
    relevance_score: float


def _manual_names(storage: Storage, product: str) -> list[str]:
    names = {row["manual_name"] for row in storage.list_manual_revisions(product)}
    for config in list_product_configs():
        if config.product == product:
            names.update(config.manual_types)
    return sorted(names)


def _paragraphs(path: Path) -> list[str]:
    text = extract_document_text(path)
    return [line.strip() for line in text.splitlines() if len(line.strip()) >= 12]


def load_other_manual_sources(storage: Storage, product: str, current_manual: str) -> list[tuple[str, str, Path]]:
    sources: dict[str, tuple[str, Path]] = {}
    for revision in storage.latest_manual_revisions_by_name(product):
        if revision["manual_name"] != current_manual:
            path = Path(revision["source_path"])
            if path.exists():
                sources[revision["manual_name"]] = (path.name, path)
    documents = storage.active_documents("manual", product) + storage.active_documents("specification", product)
    for manual_name in _manual_names(storage, product):
        if manual_name == current_manual or manual_name in sources:
            continue
        document = next((doc for doc in reversed(documents) if manual_name.lower() in doc["name"].lower()), None)
        if document:
            path = Path(document["path"])
            if path.exists():
                sources[manual_name] = (document["name"], path)
    return [(name, source_name, path) for name, (source_name, path) in sources.items()]


def find_cross_manual_impacts(
    storage: Storage, product: str, current_manual: str, release_changes: list[ReleaseChange]
) -> list[CrossManualImpact]:
    impacts: list[CrossManualImpact] = []
    if not release_changes:
        return impacts
    for manual_name, source_name, path in load_other_manual_sources(storage, product, current_manual):
        paragraphs = _paragraphs(path)
        if not paragraphs:
            continue
        retriever = BM25Retriever(paragraphs, lambda value: value)
        for change in release_changes:
            query = f"{change.title} {change.description}".strip()
            matches = retriever.search(query, 1)
            if matches and matches[0][1] > 0:
                impacts.append(CrossManualImpact(manual_name, source_name, change, matches[0][0][:1000], matches[0][1]))
    return sorted(impacts, key=lambda item: item.relevance_score, reverse=True)
