"""Problem 2: SEC submissions API + pre-announcement drift vs equity OHLCV/trades."""

from __future__ import annotations

import re
import time

import pandas as pd
import requests

from bits_hackathon.core.paths import EQUITY

SUBMISSIONS_TMPL = "https://data.sec.gov/submissions/CIK{cik10}.json"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
HEADERS = {
    "User-Agent": "BITS-Hackathon-Student contact@example.edu",
    "Accept-Encoding": "gzip, deflate",
}


def load_ohlcv() -> pd.DataFrame:
    return pd.read_csv(EQUITY / "ohlcv.csv", parse_dates=["trade_date"])


def load_trades() -> pd.DataFrame:
    return pd.read_csv(EQUITY / "trade_data.csv", parse_dates=["timestamp"])


def fetch_ticker_cik_map(session: requests.Session) -> dict[str, str]:
    r = session.get(TICKERS_URL, headers=HEADERS, timeout=60)
    r.raise_for_status()
    raw = r.json()
    out: dict[str, str] = {}
    for _, row in raw.items():
        t = str(row["ticker"]).upper().strip()
        cik = int(row["cik_str"])
        out[t] = f"{cik:010d}"
    return out


def fetch_submissions(session: requests.Session, cik10: str) -> dict | None:
    url = SUBMISSIONS_TMPL.format(cik10=cik10)
    r = session.get(url, headers=HEADERS, timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def cik_folder(cik10: str) -> str:
    return str(int(cik10))


def filing_url(cik10: str, accession: str, primary_doc: str) -> str:
    nodash = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_folder(cik10)}/{nodash}/{primary_doc}"


_MA = re.compile(
    r"merger|acquisition|acquir|take[- ]?over|tender|business\s+combination|definitive\s+agreement",
    re.I,
)


def classify_8k(items: str, doc_desc: str) -> str:
    """Use 8-K item numbers first (SEC taxonomy), then text."""
    it = items or ""
    blob = f"{it} {doc_desc or ''}"
    if re.search(r"(^|[,\s])1\.01([,\s]|$)", it) or re.search(r"(^|[,\s])2\.01([,\s]|$)", it):
        return "merger"
    if re.search(r"2\.02", it):
        return "earnings"
    if re.search(r"5\.02", it):
        return "leadership"
    if re.search(r"4\.02", it):
        return "restatement"
    if _MA.search(blob):
        return "merger"
    if re.search(r"earnings|results|EPS", blob, re.I):
        return "earnings"
    if re.search(r"officer|director|CEO|CFO|appoint|resign|departure", blob, re.I):
        return "leadership"
    if re.search(r"restate|revision", blob, re.I):
        return "restatement"
    return "other"


def pre_event_metrics(ohlcv_sec: pd.DataFrame, event_date: pd.Timestamp) -> tuple[float, float]:
    ev = pd.Timestamp(event_date).normalize()
    hist = ohlcv_sec[ohlcv_sec["trade_date"] < ev].sort_values("trade_date")
    if len(hist) < 16:
        return float("nan"), float("nan")
    baseline = hist.iloc[-16:-1]
    t_window = hist.iloc[-6:-1]
    t1 = hist.iloc[-1]
    vol_mean = baseline["volume"].mean()
    vol_std = baseline["volume"].std(ddof=0) or 1.0
    vol_z = (t1["volume"] - vol_mean) / vol_std
    if len(t_window) < 5:
        return float(vol_z), float("nan")
    cum_ret = t1["close"] / t_window.iloc[0]["close"] - 1.0
    return float(vol_z), float(cum_ret)


def trade_evidence(trades: pd.DataFrame, sec_id: int, window_start: pd.Timestamp, window_end: pd.Timestamp) -> str:
    tmin = trades["timestamp"].min()
    tmax = trades["timestamp"].max()
    ws = max(pd.Timestamp(window_start), tmin)
    we = min(pd.Timestamp(window_end), tmax + pd.Timedelta(seconds=1))
    sub = trades[
        (trades["sec_id"] == sec_id)
        & (trades["timestamp"] >= ws)
        & (trades["timestamp"] < we)
        & (trades["order_status"] == "FILLED")
    ]
    if sub.empty:
        return (
            f"No FILLED rows for sec_id in [{ws.date()} .. {we.date()}); "
            f"trade tape starts {tmin.date()} — may not cover full pre-filing window."
        )
    med_q = sub["quantity"].median()
    large = sub[sub["quantity"] > 5 * med_q]
    if large.empty:
        return f"Filled activity ({len(sub)} rows); no outsized quantity vs median."
    tids = large["trader_id"].value_counts().head(3).to_dict()
    return f"Large fills vs median qty; top trader_ids: {tids}"


