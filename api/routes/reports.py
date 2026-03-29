"""Serve text report files."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["reports"])

OUTPUTS_DIR = Path(__file__).resolve().parents[2] / "outputs"

ALLOWED_REPORTS = {
    "committee_report": "committee_report.txt",
    "reranker_report": "reranker_report.txt",
    "tuning_report": "tuning_report.txt",
}


@router.get("/reports/{name}")
def get_report(name: str):
    if name not in ALLOWED_REPORTS:
        raise HTTPException(404, f"Unknown report: {name}")
    path = OUTPUTS_DIR / ALLOWED_REPORTS[name]
    if not path.exists():
        raise HTTPException(404, f"{ALLOWED_REPORTS[name]} not found.")
    return {"text": path.read_text()}
