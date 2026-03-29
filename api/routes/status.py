"""Pipeline output status: which files exist, row counts, timestamps."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(tags=["status"])

OUTPUTS_DIR = Path(__file__).resolve().parents[2] / "outputs"

EXPECTED_FILES = [
    "submission.csv",
    "submission_committee.csv",
    "submission_ml.csv",
    "ground_truth.csv",
    "comparison_report.csv",
    "p1_alerts.csv",
    "p2_signals.csv",
    "committee_report.txt",
    "reranker_report.txt",
    "tuning_report.txt",
]


@router.get("/status")
def get_status():
    files = []
    for name in EXPECTED_FILES:
        path = OUTPUTS_DIR / name
        if path.exists():
            stat = path.stat()
            row_count = None
            if name.endswith(".csv"):
                with open(path) as f:
                    row_count = sum(1 for _ in f) - 1
            files.append({
                "name": name,
                "exists": True,
                "size_bytes": stat.st_size,
                "row_count": row_count,
                "last_modified": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
            })
        else:
            files.append({
                "name": name,
                "exists": False,
                "size_bytes": 0,
                "row_count": None,
                "last_modified": None,
            })
    return files
