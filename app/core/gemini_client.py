from __future__ import annotations

import hashlib
import json
from collections.abc import Callable

from google import genai
from google.genai import types
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.schemas import ChangeAnalysis, DraftTestCase, GeminiAnalysisResponse, ImpactDecision, SpecificationChunk, TestCase
from app.core.storage import Storage

SYSTEM_INSTRUCTION = """당신은 QA Regression Semantic Decision Engine이다.
제공된 TC ID와 Specification chunk ID만 사용한다. 존재하지 않는 ID나 근거를 만들지 않는다.
확인할 수 없으면 confidence를 낮추고 manual_review_required=true로 반환한다.
제공된 Context 범위 밖의 내용을 추측하지 않는다. 반드시 JSON Schema를 준수한다.

change.user_notes는 사용자가 이번 분석을 위해 직접 입력한 요청·설명이다. VXvue TC 가이드 Rev.1.7 §1
정보 우선순위에 따라 문서에서 자동 추출한 changed_features보다 user_notes를 최우선 근거로 판단한다.
user_notes와 문서 근거가 충돌하면 user_notes를 따르되 reason에 문서와의 차이를 명시한다.

evidence_level은 다음 기준으로만 판단한다 (VXvue TC 가이드 Rev.1.7 §7):
- EXPLICIT: 제공된 specifications에 기능/조건/동작/결과가 직접 명시되어 relevant_specifications로 인용 가능
- EXPLICIT_CANDIDATE: 관련 문장은 있으나 직접 근거로 단정하기 부족
- DELETED_HISTORY: 제공된 specifications 문장이 삭제/폐지/교체 이력으로 보임
- EXISTING_BEHAVIOR: TC 자체의 기존 검증 목적에서만 확인되고 specifications 근거는 없음
- INFERRED: 직접 근거 없이 추론한 경우 (기본값)
relevant_specifications가 비어 있으면 EXPLICIT을 쓰지 않는다.
revision_mark는 원본 PDF의 취소선/밑줄 서식을 확인한 적이 없으므로 항상 UNVERIFIED로 두고,
문장 자체에 명시적인 삭제/폐지 표현이 전혀 없을 때만 NONE_DETECTED를 쓴다.

changed_features 중 제공된 test_cases 어디에서도 검증하지 않는 항목이 있으면 draft_test_cases에 초안을 추가한다.
이미 어떤 test_case가 다루고 있는 changed_feature는 draft_test_cases에 넣지 않는다.
draft_test_cases의 각 필드는 changed_feature 원문이나 제공된 specifications 근거로만 채우고,
근거가 없는 필드는 반드시 문자열 "확인 필요"만 쓴다. 팝업 문구, UI 위치, 예외 동작 등을 임의로 만들지 않는다.
evidence_chunk_ids에는 제공된 specifications의 chunk_id만 사용한다."""


class GeminiClient:
    def __init__(self, storage: Storage | None = None, responder: Callable[[str], dict] | None = None) -> None:
        self.settings = get_settings()
        self.storage = storage or Storage()
        self.responder = responder
        self.request_count = 0
        self.token_usage: dict[str, int] = {}
        self.draft_test_cases: list[DraftTestCase] = []

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
                response_schema=GeminiAnalysisResponse,
                temperature=0.1,
            ),
        )
        usage = getattr(response, "usage_metadata", None)
        token_usage = {
            "prompt_tokens": int(getattr(usage, "prompt_token_count", 0) or 0),
            "candidate_tokens": int(getattr(usage, "candidates_token_count", 0) or 0),
            "total_tokens": int(getattr(usage, "total_token_count", 0) or 0),
        }
        payload = json.loads(response.text or "{}")
        return {"decisions": payload.get("decisions", []), "draft_test_cases": payload.get("draft_test_cases", []), "token_usage": token_usage}

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
        self.token_usage = {key: int(value) for key, value in raw.get("token_usage", {}).items()}
        values = raw.get("decisions", raw if isinstance(raw, list) else [])
        self.draft_test_cases = [DraftTestCase.model_validate(item) for item in raw.get("draft_test_cases", [])]
        return [ImpactDecision.model_validate(item) for item in values]
