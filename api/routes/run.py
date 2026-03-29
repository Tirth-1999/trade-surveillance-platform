"""Trigger pipeline runs via subprocess."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["run"])

ROOT = Path(__file__).resolve().parents[2]

ALLOWED_PIPELINES = {
    "p1", "p2", "p3", "ground-truth", "compare",
    "reranker", "committee", "tune", "all",
}


@router.post("/run/{pipeline}")
def run_pipeline(pipeline: str):
    if pipeline not in ALLOWED_PIPELINES:
        raise HTTPException(400, f"Unknown pipeline: {pipeline}")
    t0 = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(ROOT / "run.py"), pipeline],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=600,
    )
    elapsed = time.perf_counter() - t0
    return {
        "pipeline": pipeline,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "elapsed_sec": round(elapsed, 2),
    }
