import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.services.storage import storage_service
from app.routers.api_speakers import router as api_speakers_router
from app.routers.api_sessions import router as api_sessions_router
from app.routers.api_prompts import router as api_prompts_router
from app.routers.api_recordings import router as api_recordings_router
from app.routers.api_transcriptions import router as api_transcriptions_router
from app.routers.api_segmentation import router as api_segmentation_router
from app.routers.web import web_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[ALORA Application] Starting up ({settings.APP_NAME})...")
    storage_service.ensure_bucket_exists()
    yield
    print("[ALORA Application] Shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    description="Automatic Learning for Oral Resource-poor African Languages — Susu Oral Corpus Platform",
    version="0.1.0",
    lifespan=lifespan
)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="app/templates")

app.include_router(api_speakers_router)
app.include_router(api_sessions_router)
app.include_router(api_prompts_router)
app.include_router(api_recordings_router)
app.include_router(api_transcriptions_router)
app.include_router(api_segmentation_router)
app.include_router(web_router)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
