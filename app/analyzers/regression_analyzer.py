from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.analyzers.change_analyzer import analyze_change_rules
from app.analyzers.tc_candidate_selector import select_candidates
from app.analyzers.validation import validate_decisions
from app.core.config import get_settings
from app.core.gemini_client import GeminiClient
from app.core.logger import configure_logging
from app.core.schemas import AnalysisResult
from app.parsers.excel_parser import parse_testcases
from app.parsers.pdf_parser import extract_pdf_text, parse_specification
from app.reports.html_report import create_csv_export, create_html_report
from app.retrieval.bm25_retriever import BM25Retriever


class RegressionAnalyzer:
    def __init__(self, gemini: GeminiClient | None = None) -> None:
        self.settings = get_settings()
        self.gemini = gemini or GeminiClient()
        self.logger = configure_logging()

    def run(self, change_path: Path, specification_path: Path, testcase_path: Path) -> AnalysisResult:
        started = time.monotonic()
        analysis_id = uuid.uuid4().hex[:12]
        self.logger.info("analysis_started id=%s change=%s spec=%s tc=%s model=%s", analysis_id, change_path.name, specification_path.name, testcase_path.name, self.settings.secrets.gemini_model)
        try:
            change_text = extract_pdf_text(change_path)
            change = analyze_change_rules(change_text)
            chunks = parse_specification(specification_path, specification_path.stem)
            cases = parse_testcases(testcase_path)
            candidates = select_candidates(change, cases, int(self.settings.get("retrieval.candidate_limit", 150)))
            query = " ".join(change.changed_features + change.risk_keywords + [change.purpose])
            relevant_chunks = [chunk for chunk, _ in BM25Retriever(chunks, lambda item: f"{item.heading} {item.text}").search(query, int(self.settings.get("retrieval.specification_top_k", 8)))]
            decisions = self.gemini.analyze(change, candidates, relevant_chunks)
            decisions = validate_decisions(decisions, cases, relevant_chunks, float(self.settings.get("analysis.recommended_confidence", .8)), float(self.settings.get("analysis.review_confidence", .6)))
            result = AnalysisResult(analysis_id=analysis_id, created_at=datetime.now(timezone.utc), change_file=change_path.name, specification_file=specification_path.name, testcase_file=testcase_path.name, change=change, total_tc=len(cases), candidate_tc=len(candidates), decisions=decisions)
            result.report_path = create_html_report(result)
            create_csv_export(result)
            self.logger.info("analysis_finished id=%s requests=%s manual_review=%s elapsed=%.3f", analysis_id, self.gemini.request_count, sum(item.manual_review_required for item in decisions), time.monotonic() - started)
            return result
        except Exception as exc:
            self.logger.exception("analysis_failed id=%s error_type=%s elapsed=%.3f", analysis_id, type(exc).__name__, time.monotonic() - started)
            raise
