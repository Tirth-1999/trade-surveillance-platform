"""Problem 3 rule-based anomaly detectors. Returns rows: trade_id, symbol, date, violation_type, remarks."""

from __future__ import annotations

import numpy as np
import pandas as pd

from bits_hackathon.core.config import get as cfg
from bits_hackathon.core.violation_taxonomy import normalize_violation_type


def _liquid_min_notional(symbol: str, base_min: float) -> float:
    liq = cfg("p3.liquid_pair_symbols")
    if not isinstance(liq, (list, tuple)):
        liq = ["BTCUSDT", "ETHUSDT"]
    extra = float(cfg("p3.min_notional_liquid_pair_usdt"))
    if symbol in liq:
        return max(float(base_min), extra)
    return float(base_min)


def _base_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["trade_id", "symbol", "trade_date"]].copy()
    out = out.rename(columns={"trade_date": "date"})
    return out


def detect_peg_break_usdc(trades: pd.DataFrame, markets: pd.DataFrame) -> pd.DataFrame:
    """USDCUSDT: price deviates >0.5% from $1 peg; require material trade + bar volume context."""
    dev_pct = float(cfg("p3.peg_break.deviation_pct"))
    min_trade_n = float(cfg("p3.peg_break.min_trade_notional_usdt"))
    min_bar_vol = float(cfg("p3.peg_break.min_bar_volume_usdt"))
    d = trades[trades["symbol"] == "USDCUSDT"].copy()
    if d.empty:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    mb = markets[markets["symbol"] == "USDCUSDT"][["minute", "volume_usdt"]].drop_duplicates("minute")
    d = d.merge(mb, on="minute", how="left")
    dev = (d["price"] - 1.0).abs() / 1.0
    vol_ok = d["volume_usdt"].fillna(0) >= min_bar_vol
    size_ok = d["notional_usdt"] >= min_trade_n
    hit = (dev > dev_pct) & vol_ok & size_ok
    if not hit.any():
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    sub = d.loc[hit]
    base = _base_cols(sub)
    base["violation_type"] = "peg_break"
    base["remarks"] = (
        "USDCUSDT |price-1| > "
        + str(dev_pct * 100)
        + "%; trade notional ≥ "
        + str(min_trade_n)
        + " USDT and bar volume ≥ "
        + str(min_bar_vol)
        + " — peg break with context."
    )
    return base


def detect_wash_same_wallet(
    trades: pd.DataFrame,
    window_sec: int | None = None,
    notional_rel_tol: float | None = None,
    min_notional_usdt: float | None = None,
) -> pd.DataFrame:
    """Same wallet BUY then SELL (or SELL then BUY) within window with similar notional.

    Uses ordered merge_asof (forward / backward) instead of nearest to avoid wrong-leg pairing.
    """
    window_sec = int(window_sec if window_sec is not None else cfg("p3.wash.window_sec"))
    tol = float(notional_rel_tol if notional_rel_tol is not None else cfg("p3.wash.notional_rel_tol"))
    min_n_base = float(min_notional_usdt if min_notional_usdt is not None else cfg("p3.wash.min_notional_usdt"))
    rows: list[dict] = []
    tw = pd.Timedelta(seconds=window_sec)
    for sym, g in trades.groupby("symbol"):
        min_n = _liquid_min_notional(sym, min_n_base)
        g = g.sort_values("timestamp").reset_index(drop=True)
        buys = g[g["side"] == "BUY"][
            ["timestamp", "wallet_id", "notional_usdt", "trade_id", "trade_date"]
        ].copy()
        sells = g[g["side"] == "SELL"][
            ["timestamp", "wallet_id", "notional_usdt", "trade_id", "trade_date"]
        ].copy()
        buys = buys[buys["notional_usdt"] >= min_n]
        sells = sells[sells["notional_usdt"] >= min_n]
        if buys.empty or sells.empty:
            continue

        b = buys.rename(
            columns={
                "timestamp": "ts_buy",
                "notional_usdt": "n_buy",
                "trade_id": "tid_buy",
                "trade_date": "date_buy",
            }
        )
        s = sells.rename(
            columns={
                "timestamp": "ts_sell",
                "notional_usdt": "n_sell",
                "trade_id": "tid_sell",
                "trade_date": "date_sell",
            }
        )

        def _pairs_buy_first() -> None:
            for wid, bb in b.groupby("wallet_id", sort=False):
                ss = s.loc[s["wallet_id"] == wid].sort_values("ts_sell")
                bb = bb.sort_values("ts_buy")
                if ss.empty:
                    continue
                m = pd.merge_asof(
                    bb,
                    ss,
                    left_on="ts_buy",
                    right_on="ts_sell",
                    direction="forward",
                    tolerance=tw,
                )
                m = m.dropna(subset=["tid_sell"])
                if m.empty:
                    continue
                rel = (m["n_buy"] - m["n_sell"]).abs() / m[["n_buy", "n_sell"]].max(axis=1).replace(0, np.nan)
                for _, r in m.loc[rel < tol].iterrows():
                    day = str(r["date_buy"])
                    for tid, dcol in ((r["tid_buy"], day), (r["tid_sell"], str(r["date_sell"]))):
                        rows.append(
                            {
                                "trade_id": tid,
                                "symbol": sym,
                                "date": dcol,
                                "violation_type": "wash_trading",
                                "remarks": (
                                    f"Same wallet {wid} BUY→SELL within {window_sec}s (forward match), "
                                    f"notionals within {tol*100:.1f}% — wash pattern."
                                ),
                            }
                        )

        def _pairs_sell_first() -> None:
            for wid, ss in s.groupby("wallet_id", sort=False):
                bb = b.loc[b["wallet_id"] == wid].sort_values("ts_buy")
                ss = ss.sort_values("ts_sell")
                if bb.empty:
                    continue
                m = pd.merge_asof(
                    ss,
                    bb,
                    left_on="ts_sell",
                    right_on="ts_buy",
                    direction="backward",
                    tolerance=tw,
                )
                m = m.dropna(subset=["tid_buy"])
                if m.empty:
                    continue
                rel = (m["n_buy"] - m["n_sell"]).abs() / m[["n_buy", "n_sell"]].max(axis=1).replace(0, np.nan)
                for _, r in m.loc[rel < tol].iterrows():
                    day = str(r["date_sell"])
                    for tid, dcol in ((r["tid_sell"], day), (r["tid_buy"], str(r["date_buy"]))):
                        rows.append(
                            {
                                "trade_id": tid,
                                "symbol": sym,
                                "date": dcol,
                                "violation_type": "wash_trading",
                                "remarks": (
                                    f"Same wallet {wid} SELL←BUY within {window_sec}s (backward match), "
                                    f"notionals within {tol*100:.1f}% — wash pattern."
                                ),
                            }
                        )

        _pairs_buy_first()
        _pairs_sell_first()

    if not rows:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    return pd.DataFrame(rows).drop_duplicates(subset=["trade_id"])


