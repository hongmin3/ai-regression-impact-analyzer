"""여러 modules/* 의 라우터를 하나의 FastAPI 앱에 취합한다. 이 파일 자체는 비즈니스
로직을 갖지 않는다 — 어떤 모듈이 어떤 URL prefix를 쓰는지만 결정한다."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.modules.cost_dashboard.router import router as cost_dashboard_router
from app.modules.impact_analyzer.router import router as impact_analyzer_router
from app.modules.knowledge.router import router as knowledge_router
from app.modules.manual_review.router import router as manual_review_router


templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def external_services() -> list[dict[str, str]]:
    """config.yaml `services.*` 중 URL이 설정된 하위 서비스만 허브 카드로 노출한다.

    핵심 앱과 같은 프로세스에서 뜨지 않는 별도 배포 단위(예: services/qa-manual-hub)를
    링크로만 연결한다. URL이 비어 있으면 카드를 만들지 않으므로, 하위 서비스를
    배포하지 않은 환경에서는 깨진 링크가 노출되지 않는다."""
    configured = get_settings().get("services") or {}
    cards: list[dict[str, str]] = []
    for key, value in configured.items():
        if not isinstance(value, dict):
            continue
        url = str(value.get("url") or "").strip()
        if not url:
            continue
        cards.append(
            {
                "key": key,
                "name": str(value.get("name") or key),
                "description": str(value.get("description") or ""),
                "url": url,
            }
        )
    return cards


def hub(request: Request):
    """QA 자동화 기능을 선택하는 공용 진입점."""
    return templates.TemplateResponse(
        request, "hub.html", {"external_services": external_services()}
    )


def build_router() -> APIRouter:
    api = APIRouter()
    api.add_api_route("/", hub, methods=["GET"], response_class=HTMLResponse, name="hub")
    api.include_router(knowledge_router)
    api.include_router(impact_analyzer_router)
    api.include_router(manual_review_router, prefix="/manual-review")
    api.include_router(cost_dashboard_router)
    return api
