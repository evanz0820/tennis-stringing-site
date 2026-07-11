"""Vercel serverless entrypoint.

Vercel's Python runtime serves the ASGI object named ``app`` in this file. The
backend package lives in ``backend/app`` (bundled into the function via the
``includeFiles`` glob in vercel.json), so we add ``backend`` to sys.path and
import the real app, then mount it under ``/api`` so requests to ``/api/...`` on
the same domain as the static frontend reach the backend with the prefix
stripped (mount forwards ``/api/jobs`` to the app as ``/jobs``).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))

from fastapi import FastAPI  # noqa: E402
from app.main import app as backend_app  # noqa: E402

app = FastAPI()
app.mount("/api", backend_app)
