import datetime
import time
import uuid
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import configure_logging, get_logger
from app.core.security import get_client_ip
from app.services.auth import (
    WebAuthRedirect,
    WebForbiddenError,
    default_home_for_user,
    ensure_default_admin,
)
from app.services.storage import storage_service

configure_logging()
logger = get_logger("main")
from app.routers.api_speakers import router as api_speakers_router
from app.routers.api_sessions import router as api_sessions_router
from app.routers.api_prompts import router as api_prompts_router
from app.routers.api_recordings import router as api_recordings_router
from app.routers.api_transcriptions import router as api_transcriptions_router
from app.routers.api_segmentation import router as api_segmentation_router
from app.routers.api_export import router as api_export_router
from app.routers.api_public import router as api_public_router
from app.routers.web import templates as web_templates, web_router


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


@app.exception_handler(WebForbiddenError)
async def web_forbidden_handler(request: Request, exc: WebForbiddenError):
    return web_templates.TemplateResponse(
        request=request,
        name="403.html",
        context={
            "current_user": exc.user,
            "detail": exc.detail,
            "home_url": default_home_for_user(exc.user),
        },
        status_code=403,
    )


@app.middleware("http")
async def add_security_headers_and_request_logging(request: Request, call_next):
    req_id = uuid.uuid4().hex[:12]
    t0 = time.perf_counter()
    ip = get_client_ip(request)
    try:
        response = await call_next(request)
    except Exception:
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        logger.exception(
            "Unhandled server error on %s %s",
            request.method,
            request.url.path,
            extra={
                "request_id": req_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": 500,
                "duration_ms": dur_ms,
                "ip": ip,
            },
        )
        raise

    dur_ms = round((time.perf_counter() - t0) * 1000, 1)
    response.headers.setdefault("X-Request-ID", req_id)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=(), microphone=(self)")

    if not request.url.path.startswith("/static/"):
        log_fn = logger.warning if response.status_code >= 400 else logger.info
        log_fn(
            "%s %s -> %s (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            dur_ms,
            extra={
                "request_id": req_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": dur_ms,
                "ip": ip,
            },
        )
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


def _public_base_url(request: Request) -> str:
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "https").split(",")[0].strip()
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}".rstrip("/")


@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
def robots_txt(request: Request):
    base = _public_base_url(request)
    lines = [
        "User-agent: *",
        "Allow: /",
        "Allow: /contribuer",
        "Allow: /confidentialite",
        "Disallow: /api/",
        "Disallow: /admin/",
        "Disallow: /dashboard",
        "Disallow: /login",
        "Disallow: /logout",
        "Disallow: /record",
        "Disallow: /speakers",
        "Disallow: /sessions",
        "Disallow: /prompts",
        "Disallow: /recordings",
        "Disallow: /transcriptions",
        f"Sitemap: {base}/sitemap.xml",
    ]
    return "\n".join(lines) + "\n"


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml(request: Request):
    base = _public_base_url(request)
    today = datetime.date.today().isoformat()
    urls = [
        (f"{base}/", "1.0", "weekly"),
        (f"{base}/contribuer", "0.9", "weekly"),
        (f"{base}/confidentialite", "0.4", "monthly"),
    ]
    entries = "\n".join(
        f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>{freq}</changefreq>\n    <priority>{prio}</priority>\n  </url>"
        for loc, prio, freq in urls
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</urlset>\n"
    )
    return Response(content=xml, media_type="application/xml")


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
