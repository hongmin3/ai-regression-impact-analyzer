from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.scheduler import start_scheduler, stop_scheduler
from app.web.routes import router, storage

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    storage.fail_incomplete_analyses()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title=settings.get("app.name"), version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=settings.root / "app" / "web" / "static"), name="static")
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
