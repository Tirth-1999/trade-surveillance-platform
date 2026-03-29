"""Load crypto minute bars and trades; normalize column names."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bits_hackathon.core.paths import CRYPTO_MARKET, CRYPTO_TRADES, CRYPTO_SYMBOLS


def market_csv_path(symbol: str) -> Path:
    return CRYPTO_MARKET / f"Binance_{symbol}_2026_minute.csv"


def trades_csv_path(symbol: str) -> Path:
    return CRYPTO_TRADES / f"{symbol}_trades.csv"


def _base_volume_col(columns: list[str]) -> str | None:
    for c in columns:
        if c.startswith("Volume ") and c != "Volume USDT":
            return c
    return None


def load_market(symbol: str) -> pd.DataFrame:
    path = market_csv_path(symbol)
    df = pd.read_csv(path, parse_dates=["Date"])
    vol_col = _base_volume_col(list(df.columns))
    if vol_col:
        df = df.rename(columns={vol_col: "volume_base"})
    df = df.rename(
        columns={
            "Volume USDT": "volume_usdt",
            "tradecount": "tradecount",
        }
    )
    df["symbol"] = symbol
    df["minute"] = df["Date"].dt.floor("min")
    return df


def load_trades(symbol: str) -> pd.DataFrame:
    path = trades_csv_path(symbol)
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["symbol"] = symbol
    if "wallet_id" not in df.columns and "trader_id" in df.columns:
        df = df.rename(columns={"trader_id": "wallet_id"})
    df["trade_date"] = df["timestamp"].dt.strftime("%Y-%m-%d")
    df["notional_usdt"] = df["price"] * df["quantity"]
    df["minute"] = df["timestamp"].dt.floor("min")
    return df


def load_all_trades() -> pd.DataFrame:
    parts = [load_trades(s) for s in CRYPTO_SYMBOLS]
    return pd.concat(parts, ignore_index=True)


def load_all_markets() -> pd.DataFrame:
    parts = [load_market(s) for s in CRYPTO_SYMBOLS]
    return pd.concat(parts, ignore_index=True)
