"""Problem 3 rule-based anomaly detectors. Returns rows: trade_id, symbol, date, violation_type, remarks."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _base_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["trade_id", "symbol", "trade_date"]].copy()
    out = out.rename(columns={"trade_date": "date"})
    return out


def detect_peg_break_usdc(trades: pd.DataFrame) -> pd.DataFrame:
    """USDCUSDT: price deviates >0.5% from $1 peg."""
    d = trades[trades["symbol"] == "USDCUSDT"].copy()
    dev = (d["price"] - 1.0).abs() / 1.0
    hit = dev > 0.005
    if not hit.any():
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    sub = d.loc[hit]
    base = _base_cols(sub)
    base["violation_type"] = "peg_break"
    base["remarks"] = (
        "USDCUSDT stablecoin trade with |price-1|/1 > 0.5% ("
        + (dev[hit] * 100).round(4).astype(str)
        + "% from peg)."
    )
    return base


def detect_wash_same_wallet(trades: pd.DataFrame, window_sec: int = 90) -> pd.DataFrame:
    """Same wallet BUY and SELL within window with similar notional (wash_trading)."""
    rows = []
    tw = pd.Timedelta(seconds=window_sec)
    for sym, g in trades.groupby("symbol"):
        g = g.sort_values("timestamp").reset_index(drop=True)
        buys = g[g["side"] == "BUY"][["timestamp", "wallet_id", "notional_usdt", "trade_id", "price"]]
        sells = g[g["side"] == "SELL"][["timestamp", "wallet_id", "notional_usdt", "trade_id", "price"]]
        if buys.empty or sells.empty:
            continue
        merged = pd.merge_asof(
            buys.sort_values("timestamp"),
            sells.sort_values("timestamp"),
            on="timestamp",
            by="wallet_id",
            direction="nearest",
            tolerance=tw,
            suffixes=("_buy", "_sell"),
        )
        merged = merged.dropna(subset=["trade_id_sell"])
        if merged.empty:
            continue
        rel = (
            (merged["notional_usdt_buy"] - merged["notional_usdt_sell"]).abs()
            / merged[["notional_usdt_buy", "notional_usdt_sell"]].max(axis=1).replace(0, np.nan)
        )
        ok = rel < 0.02
        hit = merged.loc[ok]
        for _, r in hit.iterrows():
            for tid_col in ("trade_id_buy", "trade_id_sell"):
                tid = r[tid_col]
                rows.append(
                    {
                        "trade_id": tid,
                        "symbol": sym,
                        "date": pd.Timestamp(r["timestamp"]).strftime("%Y-%m-%d"),
                        "violation_type": "wash_trading",
                        "remarks": (
                            f"Same wallet {r['wallet_id']} BUY/SELL within {window_sec}s, "
                            f"notionals within 2% — indicative wash."
                        ),
                    }
                )
    if not rows:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    return pd.DataFrame(rows).drop_duplicates(subset=["trade_id"])


def detect_ramping(trades: pd.DataFrame, min_streak: int = 6, max_gap_sec: int = 3600) -> pd.DataFrame:
    """Same wallet monotonic BUY prices over consecutive BUY streak."""
    rows = []
    for sym, g in trades.groupby("symbol"):
        g = g.sort_values("timestamp")
        for wid, w in g.groupby("wallet_id"):
            w = w.sort_values("timestamp")
            buys = w[w["side"] == "BUY"]
            if len(buys) < min_streak:
                continue
            prices = buys["price"].values
            ts = buys["timestamp"].values
            ids = buys["trade_id"].values
            dates = buys["trade_date"].values
            streak_start = 0
            for i in range(1, len(prices)):
                gap = (pd.Timestamp(ts[i]) - pd.Timestamp(ts[i - 1])).total_seconds()
                if prices[i] > prices[i - 1] and gap <= max_gap_sec:
                    continue
                streak_len = i - streak_start
                if streak_len >= min_streak:
                    for j in range(streak_start, i):
                        rows.append(
                            {
                                "trade_id": ids[j],
                                "symbol": sym,
                                "date": dates[j],
                                "violation_type": "ramping",
                                "remarks": (
                                    f"Wallet {wid}: {streak_len} consecutive BUYs with strictly "
                                    "increasing prices (ramping sequence)."
                                ),
                            }
                        )
                streak_start = i
            streak_len = len(prices) - streak_start
            if streak_len >= min_streak:
                for j in range(streak_start, len(prices)):
                    rows.append(
                        {
                            "trade_id": ids[j],
                            "symbol": sym,
                            "date": dates[j],
                            "violation_type": "ramping",
                            "remarks": (
                                f"Wallet {wid}: {streak_len} consecutive BUYs with strictly "
                                "increasing prices (ramping sequence)."
                            ),
                        }
                    )
    if not rows:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    return pd.DataFrame(rows).drop_duplicates(subset=["trade_id"])


def detect_aml_structuring(trades: pd.DataFrame, low: float = 9980, high: float = 10000, min_count: int = 6) -> pd.DataFrame:
    """Many trades with notional just below 10k USDT from same wallet same day."""
    d = trades[(trades["notional_usdt"] >= low) & (trades["notional_usdt"] < high)].copy()
    if d.empty:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    grp = d.groupby(["wallet_id", "symbol", "trade_date"])
    rows = []
    for (wid, sym, day), sub in grp:
        if len(sub) < min_count:
            continue
        cv = sub["notional_usdt"].std() / sub["notional_usdt"].mean() if sub["notional_usdt"].mean() else 1
        if cv > 0.015:  # must be near-identical sizes
            continue
        for _, r in sub.iterrows():
            rows.append(
                {
                    "trade_id": r["trade_id"],
                    "symbol": sym,
                    "date": day,
                    "violation_type": "aml_structuring",
                    "remarks": (
                        f"{len(sub)} trades from {wid} on {day} with notional in [{low},{high}) USDT "
                        f"and tight size dispersion (smurfing below threshold)."
                    ),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    return pd.DataFrame(rows)


def detect_threshold_testing(trades: pd.DataFrame, band: float = 50, min_below: int = 4) -> pd.DataFrame:
    """At least one trade at notional ~10k then cluster just below from same wallet."""
    rows = []
    for (wid, sym), g in trades.groupby(["wallet_id", "symbol"]):
        for day, d in g.groupby("trade_date"):
            at = d[(d["notional_usdt"] >= 10000 - 1) & (d["notional_usdt"] <= 10000 + 50)]
            below = d[(d["notional_usdt"] >= 10000 - band - 500) & (d["notional_usdt"] < 10000 - 1)]
            if len(at) < 1 or len(below) < min_below:
                continue
            sub = pd.concat([at, below])
            for _, r in sub.iterrows():
                rows.append(
                    {
                        "trade_id": r["trade_id"],
                        "symbol": sym,
                        "date": day,
                        "violation_type": "threshold_testing",
                        "remarks": (
                            f"Wallet {wid}: trade at ~10k USDT then {len(below)} sub-threshold "
                            "sized trades same day — threshold probe then structuring."
                        ),
                    }
                )
    if not rows:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    return pd.DataFrame(rows).drop_duplicates(subset=["trade_id"])


def detect_layering_echo(trades: pd.DataFrame, window_sec: int = 600) -> pd.DataFrame:
    """Wallet runs BUY burst then SELL burst reversing within window (simplified layering_echo)."""
    rows = []
    tw = pd.Timedelta(seconds=window_sec)
    for sym, g in trades.groupby("symbol"):
        g = g.sort_values("timestamp")
        for wid, w in g.groupby("wallet_id"):
            w = w.sort_values("timestamp")
            buys = w[w["side"] == "BUY"]
            sells = w[w["side"] == "SELL"]
            if buys.empty or sells.empty:
                continue
            first_sell_after = sells["timestamp"].min()
            buy_burst = buys[buys["timestamp"] <= first_sell_after]
            if len(buy_burst) < 3:
                continue
            sell_after = sells[sells["timestamp"] > buy_burst["timestamp"].min()]
            sell_after = sell_after[sell_after["timestamp"] <= buy_burst["timestamp"].max() + tw]
            if len(sell_after) < 3:
                continue
            sub = pd.concat([buy_burst, sell_after])
            for _, r in sub.iterrows():
                rows.append(
                    {
                        "trade_id": r["trade_id"],
                        "symbol": sym,
                        "date": r["trade_date"],
                        "violation_type": "layering_echo",
                        "remarks": (
                            f"Wallet {wid}: BUY cluster then offsetting SELLs within {window_sec}s — "
                            "momentum fade / layering echo pattern."
                        ),
                    }
                )
    if not rows:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    return pd.DataFrame(rows).drop_duplicates(subset=["trade_id"])


def detect_coordinated_structuring(trades: pd.DataFrame, low: float = 9950, high: float = 10000) -> pd.DataFrame:
    """Multiple distinct wallets each with sub-threshold notional in same minute (coordinated smurfing)."""
    d = trades[(trades["notional_usdt"] >= low) & (trades["notional_usdt"] < high)].copy()
    if d.empty:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    rows = []
    for (sym, minute), sub in d.groupby(["symbol", "minute"]):
        if sub["wallet_id"].nunique() < 4:
            continue
        for _, r in sub.iterrows():
            rows.append(
                {
                    "trade_id": r["trade_id"],
                    "symbol": sym,
                    "date": r["trade_date"],
                    "violation_type": "coordinated_structuring",
                    "remarks": (
                        f"{sub['wallet_id'].nunique()} wallets in same minute with notional in "
                        f"[{low},{high}) — coordinated structuring."
                    ),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    return pd.DataFrame(rows)


def detect_bat_volume_spike_trades(trades: pd.DataFrame, markets: pd.DataFrame, mult: float = 5.0) -> pd.DataFrame:
    """BATUSDT: flag trades in hours where volume_usdt exceeds mult × median hourly for that symbol."""
    sym = "BATUSDT"
    m = markets[markets["symbol"] == sym].copy()
    if m.empty:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    m["hour"] = m["Date"].dt.floor("h")
    hv = m.groupby("hour")["volume_usdt"].sum()
    med = hv.median()
    if med == 0:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    hot = hv[hv > mult * med].index
    t = trades[trades["symbol"] == sym].copy()
    t["hour"] = t["timestamp"].dt.floor("h")
    sub = t[t["hour"].isin(hot)]
    if sub.empty:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    base = _base_cols(sub)
    base["violation_type"] = "pump_and_dump"
    base["remarks"] = (
        f"BATUSDT trade in hour with aggregate bar volume >{mult}× median hourly — "
        "investigate pump/liquidity event."
    )
    return base.drop_duplicates(subset=["trade_id"])


def detect_price_bar_violation(trades: pd.DataFrame, markets: pd.DataFrame, min_mid_bps: float = 35.0) -> pd.DataFrame:
    """Trades whose price is outside that minute's High/Low with material distance from bar mid."""
    m = markets[["symbol", "minute", "High", "Low"]].copy()
    t = trades.merge(m, on=["symbol", "minute"], how="left")
    bad = (t["price"] < t["Low"]) | (t["price"] > t["High"])
    mid = (t["High"] + t["Low"]) / 2.0
    bps = (t["price"] - mid).abs() / mid.replace(0, float("nan")) * 10000.0
    sub = t.loc[bad.fillna(False) & (bps > min_mid_bps)]
    if sub.empty:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    base = _base_cols(sub)
    base["violation_type"] = "spoofing"
    base["remarks"] = (
        "Trade price outside 1m bar range; deviation from bar mid exceeds "
        f"{min_mid_bps:.0f} bps — inconsistent with bar OHLC."
    )
    return base


