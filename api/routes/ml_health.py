"""Expose staged ML artifact metadata for dashboard health."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from bits_hackathon.core.paths import ARTIFACTS_DIR, OUTPUTS_DIR

router = APIRouter(tags=["ml"])


def _read_json(p: Path) -> dict | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


@router.get("/ml/health")
def ml_health():
    stage1 = _read_json(ARTIFACTS_DIR / "stage1_meta.json")
    stage2 = _read_json(ARTIFACTS_DIR / "stage2_meta.json")
    prior = _read_json(ARTIFACTS_DIR / "stage1_meta_previous.json")
    eval_path = OUTPUTS_DIR / "ml_evaluation_report.txt"
    evaluation_snippet = eval_path.read_text()[:2000] if eval_path.exists() else None
    return {
        "artifacts_dir": str(ARTIFACTS_DIR),
        "stage1": stage1,
        "stage2": stage2,
        "stage1_previous": prior,
        "evaluation_report_preview": evaluation_snippet,
        "artifacts_present": {
            "stage1": (ARTIFACTS_DIR / "stage1_model.joblib").exists(),
            "stage2": bool(
                stage2 is not None
                and not stage2.get("skipped", False)
                and (ARTIFACTS_DIR / "stage2_model.joblib").exists()
            ),
        },
    }