def detect_ramping(
    trades: pd.DataFrame,
    min_streak: int | None = None,
    max_gap_sec: int | None = None,
    max_median_gap_sec: float | None = None,
) -> pd.DataFrame:
    """Same wallet monotonic BUY prices over a tight burst (not stitched trends)."""
    min_streak = int(min_streak if min_streak is not None else cfg("p3.ramping.min_streak"))
    max_gap_sec = int(max_gap_sec if max_gap_sec is not None else cfg("p3.ramping.max_gap_sec"))
    max_med = float(max_median_gap_sec if max_median_gap_sec is not None else cfg("p3.ramping.max_median_gap_sec"))
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

            def emit_segment(start: int, end: int) -> None:
                """end exclusive; require median inter-trade gap <= max_med."""
                if end - start < min_streak:
                    return
                gaps = []
                for k in range(start + 1, end):
                    gaps.append((pd.Timestamp(ts[k]) - pd.Timestamp(ts[k - 1])).total_seconds())
                med = float(np.median(gaps)) if gaps else 0.0
                if med > max_med:
                    return
                streak_len = end - start
                for j in range(start, end):
                    rows.append(
                        {
                            "trade_id": ids[j],
                            "symbol": sym,
                            "date": dates[j],
                            "violation_type": "ramping",
                            "remarks": (
                                f"Wallet {wid}: {streak_len} BUYs strictly increasing prices, "
                                f"max_gap≤{max_gap_sec}s median_gap≤{max_med:.0f}s — ramping burst."
                            ),
                        }
                    )

            for i in range(1, len(prices)):
                gap = (pd.Timestamp(ts[i]) - pd.Timestamp(ts[i - 1])).total_seconds()
                if prices[i] > prices[i - 1] and gap <= max_gap_sec:
                    continue
                emit_segment(streak_start, i)
                streak_start = i
            emit_segment(streak_start, len(prices))
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


def detect_layering_echo(trades: pd.DataFrame, window_sec: int | None = None) -> pd.DataFrame:
    """Wallet runs BUY burst then SELL burst with balanced notional (layering_echo)."""
    window_sec = int(window_sec if window_sec is not None else cfg("p3.layering_echo.window_sec"))
    max_imb = float(cfg("p3.layering_echo.max_notional_imbalance"))
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
            if len(buy_burst) < int(cfg("p3.layering_echo.min_burst")):
                continue
            sell_after = sells[sells["timestamp"] > buy_burst["timestamp"].min()]
            sell_after = sell_after[sell_after["timestamp"] <= buy_burst["timestamp"].max() + tw]
            if len(sell_after) < int(cfg("p3.layering_echo.min_burst")):
                continue
            bsum = float(buy_burst["notional_usdt"].sum())
            ssum = float(sell_after["notional_usdt"].sum())
            denom = max(bsum, ssum, 1e-9)
            if abs(bsum - ssum) / denom > max_imb:
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
                            f"Wallet {wid}: BUY/SELL bursts within {window_sec}s, "
                            f"notional imbalance ≤{max_imb*100:.0f}% — layering echo."
                        ),
                    }
                )
    if not rows:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    return pd.DataFrame(rows).drop_duplicates(subset=["trade_id"])


