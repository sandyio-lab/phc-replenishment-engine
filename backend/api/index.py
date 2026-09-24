"""Vercel serverless entry point for the FastAPI application."""

import sys
from pathlib import Path


_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.main import app

__all__ = ["app"]