def detect_round_trip_pairs(trades: pd.DataFrame, window_sec: int = 120) -> pd.DataFrame:
    """Two wallets swap BUY/SELL with matched notionals within window (round_trip_wash)."""
    rows = []
    tw = pd.Timedelta(seconds=window_sec)
    for sym, g in trades.groupby("symbol"):
        g = g.sort_values("timestamp")
        buys = g[g["side"] == "BUY"][
            ["timestamp", "wallet_id", "notional_usdt", "trade_id", "trade_date"]
        ].rename(columns={"wallet_id": "w_buy", "trade_id": "tid_buy"})
        sells = g[g["side"] == "SELL"][
            ["timestamp", "wallet_id", "notional_usdt", "trade_id", "trade_date"]
        ].rename(columns={"wallet_id": "w_sell", "trade_id": "tid_sell"})
        if buys.empty or sells.empty:
            continue
        m = pd.merge_asof(
            buys.sort_values("timestamp"),
            sells.sort_values("timestamp"),
            on="timestamp",
            direction="nearest",
            tolerance=tw,
        )
        m = m[m["w_buy"] != m["w_sell"]]
        if m.empty:
            continue
        rel = (m["notional_usdt_x"] - m["notional_usdt_y"]).abs() / m[
            ["notional_usdt_x", "notional_usdt_y"]
        ].max(axis=1).replace(0, np.nan)
        hit = m[rel < 0.02]
        for _, r in hit.iterrows():
            rows.append(
                {
                    "trade_id": r["tid_buy"],
                    "symbol": sym,
                    "date": r["trade_date_x"],
                    "violation_type": "round_trip_wash",
                    "remarks": (
                        f"Wallets {r['w_buy']} / {r['w_sell']} crossed BUY/SELL within {window_sec}s "
                        "with matched notionals (within 2%) — round-trip wash between accounts."
                    ),
                }
            )
            rows.append(
                {
                    "trade_id": r["tid_sell"],
                    "symbol": sym,
                    "date": r["trade_date_y"] if pd.notna(r["trade_date_y"]) else r["trade_date_x"],
                    "violation_type": "round_trip_wash",
                    "remarks": (
                        f"Wallets {r['w_buy']} / {r['w_sell']} crossed BUY/SELL within {window_sec}s "
                        "with matched notionals (within 2%) — round-trip wash between accounts."
                    ),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    return pd.DataFrame(rows).drop_duplicates(subset=["trade_id"])


def detect_usdc_wash_at_peg(trades: pd.DataFrame) -> pd.DataFrame:
    """USDC trades at ~1.0 with same-wallet quick round-trip."""
    d = trades[trades["symbol"] == "USDCUSDT"].copy()
    d = d[(d["price"] - 1.0).abs() < 0.0005]
    w = detect_wash_same_wallet(d, window_sec=60)
    if w.empty:
        return w
    w = w.copy()
    w["violation_type"] = "wash_volume_at_peg"
    w["remarks"] = w["remarks"] + " At peg ~$1.00."
    return w


def detect_chain_layering(trades: pd.DataFrame, window_sec: int = 300) -> pd.DataFrame:
    """Sequential SELL notional passes A->B->C within short window (simplified chain)."""
    rows = []
    tw = pd.Timedelta(seconds=window_sec)
    for sym, g in trades.groupby("symbol"):
        sells = g[g["side"] == "SELL"].sort_values("timestamp")
        n = len(sells)
        if n < 3 or n > 2500:
            continue
        ts = sells["timestamp"].values
        wid = sells["wallet_id"].values
        nid = sells["notional_usdt"].values
        tid = sells["trade_id"].values
        day = sells["trade_date"].values
        for i in range(min(n - 2, 800)):
            for j in range(i + 1, min(i + 12, n)):
                if (pd.Timestamp(ts[j]) - pd.Timestamp(ts[i])) > tw:
                    break
                if abs(nid[i] - nid[j]) / max(nid[i], nid[j], 1e-9) > 0.1:
                    continue
                for k in range(j + 1, min(j + 12, n)):
                    if (pd.Timestamp(ts[k]) - pd.Timestamp(ts[j])) > tw:
                        break
                    if abs(nid[j] - nid[k]) / max(nid[j], nid[k], 1e-9) > 0.1:
                        continue
                    if len({wid[i], wid[j], wid[k]}) == 3:
                        for idx in (i, j, k):
                            rows.append(
                                {
                                    "trade_id": tid[idx],
                                    "symbol": sym,
                                    "date": day[idx],
                                    "violation_type": "chain_layering",
                                    "remarks": (
                                        "Three-wallet sequential SELL chain with matched notionals within "
                                        f"{window_sec}s."
                                    ),
                                }
                            )
                        break
    if not rows:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    return pd.DataFrame(rows).drop_duplicates(subset=["trade_id"])


def detect_pump_dump_bars(
    trades: pd.DataFrame,
    markets: pd.DataFrame,
    symbols: tuple[str, ...] = ("BATUSDT", "DOGEUSDT"),
) -> pd.DataFrame:
    """Bars with strong up move then sharp reversal — BUY trades in pump leg (illiquid / volatile pairs only)."""
    rows = []
    for sym, m in markets.groupby("symbol"):
        if sym not in symbols:
            continue
        m = m.sort_values("Date").reset_index(drop=True)
        c = m["Close"]
        vol = m["volume_usdt"]
        med_vol = vol.rolling(60, min_periods=10).median()
        up = c / c.shift(3) - 1.0
        down = c.shift(-3) / c - 1.0
        thr_up, thr_dn = (0.025, -0.015) if sym == "DOGEUSDT" else (0.02, -0.015)
        flag = (up > thr_up) & (down < thr_dn) & (vol > med_vol * 1.5)
        hits = m.loc[flag]
        if hits.empty:
            continue
        for _, bar in hits.iterrows():
            i = bar.name
            if i < 3:
                continue
            t0 = m.loc[i - 3, "Date"]
            t1 = m.loc[i, "Date"]
            sub = trades[
                (trades["symbol"] == sym)
                & (trades["timestamp"] >= t0)
                & (trades["timestamp"] <= t1)
                & (trades["side"] == "BUY")
            ]
            if sub.empty:
                continue
            nmin = trades.loc[trades["symbol"] == sym, "notional_usdt"].quantile(0.72)
            sub = sub[sub["notional_usdt"] >= nmin]
            sub = sub.nlargest(6, "notional_usdt")
            for _, r in sub.iterrows():
                rows.append(
                    {
                        "trade_id": r["trade_id"],
                        "symbol": sym,
                        "date": r["trade_date"],
                        "violation_type": "pump_and_dump",
                        "remarks": (
                            "Local price run-up followed by reversal in subsequent bars — "
                            "pump-phase BUY participation."
                        ),
                    }
                )
    if not rows:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    return pd.DataFrame(rows).drop_duplicates(subset=["trade_id"])


def detect_placement_smurfing(trades: pd.DataFrame, min_new_wallets: int = 6) -> pd.DataFrame:
    """Many wallets' first-ever trade in the dataset falls in the same minute (coordinated placement)."""
    t = trades.sort_values("timestamp")
    first_ts = t.groupby("wallet_id")["timestamp"].transform("min")
    t = t.copy()
    t["is_first_trade"] = t["timestamp"] == first_ts
    firsts = t[t["is_first_trade"]]
    rows = []
    for (sym, minute), sub in firsts.groupby(["symbol", "minute"]):
        if sub["wallet_id"].nunique() < min_new_wallets:
            continue
        for _, r in sub.iterrows():
            rows.append(
                {
                    "trade_id": r["trade_id"],
                    "symbol": sym,
                    "date": r["trade_date"],
                    "violation_type": "placement_smurfing",
                    "remarks": (
                        f"{sub['wallet_id'].nunique()} wallets' first observed trade in same minute — "
                        "placement smurfing / coordinated onboarding."
                    ),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    return pd.DataFrame(rows).drop_duplicates(subset=["trade_id"])


def _trim_violation(hits: pd.DataFrame, trades: pd.DataFrame, vtype: str, max_rows: int) -> pd.DataFrame:
    sub = hits[hits["violation_type"] == vtype]
    rest = hits[hits["violation_type"] != vtype]
    if len(sub) <= max_rows:
        return hits
    n = trades.set_index("trade_id")["notional_usdt"]
    sub = sub.copy()
    sub["_n"] = sub["trade_id"].map(n)
    sub = sub.nlargest(max_rows, "_n").drop(columns=["_n"])
    return pd.concat([rest, sub], ignore_index=True)


def run_all_detectors(trades: pd.DataFrame, markets: pd.DataFrame) -> pd.DataFrame:
    """Merge detector outputs; later rows win on duplicate trade_id for violation_type."""
    markets = markets.copy()
    markets["minute"] = markets["Date"].dt.floor("min")
    # Omit noisy rules (mid deviation, cross-pair every trade, manager consolidation, coordinated_pump per minute)
    detectors = [
        detect_peg_break_usdc,
        detect_price_bar_violation,
        detect_wash_same_wallet,
        detect_usdc_wash_at_peg,
        detect_round_trip_pairs,
        detect_ramping,
        detect_aml_structuring,
        detect_threshold_testing,
        detect_coordinated_structuring,
        detect_layering_echo,
        detect_bat_volume_spike_trades,
        detect_placement_smurfing,
        detect_chain_layering,
        detect_pump_dump_bars,
    ]
    parts = []
    for f in detectors:
        if f in (detect_bat_volume_spike_trades, detect_price_bar_violation, detect_pump_dump_bars):
            parts.append(f(trades, markets))
        else:
            parts.append(f(trades))
    out = pd.concat([p for p in parts if not p.empty], ignore_index=True)
    if out.empty:
        return out
    out = _trim_violation(out, trades, "pump_and_dump", max_rows=35)
    out = _trim_violation(out, trades, "spoofing", max_rows=80)
    out = _trim_violation(out, trades, "round_trip_wash", max_rows=25)
    # Priority: peg and bar violations and wash are high precision — keep first occurrence
    priority = {
        "peg_break": 0,
        "wash_volume_at_peg": 1,
        "wash_trading": 2,
        "round_trip_wash": 3,
        "aml_structuring": 4,
        "threshold_testing": 5,
        "coordinated_structuring": 6,
        "ramping": 7,
        "layering_echo": 8,
        "pump_and_dump": 9,
        "chain_layering": 10,
        "placement_smurfing": 11,
        "spoofing": 12,
    }
    out["_prio"] = out["violation_type"].map(lambda x: priority.get(x, 99))
    out = out.sort_values(["trade_id", "_prio"]).drop_duplicates(subset=["trade_id"], keep="first")
    out = out.drop(columns=["_prio"])
    return out.reset_index(drop=True)


def build_submission(trades: pd.DataFrame, markets: pd.DataFrame) -> pd.DataFrame:
    hits = run_all_detectors(trades, markets)
    if hits.empty:
        return pd.DataFrame(columns=["symbol", "date", "trade_id", "violation_type", "remarks"])
    return hits[["symbol", "date", "trade_id", "violation_type", "remarks"]]
