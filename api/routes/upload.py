"""Handle CSV file uploads and run detection on uploaded data."""

from __future__ import annotations

import tempfile
import subprocess
import sys
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File

router = APIRouter(tags=["upload"])

ROOT = Path(__file__).resolve().parents[2]


@router.post("/upload")
async def upload_and_analyse(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only CSV files are accepted.")
    contents = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, dir=str(ROOT / "outputs")) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        df = pd.read_csv(tmp_path)
        required = {"trade_id", "symbol", "timestamp", "price", "quantity", "side"}
        missing = required - set(df.columns)
        if missing:
            raise HTTPException(
                400,
                f"CSV missing required columns: {missing}. "
                f"Expected: {sorted(required)}. Got: {sorted(df.columns)}",
            )
        result = subprocess.run(
            [sys.executable, str(ROOT / "run.py"), "p3"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        sub_path = ROOT / "outputs" / "submission.csv"
        if sub_path.exists():
            flags = pd.read_csv(sub_path)
            return {
                "uploaded_rows": len(df),
                "flags_found": len(flags),
                "flags": flags.fillna("").to_dict(orient="records"),
                "stdout": result.stdout,
            }
        return {
            "uploaded_rows": len(df),
            "flags_found": 0,
            "flags": [],
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    finally:
        Path(tmp_path).unlink(missing_ok=True)
