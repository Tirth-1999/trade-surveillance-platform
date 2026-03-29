"""Independent AI ground-truth agent for crypto trade surveillance.

Loads raw data (no imports from p3_detect or crypto_load), reasons from
finance first principles via LLM, and produces ground_truth.csv.
Falls back to a lightweight independent rule set if the API is unavailable.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import numpy as np
import pandas as pd

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

from bits_hackathon.core.paths import ROOT, OUTPUTS_DIR, CRYPTO_TRADES, CRYPTO_MARKET, CRYPTO_SYMBOLS as SYMBOLS

SYSTEM_PROMPT = """\
You are a senior trade surveillance analyst at a financial regulator.
You review crypto trades for suspicious activity.

VIOLATION TAXONOMY (use exact strings):
- wash_trading: Trades with no economic risk transfer (same wallet buy+sell, circular)
- spoofing: Orders/trades to mislead about supply/demand
- layering: Multiple orders at different prices to create false depth
- pump_and_dump: Coordinated price inflation followed by selling
- ramping: Sustained directional pressure to move price
- peg_manipulation: Stablecoin trades deviating from expected peg
- structuring: Splitting transactions to avoid reporting thresholds
- aml_structuring: AML-specific structuring patterns

For each trade, you receive a facts bundle. Respond with ONLY a valid JSON array.
Each element must be:
{
  "trade_id": "<string>",
  "verdict": "suspicious" | "benign" | "uncertain",
  "violation_type": "<exact string from taxonomy above, or empty string>",
  "confidence": <float 0.0-1.0>,
  "rationale": "<2-3 sentences explaining why>",
  "remark_draft": "<1-2 sentence remark suitable for a compliance report>"
}
Return ONLY the JSON array, no markdown fences or commentary."""


# ---------------------------------------------------------------------------
# Data loading (independent of crypto_load.py)
# ---------------------------------------------------------------------------

def _load_trades_raw(symbol: str) -> pd.DataFrame:
    path = CRYPTO_TRADES / f"{symbol}_trades.csv"
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["symbol"] = symbol
    if "wallet_id" not in df.columns and "trader_id" in df.columns:
        df = df.rename(columns={"trader_id": "wallet_id"})
    df["notional_usdt"] = df["price"] * df["quantity"]
    df["trade_date"] = df["timestamp"].dt.strftime("%Y-%m-%d")
    df["minute"] = df["timestamp"].dt.floor("min")
    return df


def _load_market_raw(symbol: str) -> pd.DataFrame:
    path = CRYPTO_MARKET / f"Binance_{symbol}_2026_minute.csv"
    df = pd.read_csv(path, parse_dates=["Date"])
    for c in df.columns:
        if c.startswith("Volume ") and c != "Volume USDT":
            df = df.rename(columns={c: "volume_base"})
    df = df.rename(columns={"Volume USDT": "volume_usdt"})
    df["symbol"] = symbol
    df["minute"] = df["Date"].dt.floor("min")
    return df


def load_all() -> tuple[pd.DataFrame, pd.DataFrame]:
    trades = pd.concat([_load_trades_raw(s) for s in SYMBOLS], ignore_index=True)
    markets = pd.concat([_load_market_raw(s) for s in SYMBOLS], ignore_index=True)
    return trades, markets


# ---------------------------------------------------------------------------
# Facts bundle builder
# ---------------------------------------------------------------------------

def _build_facts(
    row: pd.Series,
    markets: pd.DataFrame,
    wallet_summary: dict[str, dict],
    symbol_stats: dict[str, dict],
    peer_cache: dict[tuple[str, Any], dict],
) -> dict:
    sym = row["symbol"]
    minute = row["minute"]

    bar = markets[(markets["symbol"] == sym) & (markets["minute"] == minute)]
    bar_ctx: list[dict] = []
    if not bar.empty:
        idx = bar.index[0]
        for offset in range(-2, 3):
            loc = idx + offset
            if 0 <= loc < len(markets):
                b = markets.iloc[loc]
                if b["symbol"] == sym:
                    bar_ctx.append({
                        "offset": offset,
                        "open": float(b["Open"]), "high": float(b["High"]),
                        "low": float(b["Low"]), "close": float(b["Close"]),
                        "volume_usdt": float(b.get("volume_usdt", 0)),
                        "tradecount": int(b.get("tradecount", 0)),
                    })

    mid = None
    price_vs_mid_bps = None
    if bar_ctx:
        centre = [b for b in bar_ctx if b["offset"] == 0]
        if centre:
            mid = (centre[0]["high"] + centre[0]["low"]) / 2.0
            if mid > 0:
                price_vs_mid_bps = abs(row["price"] - mid) / mid * 10000

    ss = symbol_stats.get(sym, {})
    median_notional = ss.get("median_notional", row["notional_usdt"])
    notional_ratio = row["notional_usdt"] / median_notional if median_notional else 1.0

    ws = wallet_summary.get(row["wallet_id"], {})
    peer_key = (sym, minute)
    peer = peer_cache.get(peer_key, {"count": 0, "total_notional": 0, "sides": {}})

    return {
        "trade_id": row["trade_id"],
        "symbol": sym,
        "side": row["side"],
        "price": float(row["price"]),
        "quantity": float(row["quantity"]),
        "notional_usdt": float(row["notional_usdt"]),
        "timestamp": str(row["timestamp"]),
        "bar_context": bar_ctx,
        "price_vs_mid_bps": round(price_vs_mid_bps, 2) if price_vs_mid_bps is not None else None,
        "notional_vs_pair_median": round(notional_ratio, 4),
        "wallet_summary": ws,
        "peer_trades": peer,
    }


def precompute_lookups(
    trades: pd.DataFrame, markets: pd.DataFrame,
) -> tuple[dict, dict, dict]:
    wallet_summary: dict[str, dict] = {}
    for wid, g in trades.groupby("wallet_id"):
        wallet_summary[wid] = {
            "total_trades": len(g),
            "total_notional": round(float(g["notional_usdt"].sum()), 2),
            "distinct_symbols": int(g["symbol"].nunique()),
            "time_span_hours": round(
                (g["timestamp"].max() - g["timestamp"].min()).total_seconds() / 3600, 2
            ),
        }

    symbol_stats: dict[str, dict] = {}
    for sym, g in trades.groupby("symbol"):
        symbol_stats[sym] = {
            "median_notional": float(g["notional_usdt"].median()),
            "mean_notional": float(g["notional_usdt"].mean()),
            "std_notional": float(g["notional_usdt"].std()),
        }

    peer_cache: dict[tuple[str, Any], dict] = {}
    for (sym, minute), g in trades.groupby(["symbol", "minute"]):
        sides = g["side"].value_counts().to_dict()
        peer_cache[(sym, minute)] = {
            "count": len(g),
            "total_notional": round(float(g["notional_usdt"].sum()), 2),
            "sides": sides,
        }

    return wallet_summary, symbol_stats, peer_cache


# ---------------------------------------------------------------------------
# LLM caller (OpenRouter)
# ---------------------------------------------------------------------------

def _call_llm(facts_batch: list[dict], api_key: str, attempt: int = 0) -> list[dict]:
    if requests is None:
        raise RuntimeError("requests library not installed")

    prompt = (
        "Analyze these trades. Return a JSON array, one element per trade.\n"
        + json.dumps(facts_batch, separators=(",", ":"))
    )

    models = ["nvidia/nemotron-3-nano-30b-a3b:free", "openrouter/free"]
    model = models[0] if attempt < 2 else models[1]

    max_retries = 3
    for retry in range(max_retries):
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://bits-hackathon.local",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 8192,
                },
                timeout=120,
            )

            if resp.status_code == 429:
                wait = min(2 ** (retry + 1), 30)
                time.sleep(wait)
                continue

            resp.raise_for_status()
            body = resp.json()
            content = body.get("choices", [{}])[0].get("message", {}).get("content")
            if not content:
                raise ValueError("Empty content from LLM")

            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[: content.rfind("```")]
            content = content.strip()

            parsed = json.loads(content)
            if isinstance(parsed, dict):
                parsed = [parsed]
            return parsed

        except (json.JSONDecodeError, ValueError) as e:
            if retry < max_retries - 1:
                time.sleep(1)
                continue
            raise

    raise RuntimeError(f"LLM failed after {max_retries} retries")


# ---------------------------------------------------------------------------
# Vectorized stub fallback (independent rule set — NOT the same as p3_detect.py)
# ---------------------------------------------------------------------------

def _stub_analyse_vectorized(
    trades: pd.DataFrame,
    markets: pd.DataFrame,
    symbol_stats: dict[str, dict],
) -> pd.DataFrame:
    """Fully vectorized stub analysis — no row-by-row iteration."""
    t = trades.copy()
    t["verdict"] = "benign"
    t["violation_type"] = ""
    t["confidence"] = 0.1
    t["rationale"] = "No anomaly detected by independent rule set."
    t["remark_draft"] = "Trade appears normal."

    # Pre-join bars
    bar_info = markets.groupby(["symbol", "minute"]).agg(
        bar_high=("High", "first"),
        bar_low=("Low", "first"),
    ).reset_index()
    t = t.merge(bar_info, on=["symbol", "minute"], how="left")
    t["bar_mid"] = (t["bar_high"] + t["bar_low"]) / 2.0

    # Rule 1: Price outside bar [Low, High] with >20 bps from mid
    outside = (t["price"] < t["bar_low"]) | (t["price"] > t["bar_high"])
    bps = (t["price"] - t["bar_mid"]).abs() / t["bar_mid"].replace(0, np.nan) * 10000
    r1 = outside.fillna(False) & (bps > 20)
    t.loc[r1, "verdict"] = "suspicious"
    t.loc[r1, "violation_type"] = "spoofing"
    t.loc[r1, "confidence"] = (0.5 + bps[r1] / 500).clip(upper=0.95)
    t.loc[r1, "rationale"] = "Trade price outside bar range — possible spoofing."
    t.loc[r1, "remark_draft"] = "Price deviation from bar midpoint — possible spoofing."

    # Rule 2: Same wallet buy+sell within 120s via merge_asof (per symbol)
    benign_mask = t["verdict"] == "benign"
    wash_ids: set[str] = set()
    for sym, g in t[benign_mask].groupby("symbol"):
        g = g.sort_values("timestamp")
        buys = g[g["side"] == "BUY"][["timestamp", "wallet_id", "notional_usdt", "trade_id"]]
        sells = g[g["side"] == "SELL"][["timestamp", "wallet_id", "notional_usdt", "trade_id"]]
        if buys.empty or sells.empty:
            continue
        tw = pd.Timedelta(seconds=120)
        m = pd.merge_asof(
            buys.sort_values("timestamp"),
            sells.sort_values("timestamp"),
            on="timestamp", by="wallet_id",
            direction="nearest", tolerance=tw,
            suffixes=("_buy", "_sell"),
        ).dropna(subset=["trade_id_sell"])
        if m.empty:
            continue
        rel = (m["notional_usdt_buy"] - m["notional_usdt_sell"]).abs() / (
            m[["notional_usdt_buy", "notional_usdt_sell"]].max(axis=1).replace(0, np.nan)
        )
        hit = m[rel < 0.05]
        for col in ("trade_id_buy", "trade_id_sell"):
            wash_ids.update(hit[col].tolist())

    if wash_ids:
        r2 = t["trade_id"].isin(wash_ids) & (t["verdict"] == "benign")
        t.loc[r2, "verdict"] = "suspicious"
        t.loc[r2, "violation_type"] = "wash_trading"
        t.loc[r2, "confidence"] = 0.75
        t.loc[r2, "rationale"] = "Same wallet BUY/SELL within 120s with similar notional."
        t.loc[r2, "remark_draft"] = "Possible wash trade — same wallet round-trip."

    # Rule 3: Notional just below round thresholds (structuring)
    benign_mask = t["verdict"] == "benign"
    for threshold in [3000, 5000, 10000]:
        r3 = benign_mask & (t["notional_usdt"] >= threshold * 0.98) & (t["notional_usdt"] < threshold)
        t.loc[r3, "verdict"] = "suspicious"
        t.loc[r3, "violation_type"] = "structuring"
        t.loc[r3, "confidence"] = 0.55
        t.loc[r3, "rationale"] = f"Notional just below ${threshold} threshold."
        t.loc[r3, "remark_draft"] = f"Trade sized just below ${threshold} — possible structuring."
        benign_mask = t["verdict"] == "benign"

    # Rule 4: USDC peg deviation > 0.5%
    r4 = benign_mask & (t["symbol"] == "USDCUSDT") & ((t["price"] - 1.0).abs() * 100 > 0.5)
    dev_pct = (t["price"] - 1.0).abs() * 100
    t.loc[r4, "verdict"] = "suspicious"
    t.loc[r4, "violation_type"] = "peg_manipulation"
    t.loc[r4, "confidence"] = (0.5 + dev_pct[r4] / 5).clip(upper=0.95)
    t.loc[r4, "rationale"] = "USDCUSDT price deviating from $1 peg."
    t.loc[r4, "remark_draft"] = "Stablecoin trade off peg — possible peg manipulation."

    # Rule 5: Notional z-score > 3
    benign_mask = t["verdict"] == "benign"
    sym_mean = t["symbol"].map({s: v["mean_notional"] for s, v in symbol_stats.items()})
    sym_std = t["symbol"].map({s: v["std_notional"] for s, v in symbol_stats.items()}).replace(0, 1)
    zscore = (t["notional_usdt"] - sym_mean) / sym_std
    r5 = benign_mask & (zscore > 3.0)
    t.loc[r5, "verdict"] = "suspicious"
    t.loc[r5, "violation_type"] = "pump_and_dump"
    t.loc[r5, "confidence"] = (0.4 + zscore[r5] / 20).clip(upper=0.85)
    t.loc[r5, "rationale"] = "Extreme notional outlier for this symbol."
    t.loc[r5, "remark_draft"] = "Unusually large trade — possible market manipulation."

    result_cols = ["trade_id", "verdict", "violation_type", "confidence", "rationale", "remark_draft"]
    return t[result_cols].drop_duplicates(subset=["trade_id"], keep="first")


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def _process_llm_batch(
    batch: list[dict],
    api_key: str,
    batch_num: int,
    n_batches: int,
) -> list[dict]:
    """Process a single LLM batch — returns list of dicts or empty on failure."""
    try:
        llm_results = _call_llm(batch, api_key)
        print(f"  LLM batch {batch_num}/{n_batches}: {len(llm_results)} results")
        return llm_results
    except Exception as e:
        print(f"  LLM batch {batch_num}/{n_batches} failed ({e})")
        return []


def run_ground_truth(
    trades: pd.DataFrame,
    markets: pd.DataFrame,
    batch_size: int = 10,
    use_llm: bool = True,
    max_workers: int = 3,
) -> pd.DataFrame:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key or requests is None:
        use_llm = False
        print("No OPENROUTER_API_KEY or requests missing — using stub fallback rules.")

    wallet_summary, symbol_stats, peer_cache = precompute_lookups(trades, markets)

    # Pass 1: Vectorized stub on ALL trades (fast baseline)
    print(f"Pass 1: Stub analysis on {len(trades)} trades …")
    stub_results = _stub_analyse_vectorized(trades, markets, symbol_stats)
    print(f"  Stub found {(stub_results['verdict'] == 'suspicious').sum()} suspicious")

    results_df = stub_results

    if use_llm:
        # Pass 2: LLM enrichment on suspicious + borderline trades only
        sus_ids = set(stub_results[stub_results["verdict"] == "suspicious"]["trade_id"])

        # Also include borderline trades (high notional, near thresholds, USDC)
        bar_info = markets.groupby(["symbol", "minute"]).agg(
            bar_high=("High", "first"), bar_low=("Low", "first"),
        ).reset_index()
        t_check = trades.merge(bar_info, on=["symbol", "minute"], how="left")
        outside_bar = (t_check["price"] < t_check["bar_low"]) | (t_check["price"] > t_check["bar_high"])
        borderline_ids = set(t_check.loc[outside_bar.fillna(False), "trade_id"])

        sym_stats_map = {s: v for s, v in symbol_stats.items()}
        for sym, g in trades.groupby("symbol"):
            ss = sym_stats_map.get(sym)
            if ss and ss["std_notional"] > 0:
                z = (g["notional_usdt"] - ss["mean_notional"]) / ss["std_notional"]
                borderline_ids.update(g.loc[z > 2.0, "trade_id"])

        for threshold in [3000, 5000, 10000]:
            near = trades[(trades["notional_usdt"] >= threshold * 0.95) & (trades["notional_usdt"] < threshold * 1.02)]
            borderline_ids.update(near["trade_id"])

        usdc_off_peg = trades[(trades["symbol"] == "USDCUSDT") & ((trades["price"] - 1.0).abs() > 0.003)]
        borderline_ids.update(usdc_off_peg["trade_id"])

        review_ids = sus_ids | borderline_ids
        review_trades = trades[trades["trade_id"].isin(review_ids)].reset_index(drop=True)
        print(f"\nPass 2: LLM review on {len(review_trades)} trades (suspicious + borderline) …")

        bar_index: dict[tuple[str, Any], dict] = {}
        for sym_name, g in markets.groupby("symbol"):
            for minute_val, sub in g.groupby("minute"):
                row0 = sub.iloc[0]
                bar_index[(sym_name, minute_val)] = {
                    "h": float(row0["High"]), "l": float(row0["Low"]),
                    "vol": float(row0.get("volume_usdt", 0)),
                    "tc": int(row0.get("tradecount", 0)),
                }

        facts_list = []
        for _, row in review_trades.iterrows():
            sym = row["symbol"]
            bar = bar_index.get((sym, row["minute"]))
            mid = (bar["h"] + bar["l"]) / 2.0 if bar else None
            price_vs_mid = round(abs(row["price"] - mid) / mid * 10000, 2) if mid and mid > 0 else None
            ss = symbol_stats.get(sym, {})
            med_n = ss.get("median_notional", row["notional_usdt"])
            ws = wallet_summary.get(row["wallet_id"], {})
            peer = peer_cache.get((sym, row["minute"]), {})
            facts_list.append({
                "trade_id": row["trade_id"],
                "symbol": sym,
                "side": row["side"],
                "price": float(row["price"]),
                "notional": float(row["notional_usdt"]),
                "ts": str(row["timestamp"]),
                "bar": bar or {},
                "mid_bps": price_vs_mid,
                "n_ratio": round(row["notional_usdt"] / med_n, 4) if med_n else 1.0,
                "wallet": ws,
                "peers": peer.get("count", 0),
            })

        batches = [
            facts_list[i : i + batch_size]
            for i in range(0, len(facts_list), batch_size)
        ]
        n_batches = len(batches)
        print(f"  {n_batches} batches of {batch_size}, {max_workers} workers")

        llm_results: list[dict] = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(
                    _process_llm_batch, batch, api_key, idx + 1, n_batches,
                ): idx
                for idx, batch in enumerate(batches)
            }
            for future in as_completed(futures):
                llm_results.extend(future.result())

        if llm_results:
            llm_df = pd.DataFrame(llm_results)
            if "trade_id" in llm_df.columns:
                llm_df = llm_df.drop_duplicates(subset=["trade_id"], keep="first")
                llm_ids = set(llm_df["trade_id"])
                results_df = pd.concat([
                    results_df[~results_df["trade_id"].isin(llm_ids)],
                    llm_df[["trade_id", "verdict", "violation_type", "confidence", "rationale", "remark_draft"]],
                ], ignore_index=True)
                print(f"  LLM enriched {len(llm_ids)} trades")
            else:
                print("  LLM results missing trade_id column, keeping stub results")
        else:
            print("  No LLM results, keeping stub results")
    else:
        total = len(trades)
        print(f"Running vectorized stub analysis on {total} trades …")
        results_df = _stub_analyse_vectorized(trades, markets, symbol_stats)
        print(f"  Done: {len(results_df)} results")

    results_df = results_df.drop_duplicates(subset=["trade_id"], keep="first")

    trade_info = trades[["trade_id", "symbol", "trade_date"]].drop_duplicates(subset=["trade_id"])
    results_df = results_df.merge(trade_info, on="trade_id", how="left")
    results_df = results_df.rename(columns={"trade_date": "date"})

    cols = ["symbol", "date", "trade_id", "verdict", "violation_type", "confidence", "rationale", "remark_draft"]
    for c in cols:
        if c not in results_df.columns:
            results_df[c] = ""
    return results_df[cols].reset_index(drop=True)
