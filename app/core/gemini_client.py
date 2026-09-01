from __future__ import annotations

import hashlib
import json
from collections.abc import Callable

from google import genai
from google.genai import types
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.prompt_manager import load_prompt
from app.core.storage import Storage


class GeminiClient:
    """도메인 무관 Gemini 구조화 호출 클라이언트. 어떤 모듈의 Pydantic 스키마인지, 어떤
    system_instruction을 쓰는지는 전혀 모른다 — 호출자가 prompt_name(→prompts/*.yaml)과
    response_schema를 그때그때 넘긴다. 캐시/재시도/토큰 사용량 추적만 여기서 담당한다."""

    def __init__(self, storage: Storage | None = None, responder: Callable[[str], dict] | None = None) -> None:
        self.settings = get_settings()
        self.storage = storage or Storage()
        self.responder = responder
        self.request_count = 0
        self.token_usage: dict[str, int] = {}
        self.last_cache_hit = False

    @retry(retry=retry_if_exception_type((TimeoutError, ConnectionError)), stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
    def _request(self, prompt: str, *, system_instruction: str, response_schema: type[BaseModel], temperature: float, max_output_tokens: int, thinking_budget: int) -> dict:
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
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=temperature,
                # 후보가 많으면 응답 JSON이 커서 기본 한도에 잘릴 수 있어 명시적으로 올린다.
                max_output_tokens=max_output_tokens,
                # Gemini 2.5의 내부 thinking 토큰이 max_output_tokens 예산을 함께 소비해 JSON이 잘리는
                # 문제가 있었다. 구조화된 추출 작업이라 별도 추론 과정이 필요 없으므로 비활성화한다.
                thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
            ),
        )
        usage = getattr(response, "usage_metadata", None)
        token_usage = {
            "prompt_tokens": int(getattr(usage, "prompt_token_count", 0) or 0),
            "candidate_tokens": int(getattr(usage, "candidates_token_count", 0) or 0),
            "total_tokens": int(getattr(usage, "total_token_count", 0) or 0),
        }
        finish_reason = getattr(getattr(response, "candidates", [None])[0], "finish_reason", None)
        try:
            payload = json.loads(response.text or "{}")
        except json.JSONDecodeError as exc:
            hint = " (MAX_TOKENS로 잘렸을 가능성이 높습니다 — retrieval.candidate_limit을 낮춰보세요.)" if str(finish_reason) == "MAX_TOKENS" else ""
            raise RuntimeError(f"Gemini 응답이 완전한 JSON이 아닙니다{hint}: {exc}") from exc
        payload["token_usage"] = token_usage
        return payload

    def generate_structured(self, prompt: str, *, prompt_name: str, response_schema: type[BaseModel]) -> dict:
        """prompt_name(prompts/{prompt_name}.yaml)의 system_instruction/생성 설정으로 Gemini를
        호출하고, 응답 JSON 전체를 dict로 반환한다 (도메인 파싱은 호출자 책임)."""
        prompt_cfg = load_prompt(prompt_name)
        cache_key = hashlib.sha256((self.settings.secrets.gemini_model + prompt_name + str(prompt_cfg.version) + prompt).encode()).hexdigest()
        cached = self.storage.cache_get(cache_key) if self.settings.get("analysis.cache_enabled", True) else None
        self.last_cache_hit = cached is not None
        raw = cached or self._request(
            prompt,
            system_instruction=prompt_cfg.system_instruction,
            response_schema=response_schema,
            temperature=prompt_cfg.temperature,
            max_output_tokens=prompt_cfg.max_output_tokens,
            thinking_budget=prompt_cfg.thinking_budget,
        )
        if not cached:
            self.storage.cache_set(cache_key, raw)
        self.token_usage = {key: int(value) for key, value in raw.get("token_usage", {}).items()}
        return raw
