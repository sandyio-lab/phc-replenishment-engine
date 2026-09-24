"""
PHC Supply Chain Backend — FastAPI Application Entry Point
==========================================================
Start the server:
    uvicorn app.main:app --reload --port 8000

API docs auto-generated at:
    http://localhost:8000/docs   (Swagger UI)
    http://localhost:8000/redoc  (ReDoc)
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import engine, Base
from app.routes        import phcs, inventory, vendors, orders, analytics, ai

load_dotenv()
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_ROOT.parent
load_dotenv(_REPO_ROOT / "ai_integration" / ".env")

# ─────────────────────────────────────────────────────────────────────────────
# Lifespan — runs on startup / shutdown
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables on startup (safe if they already exist)
    try:
        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError:
        # Vercel's deployment filesystem is read-only; the API can still start
        # when a persistent database is not configured.
        pass
    yield
    # Nothing to clean up on shutdown for now


# ─────────────────────────────────────────────────────────────────────────────
# App initialisation
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "PHC Supply Chain API",
    description = (
        "Backend 1 — Core API & Business Logic for the Autonomous PHC Medicine "
        "Replenishment & Supply Chain Resilience Engine. "
        "Hackathon: Build with AI: Code for Communities (Google Cloud, 2026)."
    ),
    version     = "1.0.0",
    lifespan    = lifespan,
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

# ─────────────────────────────────────────────────────────────────────────────
# CORS — allow the two frontend apps + local dev
# ─────────────────────────────────────────────────────────────────────────────

_raw_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:8000",
)
cors_origins  = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins     = cors_origins,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────────────────────

API_V1 = "/api/v1"

app.include_router(phcs.router,       prefix=API_V1)
app.include_router(inventory.router,  prefix=API_V1)
app.include_router(vendors.router,    prefix=API_V1)
app.include_router(orders.router,     prefix=API_V1)
app.include_router(analytics.router,  prefix=API_V1)
app.include_router(ai.router,          prefix=API_V1)

# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health_check():
    """Liveness probe — returns 200 if the server is running."""
    return {"status": "ok", "service": "phc-backend"}


@app.get("/", tags=["Health"])
def root():
    return FileResponse(_REPO_ROOT / "merge.html")


@app.get("/worker", include_in_schema=False)
def worker_app():
    return FileResponse(_BACKEND_ROOT / "index.html", media_type="text/html")


# Keep any local worker assets available without relying on Render's working directory.
app.mount(
    "/worker-assets",
    StaticFiles(directory=_BACKEND_ROOT),
    name="worker-assets",
)