"""여러 modules/* 의 라우터를 하나의 FastAPI 앱에 취합한다. 이 파일 자체는 비즈니스
로직을 갖지 않는다 — 어떤 모듈이 어떤 URL prefix를 쓰는지만 결정한다."""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.impact_analyzer.router import router as impact_analyzer_router
from app.modules.manual_review.router import router as manual_review_router


def build_router() -> APIRouter:
    api = APIRouter()
    api.include_router(impact_analyzer_router)  # prefix 없음 — 기존 URL(/, /analyses, /knowledge 등) 그대로 유지
    api.include_router(manual_review_router, prefix="/manual-review")
    return api
