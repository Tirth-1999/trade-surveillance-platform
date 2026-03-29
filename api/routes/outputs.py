"""Serve CSV output files as JSON arrays."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

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

# Pre-merged submission + trade tape (dashboard only; run sync_frontend_data.py)
ALLOWED_JSON = {
    "submission_with_trades": "submission_with_trades.json",
    "submission_committee_with_trades": "submission_committee_with_trades.json",
}


@router.get("/outputs/{name}")
def get_output(
    name: str,
    symbol: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
) -> list[dict[str, Any]] | Any:
    if name in ALLOWED_JSON:
        path = OUTPUTS_DIR / ALLOWED_JSON[name]
        if not path.exists():
            raise HTTPException(
                404,
                f"{ALLOWED_JSON[name]} not found. Run: python3 scripts/sync_frontend_data.py",
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return data
        if symbol:
            data = [r for r in data if r.get("symbol") == symbol]
        if limit:
            data = data[:limit]
        return data

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
