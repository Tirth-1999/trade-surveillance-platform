"""FastAPI backend for the Trade Surveillance dashboard."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import outputs, reports, run, upload, status, decisions

app = FastAPI(title="Trade Surveillance API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(outputs.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(run.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(status.router, prefix="/api")
app.include_router(decisions.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
