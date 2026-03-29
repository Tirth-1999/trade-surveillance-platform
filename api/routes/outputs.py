"""Serve CSV output files as JSON arrays."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["outputs"])

OUTPUTS_DIR = Path(__file__).resolve().parents[2] / "outputs"

ALLOWED_FILES = {
    "submission": "submission.csv",
    "submission_committee": "submission_committee.csv",
    "submission_ml": "submission_ml.csv",
    "ground_truth": "ground_truth.csv",
    "comparison_report": "comparison_report.csv",
    "p1_alerts": "p1_alerts.csv",
    "p2_signals": "p2_signals.csv",
}


@router.get("/outputs/{name}")
def get_output(
    name: str,
    symbol: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
):
    if name not in ALLOWED_FILES:
        raise HTTPException(404, f"Unknown output: {name}")
    path = OUTPUTS_DIR / ALLOWED_FILES[name]
    if not path.exists():
        raise HTTPException(404, f"{ALLOWED_FILES[name]} not found. Run the pipeline first.")
    df = pd.read_csv(path)
    if symbol and "symbol" in df.columns:
        df = df[df["symbol"] == symbol]
    if limit:
        df = df.head(limit)
    return df.fillna("").to_dict(orient="records")
