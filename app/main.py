import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.core.config import settings
from app.services.storage import storage_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    print(f"[ALORA Application] Starting up ({settings.APP_NAME})...")
    storage_service.ensure_bucket_exists()
    yield
    # Shutdown actions
    print("[ALORA Application] Shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    description="Automatic Learning for Oral Resource-poor African Languages — Susu Oral Corpus Platform",
    version="0.1.0",
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure Jinja2 templates
templates = Jinja2Templates(directory="app/templates")

@app.middleware("http")
async def add_current_year(request: Request, call_next):
    response = await call_next(request)
    return response

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
