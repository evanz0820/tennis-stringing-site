"""Vercel serverless entrypoint.

Vercel's Python runtime serves the ASGI object named ``app`` in this file. We
wrap the real FastAPI app and mount it under ``/api`` so that, on the same domain
as the static frontend, requests to ``/api/...`` reach the backend with the
prefix stripped (mount forwards ``/api/jobs`` to the app as ``/jobs``).
"""
import os
import sys

# Make the backend package (repo_root/backend/app) importable.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi import FastAPI  # noqa: E402
from app.main import app as backend_app  # noqa: E402

app = FastAPI()
app.mount("/api", backend_app)
