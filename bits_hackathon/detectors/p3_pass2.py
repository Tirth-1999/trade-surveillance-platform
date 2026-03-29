"""Pass 2: re-verify each candidate row against detector logic (CSV schema unchanged).

- peg_break / spoofing: stricter thresholds from config (multipliers on Pass 1).
- Other types: trade_id must appear in the corresponding detector output for that violation_type.

Drops rows that fail confirmation; optional audit CSV lists kept vs dropped.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bits_hackathon.core.config import get as cfg
from bits_hackathon.core.paths import OUTPUTS_DIR
from bits_hackathon.core.violation_taxonomy import normalize_violation_type

from .p3_crypto import (
    detect_aml_structuring,
    detect_chain_layering,
    detect_coordinated_structuring,
    detect_layering_echo,
    detect_peg_break_usdc,
    detect_placement_smurfing,
    detect_price_bar_violation,
    detect_pump_dump_bars,
    detect_ramping,
    detect_round_trip_pairs,
    detect_threshold_testing,
    detect_usdc_wash_at_peg,
    detect_wash_same_wallet,
    detect_bat_volume_spike_trades,
)


def _spoofing_ids_strict(trades: pd.DataFrame, markets: pd.DataFrame) -> set[str]:
    m = float(cfg("p3.pass2.spoofing_bps_multiplier"))
    min_b = float(cfg("p3.price_bar_violation.min_mid_bps")) * m
    strict_b = float(cfg("p3.price_bar_violation.min_mid_bps_low_liquidity")) * m
    df = detect_price_bar_violation(trades, markets, min_mid_bps=min_b, min_mid_bps_low_liquidity=strict_b)
    return set(df["trade_id"].astype(str))


def _peg_ids_strict(trades: pd.DataFrame, markets: pd.DataFrame) -> set[str]:
    m = float(cfg("p3.pass2.peg_deviation_multiplier"))
    dev_pct = float(cfg("p3.peg_break.deviation_pct")) * m
    df = detect_peg_break_usdc(trades, markets, deviation_pct=dev_pct)
    return set(df["trade_id"].astype(str))


def _pump_dump_ids(trades: pd.DataFrame, markets: pd.DataFrame) -> set[str]:
    bat = detect_bat_volume_spike_trades(trades, markets)
    bars = detect_pump_dump_bars(trades, markets)
    return set(bat["trade_id"].astype(str)) | set(bars["trade_id"].astype(str))


def build_detector_id_sets(trades: pd.DataFrame, markets: pd.DataFrame) -> dict[str, set[str]]:
    """Maps normalized violation_type -> set of trade_ids that detector logic would emit."""
    return {
        "peg_break": _peg_ids_strict(trades, markets),
        "wash_volume_at_peg": set(detect_usdc_wash_at_peg(trades)["trade_id"].astype(str)),
        "wash_trading": set(detect_wash_same_wallet(trades)["trade_id"].astype(str)),
        "spoofing": _spoofing_ids_strict(trades, markets),
        "ramping": set(detect_ramping(trades)["trade_id"].astype(str)),
        "aml_structuring": set(detect_aml_structuring(trades)["trade_id"].astype(str)),
        "threshold_testing": set(detect_threshold_testing(trades)["trade_id"].astype(str)),
        "coordinated_structuring": set(detect_coordinated_structuring(trades)["trade_id"].astype(str)),
        "layering_echo": set(detect_layering_echo(trades)["trade_id"].astype(str)),
        "pump_and_dump": _pump_dump_ids(trades, markets),
        "chain_layering": set(detect_chain_layering(trades)["trade_id"].astype(str)),
        "placement_smurfing": set(detect_placement_smurfing(trades)["trade_id"].astype(str)),
        "round_trip_wash": set(detect_round_trip_pairs(trades)["trade_id"].astype(str)),
    }


def confirm_pass2(
    hits: pd.DataFrame,
    trades: pd.DataFrame,
    markets: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (confirmed_hits, audit_rows) where audit has columns:
    trade_id, violation_type, decision (kept|dropped), reason
    """
    if hits.empty:
        return hits, pd.DataFrame(
            columns=["trade_id", "violation_type", "decision", "reason"]
        )

    id_sets = build_detector_id_sets(trades, markets)
    audit_rows: list[dict] = []

    kept_idx: list[int] = []
    for idx, row in hits.iterrows():
        tid = str(row.get("trade_id", "")).strip()
        vtype = normalize_violation_type(str(row.get("violation_type", "")))
        if not tid or not vtype:
            audit_rows.append(
                {
                    "trade_id": tid,
                    "violation_type": vtype or "",
                    "decision": "dropped",
                    "reason": "empty_trade_id_or_type",
                }
            )
            continue
        allowed = id_sets.get(vtype)
        if allowed is None:
            audit_rows.append(
                {
                    "trade_id": tid,
                    "violation_type": vtype,
                    "decision": "dropped",
                    "reason": "unknown_violation_type",
                }
            )
            continue
        if tid in allowed:
            kept_idx.append(idx)
            audit_rows.append(
                {
                    "trade_id": tid,
                    "violation_type": vtype,
                    "decision": "kept",
                    "reason": "pass2_detector_match",
                }
            )
        else:
            audit_rows.append(
                {
                    "trade_id": tid,
                    "violation_type": vtype,
                    "decision": "dropped",
                    "reason": "not_in_pass2_detector_output",
                }
            )

    out = hits.loc[kept_idx] if kept_idx else hits.iloc[0:0]
    audit = pd.DataFrame(audit_rows)
    return out, audit


def write_pass2_audit(audit: pd.DataFrame) -> Path | None:
    if audit.empty:
        return None
    path = OUTPUTS_DIR / "p3_second_pass_audit.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(path, index=False)
    return path
