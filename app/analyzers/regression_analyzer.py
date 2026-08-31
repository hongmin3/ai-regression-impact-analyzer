from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.analyzers.change_analyzer import analyze_change_rules
from app.analyzers.tc_candidate_selector import select_candidates
from app.analyzers.validation import validate_decisions, validate_draft_test_cases
from app.core.config import get_settings
from app.core.gemini_client import GeminiClient
from app.core.logger import configure_logging
from app.core.schemas import AnalysisResult, SpecificationChunk, TestCase
from app.core.storage import Storage
from app.parsers.excel_parser import parse_testcases
from app.parsers.document_parser import extract_document_text, parse_document
from app.reports.html_report import create_csv_export, create_html_report, create_xlsx_export
from app.reports.tc_draft import create_tc_draft_markdown
from app.retrieval.bm25_retriever import BM25Retriever


class RegressionAnalyzer:
    def __init__(self, gemini: GeminiClient | None = None, storage: Storage | None = None) -> None:
        self.settings = get_settings()
        self.gemini = gemini or GeminiClient()
        self.storage = storage or Storage()
        self.logger = configure_logging()

    def run(self, change_path: Path, specification_path: Path, testcase_path: Path, analysis_id: str | None = None) -> AnalysisResult:
        baseline_text = extract_document_text(specification_path)
        chunks = parse_document(specification_path, specification_path.stem)
        cases = parse_testcases(testcase_path)
        return self._execute(change_path, chunks, cases, baseline_text, specification_path.name, testcase_path.name, analysis_id)

    def run_for_product(self, change_path: Path, product: str, analysis_id: str | None = None) -> AnalysisResult:
        """개별 사양서/TC를 고르지 않고, 제품에 등록된 모든 사양서·TC 문서를 검색 대상으로 삼는다.

        사양서1~5처럼 같은 제품에 서로 다른 문서가 여러 개 등록될 수 있으므로, 새 문서가
        추가돼도 이전 문서를 제외하지 않고 전부 합쳐서 검색한다 (Storage.active_documents).
        """
        spec_docs = self.storage.active_documents("specification", product)
        tc_docs = self.storage.active_documents("testcase", product)
        if not spec_docs or not tc_docs:
            raise ValueError(f"'{product}' 제품에 등록된 사양서 또는 TC가 없습니다.")
        chunks: list[SpecificationChunk] = []
        baseline_texts: list[str] = []
        for doc in spec_docs:
            path = Path(doc["path"])
            chunks.extend(parse_document(path, path.stem))
            baseline_texts.append(extract_document_text(path))
        cases: list[TestCase] = []
        for doc in tc_docs:
            cases.extend(parse_testcases(Path(doc["path"])))
        spec_label = ", ".join(doc["name"] for doc in spec_docs)
        tc_label = ", ".join(doc["name"] for doc in tc_docs)
        return self._execute(change_path, chunks, cases, "\n".join(baseline_texts), spec_label, tc_label, analysis_id)

    def _execute(
        self,
        change_path: Path,
        chunks: list[SpecificationChunk],
        cases: list[TestCase],
        baseline_text: str,
        specification_label: str,
        testcase_label: str,
        analysis_id: str | None,
    ) -> AnalysisResult:
        started = time.monotonic()
        analysis_id = analysis_id or uuid.uuid4().hex[:12]
        self.logger.info("analysis_started id=%s change=%s spec=%s tc=%s model=%s", analysis_id, change_path.name, specification_label, testcase_label, self.settings.secrets.gemini_model)
        try:
            change_text = extract_document_text(change_path)
            change = analyze_change_rules(change_text, baseline_text=baseline_text)
            candidates = select_candidates(change, cases, int(self.settings.get("retrieval.candidate_limit", 150)))
            query = " ".join(change.changed_features + change.risk_keywords + [change.purpose])
            relevant_chunks = [chunk for chunk, _ in BM25Retriever(chunks, lambda item: f"{item.heading} {item.text}").search(query, int(self.settings.get("retrieval.specification_top_k", 8)))]
            decisions = self.gemini.analyze(change, candidates, relevant_chunks)
            decisions = validate_decisions(decisions, cases, relevant_chunks, float(self.settings.get("analysis.recommended_confidence", .8)), float(self.settings.get("analysis.review_confidence", .6)))
            drafts = validate_draft_test_cases(self.gemini.draft_test_cases, relevant_chunks)
            result = AnalysisResult(analysis_id=analysis_id, created_at=datetime.now(timezone.utc), change_file=change_path.name, specification_file=specification_label, testcase_file=testcase_label, change=change, total_tc=len(cases), candidate_tc=len(candidates), decisions=decisions, draft_test_cases=drafts, token_usage=self.gemini.token_usage)
            result.report_path = create_html_report(result)
            create_csv_export(result)
            create_xlsx_export(result)
            result.draft_tc_path = create_tc_draft_markdown(result)
            self.logger.info("analysis_finished id=%s requests=%s prompt_tokens=%s candidate_tokens=%s total_tokens=%s manual_review=%s elapsed=%.3f", analysis_id, self.gemini.request_count, self.gemini.token_usage.get("prompt_tokens", 0), self.gemini.token_usage.get("candidate_tokens", 0), self.gemini.token_usage.get("total_tokens", 0), sum(item.manual_review_required for item in decisions), time.monotonic() - started)
            return result
        except Exception as exc:
            self.logger.exception("analysis_failed id=%s error_type=%s elapsed=%.3f", analysis_id, type(exc).__name__, time.monotonic() - started)
            raise
