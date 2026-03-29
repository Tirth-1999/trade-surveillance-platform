"""Join submission CSVs to full trade tape for dashboard-only JSON (not for grading)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from bits_hackathon.core.crypto_load import load_all_trades
from bits_hackathon.core.paths import OUTPUTS_DIR


def _trade_frame(trades: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "trade_id",
        "timestamp",
        "wallet_id",
        "side",
        "order_type",
        "price",
        "quantity",
    ]
    if "notional_usdt" in trades.columns:
        cols.append("notional_usdt")
    use = [c for c in cols if c in trades.columns]
    t = trades[use].drop_duplicates(subset=["trade_id"], keep="last")
    if "wallet_id" in t.columns:
        t = t.copy()
        t["trader_id"] = t["wallet_id"]
    return t


def enrich_submission_file(csv_name: str, trades: pd.DataFrame) -> list[dict]:
    path = OUTPUTS_DIR / csv_name
    if not path.exists():
        return []
    sub = pd.read_csv(path)
    t = _trade_frame(trades)
    merged = sub.merge(t, on="trade_id", how="left")
    return merged.fillna("").to_dict(orient="records")


def write_submission_with_trades_json(out_dir: Path | None = None) -> dict[str, int]:
    """Write submission_with_trades.json and submission_committee_with_trades.json.

    Returns row counts per output file written.
    """
    root = out_dir or OUTPUTS_DIR
    root.mkdir(parents=True, exist_ok=True)
    trades = load_all_trades()
    counts: dict[str, int] = {}
    mapping = [
        ("submission.csv", "submission_with_trades.json"),
        ("submission_committee.csv", "submission_committee_with_trades.json"),
    ]
    for csv_name, json_name in mapping:
        rows = enrich_submission_file(csv_name, trades)
        (root / json_name).write_text(json.dumps(rows, default=str), encoding="utf-8")
        counts[json_name] = len(rows)
    return counts
