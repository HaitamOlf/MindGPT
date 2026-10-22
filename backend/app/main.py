from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import chat, conversations, health, memory, profile, uploads, wellness

# Interactive docs/schema are disabled in production (recon-surface reduction, per the DAST
# pass) and re-enabled in local dev via ENABLE_API_DOCS=true.
app = FastAPI(
    title="MindGPT API",
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url="/redoc" if settings.enable_api_docs else None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
)


# Transport/response hardening applied at the app so it holds at the BUILD tier too, before
# any Front Door/WAF edge exists (docs/THREAT_MODEL.md Information disclosure; surfaced by the
# DAST pass in security/dast_probe.py). HSTS pins HTTPS; nosniff blocks MIME confusion;
# DENY stops this JSON API being framed; no-referrer avoids leaking URLs cross-origin.
_SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    for header, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response

# Pinned to an explicit allow-list — never a wildcard (docs/ARCHITECTURE.md §7.2, §10): the
# frontend origin(s) are named exactly (e.g. the Vercel production URL, plus localhost for
# dev). `*.vercel.app` is never allow-listed since any third party can deploy there.
# CORS_ALLOWED_ORIGIN is a comma-separated list; allow_credentials stays False — auth is a
# bearer JWT in the Authorization header, never a cookie.
_allowed_origins = [o.strip() for o in settings.cors_allowed_origin.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(profile.router)
app.include_router(memory.router)
app.include_router(wellness.router)
app.include_router(uploads.router)
