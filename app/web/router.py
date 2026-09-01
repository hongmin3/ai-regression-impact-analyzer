"""여러 modules/* 의 라우터를 하나의 FastAPI 앱에 취합한다. 이 파일 자체는 비즈니스
로직을 갖지 않는다 — 어떤 모듈이 어떤 URL prefix를 쓰는지만 결정한다."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.modules.impact_analyzer.router import router as impact_analyzer_router
from app.modules.manual_review.router import router as manual_review_router


templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def hub(request: Request):
    """QA 자동화 기능을 선택하는 공용 진입점."""
    return templates.TemplateResponse(request, "hub.html")


def build_router() -> APIRouter:
    api = APIRouter()
    api.add_api_route("/", hub, methods=["GET"], response_class=HTMLResponse, name="hub")
    api.include_router(impact_analyzer_router)
    api.include_router(manual_review_router, prefix="/manual-review")
    return api
