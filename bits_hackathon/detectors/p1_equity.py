"""Problem 1: order-book microstructure alerts."""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from bits_hackathon.core.paths import EQUITY


def load_market() -> pd.DataFrame:
    path = EQUITY / "market_data.csv"
    df = pd.read_csv(path, parse_dates=["timestamp"])
    bid_cols = [f"bid_size_level{i:02d}" for i in range(1, 11)]
    ask_cols = [f"ask_size_level{i:02d}" for i in range(1, 11)]
    for c in bid_cols + ask_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["total_bid"] = df[bid_cols].sum(axis=1)
    df["total_ask"] = df[ask_cols].sum(axis=1)
    tot = df["total_bid"] + df["total_ask"]
    df["obi"] = np.where(tot > 0, (df["total_bid"] - df["total_ask"]) / tot, 0.0)
    bp = df["bid_price_level01"].replace(0, np.nan)
    df["spread_bps"] = (
        (df["ask_price_level01"] - df["bid_price_level01"]) / bp * 10000.0
    )
    df["bid_concentration"] = np.where(
        df["total_bid"] > 0, df["bid_size_level01"] / df["total_bid"], np.nan
    )
    return df


def load_trades() -> pd.DataFrame:
    path = EQUITY / "trade_data.csv"
    return pd.read_csv(path, parse_dates=["timestamp"])


def _rolling_z(s: pd.Series, win: int = 30, minp: int = 15) -> pd.Series:
    m = s.rolling(win, min_periods=minp).mean()
    sd = s.rolling(win, min_periods=minp).std(ddof=0).replace(0, np.nan)
    return (s - m) / sd


def obi_spread_alerts(mkt: pd.DataFrame, z_thr: float = 3.15, min_run: int = 5) -> list[dict]:
    alerts: list[dict] = []
    for sec_id, g in mkt.groupby("sec_id"):
        g = g.sort_values("timestamp").reset_index(drop=True)
        g["obi_z"] = _rolling_z(g["obi"])
        g["spread_z"] = _rolling_z(g["spread_bps"])
        g["conc_z"] = _rolling_z(g["bid_concentration"])
        spread_hit = g["spread_z"].notna() & (g["spread_z"] > z_thr)
        extreme = (g["obi_z"].abs() > z_thr) | (g["conc_z"].abs() > z_thr) | spread_hit
        g["ext"] = extreme.fillna(False)
        if not g["ext"].any():
            continue
        g["grp"] = (g["ext"] != g["ext"].shift()).cumsum()
        for _, block in g[g["ext"]].groupby("grp"):
            if block.empty or len(block) < min_run:
                continue
            ts0 = block["timestamp"].iloc[0]
            trade_date = ts0.strftime("%Y-%m-%d")
            tstr = ts0.strftime("%H:%M:%S")
            obi_m = block["obi"].mean()
            sz = block["spread_z"].max()
            sz_s = f"{sz:.2f}" if pd.notna(sz) else "n/a"
            remarks = (
                f"Sustained {len(block)}+ minutes where rolling 30m z>{z_thr}: mean OBI={obi_m:.3f}, "
                f"max spread_z={sz_s}, max |obi_z|={block['obi_z'].abs().max():.2f} — "
                "order book imbalance / spread vs prior baseline."
            )
            sev = (
                "HIGH"
                if block["obi"].abs().mean() > 0.72 or (pd.notna(sz) and sz > 4.5)
                else "MEDIUM"
            )
            alerts.append(
                {
                    "sec_id": sec_id,
                    "trade_date": trade_date,
                    "time_window_start": tstr,
                    "anomaly_type": "order_book_imbalance",
                    "severity": sev,
                    "remarks": remarks,
                    "_score": float(block["obi_z"].abs().max()),
                }
            )
    alerts.sort(key=lambda x: -x["_score"])
    for a in alerts:
        del a["_score"]
    return alerts[:28]


def cancel_pattern_alerts(trades: pd.DataFrame, win_min: int = 15, min_cancels: int = 4) -> list[dict]:
    """Clusters of CANCELLED orders from same trader (spoofing-style)."""
    c = trades[trades["order_status"] == "CANCELLED"].copy()
    if c.empty:
        return []
    alerts = []
    for (sec_id, tid), g in c.groupby(["sec_id", "trader_id"]):
        g = g.sort_values("timestamp")
        ts = g["timestamp"].values
        for i in range(len(g)):
            t0 = pd.Timestamp(ts[i])
            mask = (g["timestamp"] >= t0) & (g["timestamp"] <= t0 + pd.Timedelta(minutes=win_min))
            sub = g.loc[mask]
            if len(sub) < min_cancels:
                continue
            if sub["side"].nunique() < 1:
                continue
            dominant_side = sub["side"].mode().iloc[0]
            if (sub["side"] == dominant_side).sum() < min_cancels:
                continue
            tstart = sub["timestamp"].min().strftime("%H:%M:%S")
            d = sub["timestamp"].min().strftime("%Y-%m-%d")
            alerts.append(
                {
                    "sec_id": sec_id,
                    "trade_date": d,
                    "time_window_start": tstart,
                    "anomaly_type": "unusual_cancel_pattern",
                    "severity": "MEDIUM",
                    "remarks": (
                        f"{len(sub)} CANCELLED {dominant_side} orders from {tid} within {win_min} minutes "
                        f"on sec_id {sec_id} — consistent with layering/spoofing-style quote flicker."
                    ),
                }
            )
            break
    return alerts[:20]


def build_p1_alerts() -> tuple[pd.DataFrame, float]:
    t0 = time.perf_counter()
    mkt = load_market()
    trd = load_trades()
    rows = obi_spread_alerts(mkt)
    rows.extend(cancel_pattern_alerts(trd))
    elapsed = time.perf_counter() - t0
    if not rows:
        df = pd.DataFrame(
            columns=[
                "alert_id",
                "sec_id",
                "trade_date",
                "time_window_start",
                "anomaly_type",
                "severity",
                "remarks",
                "time_to_run",
            ]
        )
        return df, elapsed
    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["sec_id", "trade_date", "time_window_start", "anomaly_type"])
    df.insert(0, "alert_id", range(1, len(df) + 1))
    df["time_to_run"] = round(elapsed, 2)
    return df, elapsed
