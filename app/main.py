from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.web.routes import router

settings = get_settings()
app = FastAPI(title=settings.get("app.name"), version="0.1.0")
app.mount("/static", StaticFiles(directory=settings.root / "app" / "web" / "static"), name="static")
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