def detect_coordinated_structuring(
    trades: pd.DataFrame, low: float | None = None, high: float | None = None
) -> pd.DataFrame:
    """Multiple distinct wallets with similar sub-threshold notionals in same minute."""
    low = float(low if low is not None else cfg("p3.coordinated_structuring.low"))
    high = float(high if high is not None else cfg("p3.coordinated_structuring.high"))
    min_w = int(cfg("p3.coordinated_structuring.min_wallets"))
    max_cv = float(cfg("p3.coordinated_structuring.max_wallet_mean_cv"))
    d = trades[(trades["notional_usdt"] >= low) & (trades["notional_usdt"] < high)].copy()
    if d.empty:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    rows = []
    for (sym, minute), sub in d.groupby(["symbol", "minute"]):
        if sub["wallet_id"].nunique() < min_w:
            continue
        per_w = sub.groupby("wallet_id")["notional_usdt"].mean()
        wmean = float(per_w.mean()) if len(per_w) else 0.0
        wstd = float(per_w.std()) if len(per_w) > 1 else 0.0
        cv = (wstd / wmean) if wmean > 0 else 1.0
        if cv > max_cv:
            continue
        for _, r in sub.iterrows():
            rows.append(
                {
                    "trade_id": r["trade_id"],
                    "symbol": sym,
                    "date": r["trade_date"],
                    "violation_type": "coordinated_structuring",
                    "remarks": (
                        f"{sub['wallet_id'].nunique()} wallets same minute, notional in [{low},{high}), "
                        f"tight cross-wallet size (CV≤{max_cv:.2f}) — coordinated structuring."
                    ),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    return pd.DataFrame(rows)


def detect_bat_volume_spike_trades(
    trades: pd.DataFrame, markets: pd.DataFrame, mult: float | None = None
) -> pd.DataFrame:
    """BATUSDT: trades in hours where volume spikes vs median and tradecount is material."""
    sym = "BATUSDT"
    mult = float(mult if mult is not None else cfg("p3.bat_volume_spike.multiplier"))
    min_tc = int(cfg("p3.bat_volume_spike.min_hour_tradecount"))
    m = markets[markets["symbol"] == sym].copy()
    if m.empty:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    m["hour"] = m["Date"].dt.floor("h")
    agg = m.groupby("hour").agg(volume_usdt=("volume_usdt", "sum"), tradecount=("tradecount", "sum"))
    med = agg["volume_usdt"].median()
    if med == 0:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    med_tc = agg["tradecount"].median()
    tc_floor = max(min_tc, float(med_tc) * 0.35)
    hot = agg.index[(agg["volume_usdt"] > mult * med) & (agg["tradecount"] >= tc_floor)]
    t = trades[trades["symbol"] == sym].copy()
    t["hour"] = t["timestamp"].dt.floor("h")
    sub = t[t["hour"].isin(hot)]
    if sub.empty:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    base = _base_cols(sub)
    base["violation_type"] = "pump_and_dump"
    base["remarks"] = (
        f"BATUSDT hour volume >{mult}× median hourly AND hour tradecount ≥{tc_floor:.0f} — "
        "liquidity/pump context."
    )
    return base.drop_duplicates(subset=["trade_id"])


def detect_price_bar_violation(
    trades: pd.DataFrame, markets: pd.DataFrame, min_mid_bps: float | None = None
) -> pd.DataFrame:
    """Trades outside bar H/L; stricter mid-bps when bar tradecount is low (likely stale bar)."""
    min_bps = float(min_mid_bps if min_mid_bps is not None else cfg("p3.price_bar_violation.min_mid_bps"))
    low_tc_thr = int(cfg("p3.price_bar_violation.low_liquidity_tradecount"))
    strict_bps = float(cfg("p3.price_bar_violation.min_mid_bps_low_liquidity"))
    m = markets[["symbol", "minute", "High", "Low", "tradecount"]].copy()
    t = trades.merge(m, on=["symbol", "minute"], how="left")
    bad = (t["price"] < t["Low"]) | (t["price"] > t["High"])
    mid = (t["High"] + t["Low"]) / 2.0
    bps = (t["price"] - mid).abs() / mid.replace(0, float("nan")) * 10000.0
    tc = pd.to_numeric(t["tradecount"], errors="coerce").fillna(0)
    need_bps = np.where(tc < low_tc_thr, strict_bps, min_bps)
    sub = t.loc[bad.fillna(False) & (bps > need_bps)]
    if sub.empty:
        return pd.DataFrame(columns=["trade_id", "symbol", "date", "violation_type", "remarks"])
    base = _base_cols(sub)
    base["violation_type"] = "spoofing"
    base["remarks"] = (
        "Price outside 1m bar H/L with large mid deviation; low-tradecount bars use stricter bps — "
        "possible spoof/print vs bar mismatch."
    )
    return base


def detect_round_trip_pairs(trades: pd.DataFrame, window_sec: int | None = None) -> pd.DataFrame:
    """Two wallets: SELL leg matched to prior BUY within window, different wallets, min notional."""
    window_sec = int(window_sec if window_sec is not None else cfg("p3.round_trip.window_sec"))
    tol = float(cfg("p3.round_trip.notional_rel_tol"))
    min_n_base = float(cfg("p3.round_trip.min_notional_usdt"))
    rows = []
    tw = pd.Timedelta(seconds=window_sec)
    for sym, g in trades.groupby("symbol"):
        min_n = _liquid_min_notional(sym, min_n_base)
        g = g.sort_values("timestamp")
        buys = g[g["side"] == "BUY"][
            ["timestamp", "wallet_id", "notional_usdt", "trade_id", "trade_date"]
        ].rename(
            columns={
                "wallet_id": "w_buy",
                "trade_id": "tid_buy",
                "notional_usdt": "n_buy",
                "trade_date": "date_buy",
            }
        )
        sells = g[g["side"] == "SELL"][
            ["timestamp", "wallet_id", "notional_usdt", "trade_id", "trade_date"]
        ].rename(
            columns={
                "wallet_id": "w_sell",
                "trade_id": "tid_sell",
                "notional_usdt": "n_sell",
                "trade_date": "date_sell",
            }
        )
        buys = buys[buys["n_buy"] >= min_n]
        sells = sells[sells["n_sell"] >= min_n]
        if buys.empty or sells.empty:
            continue
        m = pd.merge_asof(
            sells.sort_values("timestamp"),
            buys.sort_values("timestamp"),
            on="timestamp",
            direction="backward",
            tolerance=tw,
        )
        m = m[m["w_buy"] != m["w_sell"]]
        if m.empty:
            continue
        rel = (m["n_sell"] - m["n_buy"]).abs() / m[["n_sell", "n_buy"]].max(axis=1).replace(0, np.nan)
        hit = m[rel < tol]
        for _, r in hit.iterrows():
            rows.append(
                {
                    "trade_id": r["tid_buy"],
                    "symbol": sym,
                    "date": r["date_buy"],
                    "violation_type": "round_trip_wash",
                    "remarks": (
                        f"Wallets {r['w_buy']} / {r['w_sell']} BUY→SELL within {window_sec}s "
                        f"notionals within {tol*100:.0f}%, min {min_n:.0f} USDT — round-trip wash."
                    ),
                }
            )
            rows.append(
                {
                    "trade_id": r["tid_sell"],
                    "symbol": sym,
                    "date": r["date_sell"],
                    "violation_type": "round_trip_wash",
                    "remarks": (
                        f"Wallets {r['w_buy']} / {r['w_sell']} BUY→SELL within {window_sec}s "
                        f"notionals within {tol*100:.0f}%, min {min_n:.0f} USDT — round-trip wash."
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
            q = float(cfg("p3.pump_dump.notional_quantile"))
            nmin = trades.loc[trades["symbol"] == sym, "notional_usdt"].quantile(q)
            sub = sub[sub["notional_usdt"] >= nmin]
            sub = sub.nlargest(int(cfg("p3.pump_dump.max_trades_per_bar")), "notional_usdt")
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
        if f in (
            detect_peg_break_usdc,
            detect_bat_volume_spike_trades,
            detect_price_bar_violation,
            detect_pump_dump_bars,
        ):
            parts.append(f(trades, markets))
        else:
            parts.append(f(trades))
    out = pd.concat([p for p in parts if not p.empty], ignore_index=True)
    if out.empty:
        return out
    out = _trim_violation(out, trades, "pump_and_dump", max_rows=int(cfg("p3.trim.pump_and_dump")))
    out = _trim_violation(out, trades, "spoofing", max_rows=int(cfg("p3.trim.spoofing")))
    out = _trim_violation(out, trades, "round_trip_wash", max_rows=int(cfg("p3.trim.round_trip_wash")))
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
    out = hits[["symbol", "date", "trade_id", "violation_type", "remarks"]].copy()
    out["violation_type"] = out["violation_type"].map(
        lambda x: normalize_violation_type(str(x)) if pd.notna(x) else ""
    )
    return out
