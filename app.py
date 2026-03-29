#!/usr/bin/env python3
"""HITL Trade Surveillance Dashboard — Streamlit app for P3, P1, P2 review."""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
DATA_ROOT = Path(os.environ.get("DATA_ROOT", ROOT / "student-pack"))
FEEDBACK_DIR = ROOT / "feedback"
FEEDBACK_DIR.mkdir(exist_ok=True)
DECISIONS_PATH = FEEDBACK_DIR / "decisions.jsonl"

P3_TAXONOMY = [
    "wash_trading",
    "spoofing",
    "layering",
    "layering_echo",
    "pump_and_dump",
    "ramping",
    "peg_break",
    "peg_manipulation",
    "structuring",
    "aml_structuring",
    "threshold_testing",
    "coordinated_structuring",
    "chain_layering",
    "round_trip_wash",
    "wash_volume_at_peg",
    "placement_smurfing",
]

st.set_page_config(
    page_title="Trade Surveillance HITL",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Data loading helpers (cached)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading submission.csv ...")
def load_submission() -> pd.DataFrame:
    p = OUTPUTS / "submission.csv"
    if not p.exists():
        return pd.DataFrame(columns=["symbol", "date", "trade_id", "violation_type", "remarks"])
    return pd.read_csv(p)


@st.cache_data(show_spinner="Loading committee submission ...")
def load_committee_submission() -> pd.DataFrame | None:
    p = OUTPUTS / "submission_committee.csv"
    if not p.exists():
        return None
    return pd.read_csv(p)


@st.cache_data(show_spinner="Loading ground truth ...")
def load_ground_truth() -> pd.DataFrame | None:
    p = OUTPUTS / "ground_truth.csv"
    if not p.exists():
        return None
    return pd.read_csv(p)


@st.cache_data(show_spinner="Loading comparison report ...")
def load_comparison() -> pd.DataFrame | None:
    p = OUTPUTS / "comparison_report.csv"
    if not p.exists():
        return None
    return pd.read_csv(p)


@st.cache_data(show_spinner="Loading P1 alerts ...")
def load_p1_alerts() -> pd.DataFrame:
    p = OUTPUTS / "p1_alerts.csv"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p)


@st.cache_data(show_spinner="Loading P2 signals ...")
def load_p2_signals() -> pd.DataFrame:
    p = OUTPUTS / "p2_signals.csv"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p)


@st.cache_data(show_spinner="Loading crypto trades ...")
def load_crypto_trades() -> pd.DataFrame:
    trade_dir = DATA_ROOT / "crypto-trades"
    if not trade_dir.exists():
        return pd.DataFrame()
    parts = []
    for f in sorted(trade_dir.glob("*_trades.csv")):
        sym = f.stem.replace("_trades", "")
        df = pd.read_csv(f, parse_dates=["timestamp"])
        df["symbol"] = sym
        if "trader_id" in df.columns and "wallet_id" not in df.columns:
            df = df.rename(columns={"trader_id": "wallet_id"})
        df["notional_usdt"] = df["price"] * df["quantity"]
        df["minute"] = df["timestamp"].dt.floor("min")
        parts.append(df)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


@st.cache_data(show_spinner="Loading crypto market bars ...")
def load_crypto_bars() -> pd.DataFrame:
    mkt_dir = DATA_ROOT / "crypto-market"
    if not mkt_dir.exists():
        return pd.DataFrame()
    parts = []
    for f in sorted(mkt_dir.glob("Binance_*_minute.csv")):
        sym = f.stem.split("_")[1]
        df = pd.read_csv(f, parse_dates=["Date"])
        df["symbol"] = sym
        df["minute"] = df["Date"].dt.floor("min")
        parts.append(df)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


@st.cache_data(show_spinner="Loading equity market data ...")
def load_equity_market() -> pd.DataFrame:
    p = DATA_ROOT / "equity" / "market_data.csv"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, parse_dates=["timestamp"])


@st.cache_data(show_spinner="Loading equity trade data ...")
def load_equity_trades() -> pd.DataFrame:
    p = DATA_ROOT / "equity" / "trade_data.csv"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, parse_dates=["timestamp"])


@st.cache_data(show_spinner="Loading equity OHLCV ...")
def load_equity_ohlcv() -> pd.DataFrame:
    p = DATA_ROOT / "equity" / "ohlcv.csv"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, parse_dates=["trade_date"])


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

