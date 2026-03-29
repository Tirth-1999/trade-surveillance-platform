"""Shared tabular feature engineering for P3 ML (stage-1 and stage-2)."""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_COLS: list[str] = [
    "notional_zscore",
    "price_vs_mid_bps",
    "wallet_trade_count",
    "wallet_total_notional",
    "time_gap_same_wallet",
    "bar_volume_ratio",
    "bar_tradecount",
    "minute_peer_count",
    "minute_peer_notional",
    "is_stablecoin",
    "price_vs_peg_bps",
    "hour_of_day",
    "notional_vs_threshold",
]


def engineer_features(
    trades: pd.DataFrame,
    markets: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    markets = markets.copy()
    markets["minute"] = markets["Date"].dt.floor("min")

    sym_stats = trades.groupby("symbol")["notional_usdt"].agg(["mean", "std"])
    trades = trades.merge(sym_stats, on="symbol", how="left", suffixes=("", "_sym"))
    trades["notional_zscore"] = (trades["notional_usdt"] - trades["mean"]) / trades["std"].replace(0, 1)

    bar_mid = markets.groupby(["symbol", "minute"]).agg(
        bar_high=("High", "first"),
        bar_low=("Low", "first"),
        bar_volume=("volume_usdt", "first"),
        bar_tradecount=("tradecount", "first"),
    ).reset_index()
    bar_mid["bar_mid"] = (bar_mid["bar_high"] + bar_mid["bar_low"]) / 2

    trades = trades.merge(bar_mid, on=["symbol", "minute"], how="left")
    trades["price_vs_mid_bps"] = (
        (trades["price"] - trades["bar_mid"]).abs() / trades["bar_mid"].replace(0, np.nan) * 10000
    )
    trades["bar_volume_ratio"] = trades["notional_usdt"] / trades["bar_volume"].replace(0, np.nan)

    wallet_agg = trades.groupby("wallet_id").agg(
        wallet_trade_count=("trade_id", "count"),
        wallet_total_notional=("notional_usdt", "sum"),
    )
    trades = trades.merge(wallet_agg, on="wallet_id", how="left")

    trades = trades.sort_values(["wallet_id", "timestamp"])
    trades["prev_ts_same_wallet"] = trades.groupby("wallet_id")["timestamp"].shift(1)
    trades["next_ts_same_wallet"] = trades.groupby("wallet_id")["timestamp"].shift(-1)
    gap_prev = (trades["timestamp"] - trades["prev_ts_same_wallet"]).dt.total_seconds().abs()
    gap_next = (trades["next_ts_same_wallet"] - trades["timestamp"]).dt.total_seconds().abs()
    trades["time_gap_same_wallet"] = pd.concat([gap_prev, gap_next], axis=1).min(axis=1)

    peer = trades.groupby(["symbol", "minute"]).agg(
        minute_peer_count=("trade_id", "count"),
        minute_peer_notional=("notional_usdt", "sum"),
    ).reset_index()
    trades = trades.merge(peer, on=["symbol", "minute"], how="left", suffixes=("", "_peer"))

    trades["is_stablecoin"] = (trades["symbol"] == "USDCUSDT").astype(int)
    trades["price_vs_peg_bps"] = (trades["price"] - 1.0).abs() * 10000
    trades["hour_of_day"] = trades["timestamp"].dt.hour

    thresholds = np.array([3000, 5000, 10000])
    trades["notional_vs_threshold"] = trades["notional_usdt"].apply(
        lambda x: float(np.min(np.abs(x - thresholds)))
    )

    for c in FEATURE_COLS:
        if c not in trades.columns:
            trades[c] = 0.0

    return trades, FEATURE_COLS
