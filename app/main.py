import datetime
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.auth import WebAuthRedirect, ensure_default_admin
from app.services.storage import storage_service
from app.routers.api_speakers import router as api_speakers_router
from app.routers.api_sessions import router as api_sessions_router
from app.routers.api_prompts import router as api_prompts_router
from app.routers.api_recordings import router as api_recordings_router
from app.routers.api_transcriptions import router as api_transcriptions_router
from app.routers.api_segmentation import router as api_segmentation_router
from app.routers.api_export import router as api_export_router
from app.routers.api_public import router as api_public_router
from app.routers.web import web_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[ALORA Application] Starting up ({settings.APP_NAME})...")
    storage_service.ensure_bucket_exists()
    db = SessionLocal()
    try:
        ensure_default_admin(db)
    except Exception as e:
        print(f"[ALORA Startup Warning] Could not bootstrap default admin: {e}")
    finally:
        db.close()
    yield
    print("[ALORA Application] Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    description="Automatic Learning for Oral Resource-poor African Languages — Susu Oral Corpus Platform",
    version="0.4.0",
    lifespan=lifespan,
)


@app.exception_handler(WebAuthRedirect)
async def web_auth_redirect_handler(request: Request, exc: WebAuthRedirect):
    safe_next = quote(exc.next_url or "/dashboard", safe="/?=&")
    return RedirectResponse(url=f"/login?next={safe_next}", status_code=303)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=(), microphone=(self)")
    return response


app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="app/templates")

app.include_router(api_public_router)
app.include_router(api_speakers_router)
app.include_router(api_sessions_router)
app.include_router(api_prompts_router)
app.include_router(api_recordings_router)
app.include_router(api_transcriptions_router)
app.include_router(api_segmentation_router)
app.include_router(api_export_router)
app.include_router(web_router)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return RedirectResponse(url="/static/img/alora-icon.png", status_code=302)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