def init_p3_state(sub: pd.DataFrame) -> None:
    if "p3_decisions" not in st.session_state:
        st.session_state["p3_decisions"] = {}
    if "p3_edits" not in st.session_state:
        st.session_state["p3_edits"] = {}


def persist_decision(problem: str, row_id: str, action: str, **kwargs) -> None:
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "problem": problem,
        "row_id": row_id,
        "action": action,
        **kwargs,
    }
    with open(DECISIONS_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("Surveillance HITL")
    page = st.radio(
        "Navigate",
        ["P3 Crypto", "P1 Equity", "P2 SEC/Insider", "Comparison", "Audit Trail"],
        index=0,
    )
    st.divider()
    st.caption("BITS Hackathon 2026")
    st.caption("Powered by rule-based detectors + AI ground truth")


# ===================================================================
# PAGE: P3 CRYPTO
# ===================================================================

if page == "P3 Crypto":
    st.header("P3 — Crypto Trade Surveillance")

    sub_rules = load_submission()
    sub_committee = load_committee_submission()
    trades = load_crypto_trades()
    bars = load_crypto_bars()
    gt = load_ground_truth()

    source_options = ["Rules (submission.csv)"]
    if sub_committee is not None and not sub_committee.empty:
        source_options.append("Committee (submission_committee.csv)")
    data_source = st.radio("Submission source", source_options, horizontal=True)
    sub = sub_committee if "Committee" in data_source else sub_rules

    if sub is None or sub.empty:
        st.warning("No submission.csv found. Run `python run.py all` first.")
        st.stop()

    init_p3_state(sub)

    # --- Summary metrics ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Flags", len(sub))
    col2.metric("Symbols", sub["symbol"].nunique())
    col3.metric("Violation Types", sub["violation_type"].nunique())
    if gt is not None:
        gt_sus = gt[gt.get("verdict", pd.Series(dtype=str)) == "suspicious"] if "verdict" in gt.columns else gt
        col4.metric("GT Suspicious", len(gt_sus))
    else:
        col4.metric("GT Available", "No")

    # --- Violation type distribution ---
    st.subheader("Violation Type Distribution")
    vtype_counts = sub["violation_type"].value_counts().reset_index()
    vtype_counts.columns = ["violation_type", "count"]
    fig_vtype = px.bar(
        vtype_counts,
        x="violation_type",
        y="count",
        color="violation_type",
        title="Flags by Violation Type",
    )
    fig_vtype.update_layout(showlegend=False, height=350)
    st.plotly_chart(fig_vtype, use_container_width=True)

    # --- Symbol distribution ---
    col_a, col_b = st.columns(2)
    with col_a:
        sym_counts = sub["symbol"].value_counts().reset_index()
        sym_counts.columns = ["symbol", "count"]
        fig_sym = px.pie(sym_counts, names="symbol", values="count", title="Flags by Symbol")
        fig_sym.update_layout(height=320)
        st.plotly_chart(fig_sym, use_container_width=True)

    with col_b:
        cross = sub.groupby(["symbol", "violation_type"]).size().reset_index(name="count")
        fig_heat = px.density_heatmap(
            cross, x="symbol", y="violation_type", z="count",
            color_continuous_scale="YlOrRd", title="Symbol x Violation Heatmap",
        )
        fig_heat.update_layout(height=320)
        st.plotly_chart(fig_heat, use_container_width=True)

    st.divider()

    # --- Filters ---
    st.subheader("Review Queue")
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        sel_symbols = st.multiselect("Filter by Symbol", sorted(sub["symbol"].unique()), default=[])
    with fcol2:
        sel_vtypes = st.multiselect("Filter by Violation Type", sorted(sub["violation_type"].unique()), default=[])
    with fcol3:
        sel_decision = st.selectbox("Decision Status", ["All", "Pending", "Included", "Excluded"])

    filtered = sub.copy()
    if sel_symbols:
        filtered = filtered[filtered["symbol"].isin(sel_symbols)]
    if sel_vtypes:
        filtered = filtered[filtered["violation_type"].isin(sel_vtypes)]

    decisions = st.session_state.get("p3_decisions", {})
    if sel_decision == "Included":
        filtered = filtered[filtered["trade_id"].isin([k for k, v in decisions.items() if v == "include"])]
    elif sel_decision == "Excluded":
        filtered = filtered[filtered["trade_id"].isin([k for k, v in decisions.items() if v == "exclude"])]
    elif sel_decision == "Pending":
        decided = set(decisions.keys())
        filtered = filtered[~filtered["trade_id"].isin(decided)]

    st.caption(f"Showing {len(filtered)} of {len(sub)} flags")

    # --- Editable data table ---
    for idx, row in filtered.iterrows():
        tid = row["trade_id"]
        decision = decisions.get(tid, "pending")
        edit = st.session_state.get("p3_edits", {}).get(tid, {})

        status_icon = {"include": "**INCLUDE**", "exclude": "~~EXCLUDE~~", "pending": "PENDING"}[decision]
        with st.expander(f"{status_icon} | {tid} | {row['symbol']} | {row['violation_type']}"):
            ecol1, ecol2 = st.columns([2, 1])
            with ecol1:
                st.markdown(f"**Trade ID:** `{tid}`")
                st.markdown(f"**Symbol:** {row['symbol']} | **Date:** {row['date']}")
                st.markdown(f"**Violation Type:** {row['violation_type']}")
                st.markdown(f"**Remarks:** {row['remarks']}")

                # Trade context from raw data
                if not trades.empty:
                    trade_row = trades[trades["trade_id"] == tid]
                    if not trade_row.empty:
                        tr = trade_row.iloc[0]
                        st.markdown("---")
                        st.markdown("**Trade Context:**")
                        tcol1, tcol2, tcol3, tcol4 = st.columns(4)
                        tcol1.metric("Price", f"${tr['price']:.6f}")
                        tcol2.metric("Quantity", f"{tr['quantity']:.4f}")
                        tcol3.metric("Notional", f"${tr['notional_usdt']:.2f}")
                        tcol4.metric("Side", tr["side"])

                        # Bar context
                        if not bars.empty:
                            bar_row = bars[(bars["symbol"] == row["symbol"]) & (bars["minute"] == tr["minute"])]
                            if not bar_row.empty:
                                b = bar_row.iloc[0]
                                st.markdown("**Bar Context (1m):**")
                                bcol1, bcol2, bcol3, bcol4 = st.columns(4)
                                bcol1.metric("Open", f"${b['Open']:.6f}")
                                bcol2.metric("High", f"${b['High']:.6f}")
                                bcol3.metric("Low", f"${b['Low']:.6f}")
                                bcol4.metric("Close", f"${b['Close']:.6f}")
                                mid = (b["High"] + b["Low"]) / 2
                                if mid > 0:
                                    dev_bps = abs(tr["price"] - mid) / mid * 10000
                                    st.metric("Price vs Mid (bps)", f"{dev_bps:.1f}")

                        # Wallet activity summary
                        wallet = tr.get("wallet_id", "")
                        if wallet and not trades.empty:
                            w_trades = trades[trades["wallet_id"] == wallet]
                            st.markdown(f"**Wallet `{wallet}` Activity:** {len(w_trades)} total trades, "
                                        f"${w_trades['notional_usdt'].sum():.2f} total notional, "
                                        f"{w_trades['symbol'].nunique()} symbols")

                # GT verdict if available
                if gt is not None and "trade_id" in gt.columns:
                    gt_row = gt[gt["trade_id"] == tid]
                    if not gt_row.empty:
                        g = gt_row.iloc[0]
                        st.markdown("---")
                        st.markdown("**AI Ground Truth Verdict:**")
                        verdict = g.get("verdict", "n/a")
                        conf = g.get("confidence", "n/a")
                        color = "green" if verdict == "suspicious" else ("red" if verdict == "benign" else "orange")
                        st.markdown(f":{color}[{verdict}] (confidence: {conf})")
                        if "rationale" in g.index:
                            st.markdown(f"*{g['rationale']}*")

            with ecol2:
                st.markdown("**Actions:**")
                new_vtype = st.selectbox(
                    "Edit Violation Type",
                    P3_TAXONOMY,
                    index=P3_TAXONOMY.index(edit.get("violation_type", row["violation_type"]))
                    if edit.get("violation_type", row["violation_type"]) in P3_TAXONOMY
                    else 0,
                    key=f"vtype_{tid}",
                )
                new_remarks = st.text_area(
                    "Edit Remarks",
                    value=edit.get("remarks", row["remarks"]),
                    height=100,
                    key=f"remarks_{tid}",
                )

                bcol1, bcol2 = st.columns(2)
                with bcol1:
                    if st.button("Include", key=f"inc_{tid}", type="primary"):
                        st.session_state["p3_decisions"][tid] = "include"
                        st.session_state.setdefault("p3_edits", {})[tid] = {
                            "violation_type": new_vtype,
                            "remarks": new_remarks,
                        }
                        persist_decision("P3", tid, "include",
                                         violation_type=new_vtype, remarks=new_remarks)
                        st.rerun()
                with bcol2:
                    if st.button("Exclude", key=f"exc_{tid}"):
                        st.session_state["p3_decisions"][tid] = "exclude"
                        persist_decision("P3", tid, "exclude")
                        st.rerun()

                if decision != "pending":
                    if st.button("Reset to Pending", key=f"reset_{tid}"):
                        st.session_state["p3_decisions"].pop(tid, None)
                        st.session_state.get("p3_edits", {}).pop(tid, None)
                        persist_decision("P3", tid, "reset")
                        st.rerun()

    st.divider()

    # --- Export ---
    st.subheader("Export Curated Submission")
    ecol1, ecol2 = st.columns(2)
    with ecol1:
        n_included = sum(1 for v in decisions.values() if v == "include")
        n_excluded = sum(1 for v in decisions.values() if v == "exclude")
        n_pending = len(sub) - n_included - n_excluded
        st.markdown(f"**Included:** {n_included} | **Excluded:** {n_excluded} | **Pending:** {n_pending}")
        export_mode = st.radio(
            "Export includes:",
            ["Included + Pending (conservative)", "Included only (strict)"],
            index=0,
        )

    with ecol2:
        if st.button("Generate Export", type="primary"):
            export_df = sub.copy()
            edits = st.session_state.get("p3_edits", {})
            for tid, ed in edits.items():
                mask = export_df["trade_id"] == tid
                if "violation_type" in ed:
                    export_df.loc[mask, "violation_type"] = ed["violation_type"]
                if "remarks" in ed:
                    export_df.loc[mask, "remarks"] = ed["remarks"]

            if export_mode == "Included only (strict)":
                keep = {k for k, v in decisions.items() if v == "include"}
                export_df = export_df[export_df["trade_id"].isin(keep)]
            else:
                exclude = {k for k, v in decisions.items() if v == "exclude"}
                export_df = export_df[~export_df["trade_id"].isin(exclude)]

            csv_data = export_df.to_csv(index=False)
            st.download_button(
                "Download submission_curated.csv",
                csv_data,
                file_name="submission_curated.csv",
                mime="text/csv",
            )
            st.success(f"Export ready: {len(export_df)} rows")


# ===================================================================
# PAGE: P1 EQUITY
# ===================================================================

elif page == "P1 Equity":
    st.header("P1 — Equity Order Book Surveillance")

    alerts = load_p1_alerts()
    eq_mkt = load_equity_market()
    eq_trd = load_equity_trades()

    if alerts.empty:
        st.warning("No p1_alerts.csv found. Run `python run.py all` first.")
        st.stop()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Alerts", len(alerts))
    col2.metric("Securities", alerts["sec_id"].nunique())
    if "severity" in alerts.columns:
        col3.metric("HIGH Severity", (alerts["severity"] == "HIGH").sum())

    # Severity distribution
    if "severity" in alerts.columns:
        sev_counts = alerts["severity"].value_counts().reset_index()
        sev_counts.columns = ["severity", "count"]
        fig_sev = px.bar(sev_counts, x="severity", y="count", color="severity",
                         color_discrete_map={"HIGH": "#e74c3c", "MEDIUM": "#f39c12", "LOW": "#2ecc71"},
                         title="Alerts by Severity")
        fig_sev.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig_sev, use_container_width=True)

    st.divider()
    st.subheader("Alert Review")

    # Filters
    fcol1, fcol2 = st.columns(2)
    with fcol1:
        sel_sec = st.multiselect("Filter by sec_id", sorted(alerts["sec_id"].unique()), default=[])
    with fcol2:
        sel_atype = st.multiselect("Filter by Anomaly Type",
                                   sorted(alerts["anomaly_type"].unique()) if "anomaly_type" in alerts.columns else [],
                                   default=[])

    filt = alerts.copy()
    if sel_sec:
        filt = filt[filt["sec_id"].isin(sel_sec)]
    if sel_atype:
        filt = filt[filt["anomaly_type"].isin(sel_atype)]

    for _, row in filt.iterrows():
        aid = row.get("alert_id", "?")
        sec = row["sec_id"]
        atype = row.get("anomaly_type", "")
        sev = row.get("severity", "")
        sev_color = {"HIGH": "red", "MEDIUM": "orange"}.get(sev, "blue")

        with st.expander(f"Alert {aid} | sec_id {sec} | :{sev_color}[{sev}] | {atype}"):
            st.markdown(f"**Date:** {row.get('trade_date', '')} | **Window Start:** {row.get('time_window_start', '')}")
            st.markdown(f"**Remarks:** {row.get('remarks', '')}")

            if not eq_mkt.empty:
                sec_mkt = eq_mkt[eq_mkt["sec_id"] == sec].copy()
                if not sec_mkt.empty:
                    td = row.get("trade_date", "")
                    if td:
                        day_mkt = sec_mkt[sec_mkt["timestamp"].dt.strftime("%Y-%m-%d") == td]
                        if not day_mkt.empty and "timestamp" in day_mkt.columns:
                            day_mkt = day_mkt.sort_values("timestamp")
                            bid_cols = [c for c in day_mkt.columns if c.startswith("bid_size_level")]
                            ask_cols = [c for c in day_mkt.columns if c.startswith("ask_size_level")]
                            if bid_cols:
                                day_mkt["total_bid"] = day_mkt[bid_cols].sum(axis=1)
                                day_mkt["total_ask"] = day_mkt[ask_cols].sum(axis=1)
                                tot = day_mkt["total_bid"] + day_mkt["total_ask"]
                                day_mkt["obi"] = np.where(tot > 0, (day_mkt["total_bid"] - day_mkt["total_ask"]) / tot, 0)

                                fig_obi = go.Figure()
                                fig_obi.add_trace(go.Scatter(
                                    x=day_mkt["timestamp"], y=day_mkt["obi"],
                                    mode="lines", name="OBI",
                                ))
                                ws = row.get("time_window_start", "")
                                if ws:
                                    try:
                                        alert_ts = pd.Timestamp(f"{td} {ws}")
                                        fig_obi.add_vline(x=alert_ts, line_dash="dash", line_color="red",
                                                          annotation_text="Alert")
                                    except Exception:
                                        pass
                                fig_obi.update_layout(title=f"OBI for sec_id {sec} on {td}", height=280,
                                                      yaxis_title="Order Book Imbalance")
                                st.plotly_chart(fig_obi, use_container_width=True)

            if not eq_trd.empty:
                sec_trades = eq_trd[(eq_trd["sec_id"] == sec)].copy()
                td = row.get("trade_date", "")
                if td and not sec_trades.empty:
                    day_trades = sec_trades[sec_trades["timestamp"].dt.strftime("%Y-%m-%d") == td]
                    if not day_trades.empty:
                        st.markdown(f"**Trade Activity:** {len(day_trades)} rows on {td}")
                        st.dataframe(
                            day_trades[["timestamp", "side", "quantity", "price", "order_status", "trader_id"]].head(20),
                            use_container_width=True,
                            hide_index=True,
                        )

    # Export
    st.divider()
    csv_p1 = alerts.to_csv(index=False)
    st.download_button("Download p1_alerts.csv", csv_p1, file_name="p1_alerts.csv", mime="text/csv")