def iter_recent_8k(sub_json: dict, date_min: str, date_max: str) -> list[dict]:
    recent = sub_json.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    out = []
    n = len(forms)
    keys = [
        "filingDate",
        "accessionNumber",
        "primaryDocument",
        "primaryDocDescription",
        "items",
    ]
    cols = {k: recent.get(k, [""] * n) for k in keys}
    for i in range(n):
        if forms[i] != "8-K":
            continue
        fd = cols["filingDate"][i]
        if not fd or fd < date_min or fd > date_max:
            continue
        out.append(
            {
                "filing_date": fd,
                "accessionNumber": cols["accessionNumber"][i],
                "primaryDocument": cols["primaryDocument"][i],
                "primaryDocDescription": cols["primaryDocDescription"][i] or "",
                "items": cols["items"][i] or "",
            }
        )
    return out


def build_p2_signals() -> tuple[pd.DataFrame, float]:
    t0 = time.perf_counter()
    ohlcv = load_ohlcv()
    trades = load_trades()
    mmap = ohlcv[["sec_id", "ticker"]].drop_duplicates()
    max_d = ohlcv["trade_date"].max()
    date_max = max_d.strftime("%Y-%m-%d")
    date_min = (max_d - pd.Timedelta(days=90)).strftime("%Y-%m-%d")

    session = requests.Session()
    try:
        tmap = fetch_ticker_cik_map(session)
    except requests.RequestException:
        t0e = time.perf_counter() - t0
        empty = pd.DataFrame(
            columns=[
                "sec_id",
                "event_date",
                "event_type",
                "headline",
                "source_url",
                "pre_drift_flag",
                "suspicious_window_start",
                "remarks",
                "time_to_run",
            ]
        )
        return empty, t0e

    rows: list[dict] = []
    seen: set[tuple[int, str]] = set()

    for _, r in mmap.iterrows():
        sec_id = int(r["sec_id"])
        ticker = str(r["ticker"]).upper().strip()
        cik10 = tmap.get(ticker)
        if not cik10:
            continue
        try:
            sub = fetch_submissions(session, cik10)
        except requests.RequestException:
            time.sleep(0.15)
            continue
        time.sleep(0.12)
        if not sub:
            continue
        name = sub.get("name", ticker)
        hits = iter_recent_8k(sub, date_min, date_max)
        for h in hits:
            et = classify_8k(h["items"], h["primaryDocDescription"])
            if et == "other":
                continue
            fd = h["filing_date"]
            key = (sec_id, fd)
            if key in seen:
                continue
            seen.add(key)
            event_date = pd.to_datetime(fd).normalize()
            osec = ohlcv[ohlcv["sec_id"] == sec_id]
            vol_z, cum_ret = pre_event_metrics(osec, event_date)
            drift_flag = 0
            parts = []
            if pd.notna(vol_z) and vol_z > 2.5:
                drift_flag = 1
                parts.append(f"Volume z-score on T-1 vs prior 15 sessions ~{vol_z:.2f}.")
            if pd.notna(cum_ret) and cum_ret > 0.025:
                drift_flag = 1
                parts.append(f"Cumulative return T-5..T-1 ~{cum_ret*100:.2f}%.")
            if not parts:
                parts.append("No strong volume or return spike vs baseline in pre-window.")
            hpre = osec[osec["trade_date"] < event_date].sort_values("trade_date")
            suspicious_start = (
                hpre.iloc[-6]["trade_date"].strftime("%Y-%m-%d") if len(hpre) >= 6 else ""
            )
            ws = pd.Timestamp(suspicious_start) if suspicious_start else event_date - pd.Timedelta(days=7)
            parts.append(trade_evidence(trades, sec_id, ws, event_date))
            url = filing_url(cik10, h["accessionNumber"], h["primaryDocument"])
            headline = (h["primaryDocDescription"] or name)[:200]
            rows.append(
                {
                    "sec_id": sec_id,
                    "event_date": fd,
                    "event_type": et,
                    "headline": headline,
                    "source_url": url,
                    "pre_drift_flag": drift_flag,
                    "suspicious_window_start": suspicious_start,
                    "remarks": " ".join(parts),
                }
            )

    elapsed = time.perf_counter() - t0
    if not rows:
        df = pd.DataFrame(
            columns=[
                "sec_id",
                "event_date",
                "event_type",
                "headline",
                "source_url",
                "pre_drift_flag",
                "suspicious_window_start",
                "remarks",
                "time_to_run",
            ]
        )
        return df, elapsed
    df = pd.DataFrame(rows).drop_duplicates(subset=["sec_id", "event_date"])
    df["time_to_run"] = round(elapsed, 2)
    return df, elapsed
