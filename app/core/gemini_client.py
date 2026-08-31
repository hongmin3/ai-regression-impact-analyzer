from __future__ import annotations

import hashlib
import json
from collections.abc import Callable

from google import genai
from google.genai import types
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.schemas import ChangeAnalysis, ImpactDecision, SpecificationChunk, TestCase
from app.core.storage import Storage

SYSTEM_INSTRUCTION = """당신은 QA Regression Semantic Decision Engine이다.
제공된 TC ID와 Specification chunk ID만 사용한다. 존재하지 않는 ID나 근거를 만들지 않는다.
확인할 수 없으면 confidence를 낮추고 manual_review_required=true로 반환한다.
제공된 Context 범위 밖의 내용을 추측하지 않는다. 반드시 JSON Schema를 준수한다."""


class GeminiClient:
    def __init__(self, storage: Storage | None = None, responder: Callable[[str], dict] | None = None) -> None:
        self.settings = get_settings()
        self.storage = storage or Storage()
        self.responder = responder
        self.request_count = 0

    @retry(retry=retry_if_exception_type((TimeoutError, ConnectionError)), stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
    def _request(self, prompt: str) -> dict:
        self.request_count += 1
        if self.responder:
            return self.responder(prompt)
        if not self.settings.secrets.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY가 설정되지 않았습니다.")
        client = genai.Client(api_key=self.settings.secrets.gemini_api_key)
        response = client.models.generate_content(
            model=self.settings.secrets.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=list[ImpactDecision],
                temperature=0.1,
            ),
        )
        return {"decisions": json.loads(response.text or "[]")}

    def analyze(self, change: ChangeAnalysis, cases: list[TestCase], chunks: list[SpecificationChunk]) -> list[ImpactDecision]:
        payload = {
            "change": change.model_dump(),
            "test_cases": [case.model_dump() for case in cases],
            "specifications": [chunk.model_dump() for chunk in chunks],
        }
        prompt = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        cache_key = hashlib.sha256((self.settings.secrets.gemini_model + prompt).encode()).hexdigest()
        cached = self.storage.cache_get(cache_key) if self.settings.get("analysis.cache_enabled", True) else None
        raw = cached or self._request(prompt)
        if not cached:
            self.storage.cache_set(cache_key, raw)
        values = raw.get("decisions", raw if isinstance(raw, list) else [])
        return [ImpactDecision.model_validate(item) for item in values]