# ===================================================================
# PAGE: P2 SEC/INSIDER
# ===================================================================

elif page == "P2 SEC/Insider":
    st.header("P2 — SEC 8-K / Pre-Announcement Drift")

    signals = load_p2_signals()
    ohlcv = load_equity_ohlcv()

    if signals.empty:
        st.warning("No p2_signals.csv found. Run `python run.py all` first.")
        st.stop()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Signals", len(signals))
    col2.metric("Securities", signals["sec_id"].nunique())
    if "pre_drift_flag" in signals.columns:
        col3.metric("Pre-Drift Flagged", int(signals["pre_drift_flag"].sum()))

    # Event type distribution
    if "event_type" in signals.columns:
        et_counts = signals["event_type"].value_counts().reset_index()
        et_counts.columns = ["event_type", "count"]
        fig_et = px.bar(et_counts, x="event_type", y="count", color="event_type",
                        title="Signals by Event Type")
        fig_et.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig_et, use_container_width=True)

    st.divider()
    st.subheader("Signal Review")

    fcol1, fcol2 = st.columns(2)
    with fcol1:
        sel_et = st.multiselect("Filter by Event Type",
                                sorted(signals["event_type"].unique()) if "event_type" in signals.columns else [],
                                default=[])
    with fcol2:
        sel_drift = st.selectbox("Pre-Drift Flag", ["All", "Flagged Only", "Not Flagged"])

    filt = signals.copy()
    if sel_et:
        filt = filt[filt["event_type"].isin(sel_et)]
    if sel_drift == "Flagged Only" and "pre_drift_flag" in filt.columns:
        filt = filt[filt["pre_drift_flag"] == 1]
    elif sel_drift == "Not Flagged" and "pre_drift_flag" in filt.columns:
        filt = filt[filt["pre_drift_flag"] == 0]

    for _, row in filt.iterrows():
        sec = row["sec_id"]
        et = row.get("event_type", "")
        drift = row.get("pre_drift_flag", 0)
        drift_icon = "**DRIFT**" if drift else ""

        with st.expander(f"sec_id {sec} | {row.get('event_date', '')} | {et} {drift_icon}"):
            st.markdown(f"**Headline:** {row.get('headline', '')}")
            url = row.get("source_url", "")
            if url:
                st.markdown(f"**Filing:** [{url}]({url})")
            st.markdown(f"**Event Date:** {row.get('event_date', '')} | "
                        f"**Suspicious Window Start:** {row.get('suspicious_window_start', 'n/a')}")
            st.markdown(f"**Remarks:** {row.get('remarks', '')}")

            if not ohlcv.empty:
                sec_ohlcv = ohlcv[ohlcv["sec_id"] == sec].sort_values("trade_date")
                if not sec_ohlcv.empty:
                    fig_px = go.Figure()
                    fig_px.add_trace(go.Candlestick(
                        x=sec_ohlcv["trade_date"],
                        open=sec_ohlcv["open"], high=sec_ohlcv["high"],
                        low=sec_ohlcv["low"], close=sec_ohlcv["close"],
                        name="OHLC",
                    ))
                    ev_date = row.get("event_date", "")
                    if ev_date:
                        try:
                            fig_px.add_vline(x=pd.Timestamp(ev_date), line_dash="dash",
                                             line_color="red", annotation_text="Event")
                        except Exception:
                            pass
                    ws = row.get("suspicious_window_start", "")
                    if ws:
                        try:
                            fig_px.add_vline(x=pd.Timestamp(ws), line_dash="dot",
                                             line_color="orange", annotation_text="Window Start")
                        except Exception:
                            pass
                    fig_px.update_layout(title=f"OHLCV for sec_id {sec}", height=350,
                                         xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig_px, use_container_width=True)

                    vol_fig = px.bar(sec_ohlcv, x="trade_date", y="volume", title="Volume")
                    vol_fig.update_layout(height=200)
                    st.plotly_chart(vol_fig, use_container_width=True)

    st.divider()
    csv_p2 = signals.to_csv(index=False)
    st.download_button("Download p2_signals.csv", csv_p2, file_name="p2_signals.csv", mime="text/csv")


# ===================================================================
# PAGE: COMPARISON
# ===================================================================

elif page == "Comparison":
    st.header("Comparison — Rules vs AI Ground Truth")

    comp = load_comparison()
    gt = load_ground_truth()

    if comp is None and gt is None:
        st.info("No comparison_report.csv or ground_truth.csv found yet. "
                "Run the AI ground-truth agent (Plan 2) to generate these files.")
        st.markdown("**Expected files:**")
        st.markdown("- `ground_truth.csv` — AI verdicts for all trades")
        st.markdown("- `comparison_report.csv` — Rules vs AI agreement matrix")
        st.stop()

    if gt is not None:
        st.subheader("Ground Truth Summary")
        if "verdict" in gt.columns:
            v_counts = gt["verdict"].value_counts()
            gcol1, gcol2, gcol3 = st.columns(3)
            gcol1.metric("Suspicious", int(v_counts.get("suspicious", 0)))
            gcol2.metric("Benign", int(v_counts.get("benign", 0)))
            gcol3.metric("Uncertain", int(v_counts.get("uncertain", 0)))

            fig_gt = px.pie(
                v_counts.reset_index(),
                names="verdict", values="count",
                title="Ground Truth Verdict Distribution",
                color="verdict",
                color_discrete_map={"suspicious": "#e74c3c", "benign": "#2ecc71", "uncertain": "#f39c12"},
            )
            st.plotly_chart(fig_gt, use_container_width=True)

        if "violation_type" in gt.columns:
            gt_types = gt[gt.get("verdict", pd.Series(dtype=str)) == "suspicious"]["violation_type"].value_counts()
            if not gt_types.empty:
                st.subheader("GT Violation Types (Suspicious Only)")
                st.bar_chart(gt_types)

    if comp is not None:
        st.subheader("Agreement Matrix")
        if "agreement" in comp.columns:
            ag_counts = comp["agreement"].value_counts().reset_index()
            ag_counts.columns = ["category", "count"]
            color_map = {
                "both_flag": "#2ecc71",
                "rules_only": "#e74c3c",
                "gt_only": "#3498db",
                "neither": "#95a5a6",
            }
            fig_ag = px.bar(ag_counts, x="category", y="count", color="category",
                            color_discrete_map=color_map,
                            title="Agreement Categories")
            fig_ag.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig_ag, use_container_width=True)

            # Per-symbol breakdown
            if "symbol" in comp.columns:
                sym_ag = comp.groupby(["symbol", "agreement"]).size().reset_index(name="count")
                fig_sym_ag = px.bar(sym_ag, x="symbol", y="count", color="agreement",
                                    color_discrete_map=color_map, barmode="group",
                                    title="Agreement by Symbol")
                fig_sym_ag.update_layout(height=350)
                st.plotly_chart(fig_sym_ag, use_container_width=True)

        # Disagreement drill-down
        st.subheader("Disagreement Drill-Down")
        tab1, tab2 = st.tabs(["GT-Only (Missed by Rules)", "Rules-Only (Possible FP)"])

        with tab1:
            gt_only = comp[comp["agreement"] == "gt_only"].copy() if "agreement" in comp.columns else pd.DataFrame()
            if gt_only.empty:
                st.info("No GT-only rows (rules caught everything GT flagged).")
            else:
                if "gt_confidence" in gt_only.columns:
                    gt_only = gt_only.sort_values("gt_confidence", ascending=False)
                st.dataframe(gt_only.head(30), use_container_width=True, hide_index=True)

        with tab2:
            rules_only = comp[comp["agreement"] == "rules_only"].copy() if "agreement" in comp.columns else pd.DataFrame()
            if rules_only.empty:
                st.info("No rules-only rows (all rule flags matched GT).")
            else:
                if "gt_confidence" in rules_only.columns:
                    rules_only = rules_only.sort_values("gt_confidence", ascending=True)
                st.dataframe(rules_only.head(30), use_container_width=True, hide_index=True)


# ===================================================================
# PAGE: AUDIT TRAIL
# ===================================================================

elif page == "Audit Trail":
    st.header("Audit Trail — Decision Log")

    if DECISIONS_PATH.exists():
        entries = []
        with open(DECISIONS_PATH) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

        if entries:
            df_audit = pd.DataFrame(entries)
            st.metric("Total Decisions", len(df_audit))

            if "action" in df_audit.columns:
                act_counts = df_audit["action"].value_counts().reset_index()
                act_counts.columns = ["action", "count"]
                fig_act = px.bar(act_counts, x="action", y="count", color="action",
                                 title="Decision Actions")
                fig_act.update_layout(height=250, showlegend=False)
                st.plotly_chart(fig_act, use_container_width=True)

            st.subheader("Full Log")
            st.dataframe(df_audit, use_container_width=True, hide_index=True)

            # Export
            audit_json = json.dumps(entries, indent=2)
            st.download_button(
                "Download Audit JSON",
                audit_json,
                file_name="audit_trail.json",
                mime="application/json",
            )
        else:
            st.info("No decisions recorded yet. Review flags in the P3 tab to start.")
    else:
        st.info("No decisions recorded yet. Review flags in the P3 tab to start.")

    st.divider()
    st.subheader("Session State Summary")
    p3_dec = st.session_state.get("p3_decisions", {})
    if p3_dec:
        inc = sum(1 for v in p3_dec.values() if v == "include")
        exc = sum(1 for v in p3_dec.values() if v == "exclude")
        st.markdown(f"**P3 Session:** {inc} included, {exc} excluded, {len(p3_dec)} total decisions")
    else:
        st.markdown("No P3 decisions in current session.")
