from __future__ import annotations

import json
from collections.abc import Callable

from app.core.gemini_client import GeminiClient
from app.core.prompt_manager import load_prompt
from app.core.storage import Storage
from app.modules.impact_analyzer.schemas import ChangeAnalysis, ChangeItem, DraftTestCase, GeminiAnalysisResponse, ImpactDecision, SpecificationChunk, TestCase

PROMPT_NAME = "impact_analysis"


class ImpactAnalysisAIClient:
    """impact_analyzer 모듈의 도메인 전용 AI 호출 wrapper. core.GeminiClient를 감싸서
    payload 조립과 응답 파싱(ImpactDecision/DraftTestCase/ChangeItem)만 담당한다."""

    def __init__(self, storage: Storage | None = None, responder: Callable[[str], dict] | None = None) -> None:
        self._client = GeminiClient(storage=storage, responder=responder)
        self.draft_test_cases: list[DraftTestCase] = []
        self.change_items: list[ChangeItem] = []

    @property
    def request_count(self) -> int:
        return self._client.request_count

    @property
    def token_usage(self) -> dict:
        return self._client.token_usage

    @property
    def prompt_version(self) -> int:
        return load_prompt(PROMPT_NAME).version

    def analyze(self, change: ChangeAnalysis, cases: list[TestCase], chunks: list[SpecificationChunk]) -> list[ImpactDecision]:
        payload = {
            "change": change.model_dump(),
            "test_cases": [case.model_dump() for case in cases],
            "specifications": [chunk.model_dump() for chunk in chunks],
        }
        prompt = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        raw = self._client.generate_structured(prompt, prompt_name=PROMPT_NAME, response_schema=GeminiAnalysisResponse)
        self.draft_test_cases = [DraftTestCase.model_validate(item) for item in raw.get("draft_test_cases", [])]
        self.change_items = [ChangeItem.model_validate(item) for item in raw.get("change_items", [])]
        return [ImpactDecision.model_validate(item) for item in raw.get("decisions", [])]
