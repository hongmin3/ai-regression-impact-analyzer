"""Release/설계 변경이 같은 제품의 다른 매뉴얼에도 관련되는지 검색한다.

결과는 확정 판정이 아니라 QA가 원문을 확인할 REVIEW_REQUIRED 후보이다.

대조 대상 매뉴얼은 세 곳에서 이 순서로 모은다.

1. 이 앱에 등록된 최신 매뉴얼 리비전 — 지금 검증 흐름에서 직접 올린 것이라 가장 가깝다.
2. **매뉴얼 서버(하위 서비스)의 Current 버전** — 조직이 최신본으로 인정한 문서다.
   설정과 자격증명이 있을 때만 조회하며, 서버가 내려가 있어도 이 단계만 건너뛴다.
3. 등록된 Knowledge 문서 중 이름이 매칭되는 것 — 하위 호환 소스.

같은 매뉴얼 이름이 여러 곳에 있으면 앞 순서가 이긴다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.core import manual_hub_client
from app.core.config import get_settings
from app.core.product_config import list_product_configs
from app.core.storage import Storage
from app.modules.manual_review.release_scope import ReleaseChange
from app.parsers.document_parser import extract_document_text
from app.retrieval.bm25_retriever import BM25Retriever

logger = logging.getLogger(__name__)


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


def load_manual_hub_sources(product: str, current_manual: str) -> dict[str, tuple[str, Path]]:
    """매뉴얼 서버에서 이 제품의 다른 매뉴얼 Current 버전을 받아 온다.

    연동이 꺼져 있거나 매뉴얼 서버가 응답하지 않으면 **빈 결과**를 돌려준다. 하위 서비스가
    내려갔다고 매뉴얼 개정 검증 자체가 실패하면 안 되기 때문이다."""
    sources: dict[str, tuple[str, Path]] = {}
    try:
        # 클라이언트 생성(설정·비밀정보 로딩)까지 try 안에 둔다. 여기서 터지면 연동을
        # 켜지도 못한 채 매뉴얼 개정 검증 전체가 실패한다.
        client = manual_hub_client.from_settings()
        if client is None:
            return {}
        cache_dir = get_settings().path("storage.manual_hub_cache_dir") / product
        with client:
            product_id = client.find_product_id(product)
            if not product_id:
                return {}
            for document in client.documents(product_id):
                if document.name == current_manual:
                    continue
                path = client.download_current(document, cache_dir)
                if path is not None:
                    label = f"{document.name} (매뉴얼 서버 {document.current_revision})".strip()
                    sources[document.name] = (label, path)
    except Exception:  # noqa: BLE001 - 연동 실패가 검증 실패로 번지지 않게 한다
        logger.warning("매뉴얼 서버 연동 조회에 실패해 이번 검증에서는 건너뜁니다.", exc_info=True)
        return {}
    return sources


def load_other_manual_sources(storage: Storage, product: str, current_manual: str) -> list[tuple[str, str, Path]]:
    sources: dict[str, tuple[str, Path]] = {}
    for revision in storage.latest_manual_revisions_by_name(product):
        if revision["manual_name"] != current_manual:
            path = Path(revision["source_path"])
            if path.exists():
                sources[revision["manual_name"]] = (path.name, path)
    for name, value in load_manual_hub_sources(product, current_manual).items():
        sources.setdefault(name, value)
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
