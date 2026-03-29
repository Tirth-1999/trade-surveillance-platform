"""HITL decision audit log -- read and write to decisions.jsonl."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["decisions"])

FEEDBACK_DIR = Path(__file__).resolve().parents[2] / "feedback"
FEEDBACK_DIR.mkdir(exist_ok=True)
DECISIONS_PATH = FEEDBACK_DIR / "decisions.jsonl"


class Decision(BaseModel):
    problem: str
    row_id: str
    action: str
    violation_type: str | None = None
    remarks: str | None = None


@router.post("/decisions")
def add_decision(decision: Decision):
    entry = decision.model_dump()
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(DECISIONS_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return {"status": "saved", "entry": entry}


@router.get("/decisions")
def get_decisions():
    if not DECISIONS_PATH.exists():
        return []
    entries = []
    for line in DECISIONS_PATH.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries
