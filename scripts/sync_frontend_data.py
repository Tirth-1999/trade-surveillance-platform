#!/usr/bin/env python3
"""Regenerate frontend/public/data/*.json from outputs/ and artifacts/ for local/Vercel static fallback.

Run after: train-ml, committee, or any output refresh.
  python3 scripts/sync_frontend_data.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from bits_hackathon.core.paths import ARTIFACTS_DIR, OUTPUTS_DIR
from bits_hackathon.pipeline.ui_submission_enrichment import write_submission_with_trades_json

PUB = ROOT / "frontend" / "public" / "data"
PUB.mkdir(parents=True, exist_ok=True)

UI_JSON = [
    "submission_with_trades.json",
    "submission_committee_with_trades.json",
]


def main() -> None:
    out = OUTPUTS_DIR
    pub = PUB

    print("  (enriching submissions with trade tape for UI)")
    try:
        counts = write_submission_with_trades_json(out)
        for jname, n in counts.items():
            print(f"  {jname} ({n} rows)")
    except Exception as e:
        print(f"  warning: submission UI enrichment skipped: {e}", file=sys.stderr)

    csv_map = {
        "submission": "submission.csv",
        "submission_committee": "submission_committee.csv",
        "submission_ml": "submission_ml.csv",
        "ground_truth": "ground_truth.csv",
        "comparison_report": "comparison_report.csv",
        "p1_alerts": "p1_alerts.csv",
        "p2_signals": "p2_signals.csv",
    }
    for key, fname in csv_map.items():
        p = out / fname
        if p.exists():
            df = pd.read_csv(p).fillna("")
            (pub / f"{key}.json").write_text(json.dumps(df.to_dict(orient="records"), default=str))
            print(f"  {key}.json ({len(df)} rows)")

    txt_map = {
        "committee_report": "committee_report.txt",
        "reranker_report": "reranker_report.txt",
        "tuning_report": "tuning_report.txt",
    }
    for key, fname in txt_map.items():
        p = out / fname
        if p.exists():
            (pub / f"{key}.json").write_text(json.dumps({"text": p.read_text()}))
            print(f"  {key}.json")

    for jname in UI_JSON:
        p = out / jname
        if p.exists():
            (pub / jname).write_text(p.read_text(encoding="utf-8"))
            print(f"  {jname} (copied)")

    # status.json
    import datetime

    expected = list(csv_map.values()) + list(txt_map.values()) + UI_JSON
    status = []
    for name in expected:
        p = out / name
        if p.exists():
            st = p.stat()
            rc = None
            if name.endswith(".csv"):
                rc = sum(1 for _ in open(p, encoding="utf-8")) - 1
            status.append(
                {
                    "name": name,
                    "exists": True,
                    "size_bytes": st.st_size,
                    "row_count": rc,
                    "last_modified": datetime.datetime.fromtimestamp(
                        st.st_mtime, tz=datetime.timezone.utc
                    ).isoformat(),
                }
            )
        else:
            status.append(
                {
                    "name": name,
                    "exists": False,
                    "size_bytes": 0,
                    "row_count": None,
                    "last_modified": None,
                }
            )
    (pub / "status.json").write_text(json.dumps(status, default=str))
    print("  status.json")

    # ml_health.json (mirror api/routes/ml_health.py)
    def _read_json(p: Path) -> dict | None:
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            return None

    stage1 = _read_json(ARTIFACTS_DIR / "stage1_meta.json")
    stage2 = _read_json(ARTIFACTS_DIR / "stage2_meta.json")
    prior = _read_json(ARTIFACTS_DIR / "stage1_meta_previous.json")
    eval_path = out / "ml_evaluation_report.txt"
    evaluation_snippet = eval_path.read_text(encoding="utf-8")[:2000] if eval_path.exists() else None
    ml_health = {
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
    (pub / "ml_health.json").write_text(json.dumps(ml_health, indent=2, default=str))
    print("  ml_health.json")

    dec = pub / "decisions.json"
    if not dec.exists():
        dec.write_text("[]")
    print("\nDone:", pub)


if __name__ == "__main__":
    main()
