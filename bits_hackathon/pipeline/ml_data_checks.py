"""Lightweight data validation before ML train/infer (surveillance governance)."""

from __future__ import annotations

import pandas as pd


def validate_crypto_frames(trades: pd.DataFrame, markets: pd.DataFrame) -> list[str]:
    issues: list[str] = []
    if trades is None or trades.empty:
        issues.append("trades DataFrame is empty")
        return issues
    if markets is None or markets.empty:
        issues.append("markets DataFrame is empty")
    req_t = {"trade_id", "symbol", "timestamp", "wallet_id", "notional_usdt", "trade_date"}
    missing_t = req_t - set(trades.columns)
    if missing_t:
        issues.append(f"trades missing columns: {sorted(missing_t)}")
    req_m = {"Date", "symbol", "volume_usdt"}
    missing_m = req_m - set(markets.columns)
    if missing_m:
        issues.append(f"markets missing columns: {sorted(missing_m)}")
    if "trade_id" in trades.columns:
        dup = trades["trade_id"].duplicated().sum()
        if dup:
            issues.append(f"trades has {dup} duplicate trade_id rows")
    null_frac = trades[["notional_usdt", "price", "quantity"]].isna().mean().max()
    if null_frac > 0.05:
        issues.append(f"high null fraction in price/qty/notional: max {null_frac:.2%}")
    return issues
