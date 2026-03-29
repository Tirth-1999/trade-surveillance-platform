"""ML re-ranker: train a classifier on ground-truth labels, re-score all trades."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

from bits_hackathon.core.paths import ROOT, OUTPUTS_DIR


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def engineer_features(
    trades: pd.DataFrame,
    markets: pd.DataFrame,
) -> pd.DataFrame:
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
        (trades["price"] - trades["bar_mid"]).abs()
        / trades["bar_mid"].replace(0, np.nan) * 10000
    )
    trades["bar_volume_ratio"] = (
        trades["notional_usdt"] / trades["bar_volume"].replace(0, np.nan)
    )

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

    feature_cols = [
        "notional_zscore", "price_vs_mid_bps", "wallet_trade_count",
        "wallet_total_notional", "time_gap_same_wallet", "bar_volume_ratio",
        "bar_tradecount", "minute_peer_count", "minute_peer_notional",
        "is_stablecoin", "price_vs_peg_bps", "hour_of_day", "notional_vs_threshold",
    ]

    for c in feature_cols:
        if c not in trades.columns:
            trades[c] = 0.0

    return trades, feature_cols


# ---------------------------------------------------------------------------
# Label creation from comparison
# ---------------------------------------------------------------------------

def create_labels(
    trades: pd.DataFrame,
    comparison_path: str | None = None,
) -> pd.Series:
    comp_path = comparison_path or str(OUTPUTS_DIR / "comparison_report.csv")
    comp = pd.read_csv(comp_path)
    comp["gt_confidence"] = pd.to_numeric(comp["gt_confidence"], errors="coerce")

    label_map: dict[str, int] = {}

    both = comp[comp["agreement"] == "both_flag"]
    for tid in both["trade_id"]:
        label_map[tid] = 1

    gt_only = comp[comp["agreement"] == "gt_only"]
    for _, r in gt_only.iterrows():
        if pd.notna(r["gt_confidence"]) and r["gt_confidence"] >= 0.7:
            label_map[r["trade_id"]] = 1

    rules_only = comp[comp["agreement"] == "rules_only"]
    for _, r in rules_only.iterrows():
        if pd.notna(r["gt_confidence"]) and r["gt_confidence"] < 0.3:
            label_map[r["trade_id"]] = 0
        else:
            label_map[r["trade_id"]] = 1

    labels = trades["trade_id"].map(label_map).fillna(0).astype(int)
    return labels


# ---------------------------------------------------------------------------
# Train and predict
# ---------------------------------------------------------------------------

def train_and_predict(
    trades: pd.DataFrame,
    markets: pd.DataFrame,
    comparison_path: str | None = None,
) -> tuple[pd.DataFrame, str]:
    trades_feat, feature_cols = engineer_features(trades, markets)
    labels = create_labels(trades_feat, comparison_path)

    X = trades_feat[feature_cols].fillna(0).values
    y = labels.values

    dates = pd.to_datetime(trades_feat["trade_date"])
    unique_dates = sorted(dates.unique())
    split_idx = int(len(unique_dates) * 0.8)
    split_date = unique_dates[split_idx]
    train_mask = dates <= split_date
    test_mask = dates > split_date

    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = GradientBoostingClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.1,
        subsample=0.8, random_state=42,
    )
    model.fit(X_train_s, y_train)

    X_all_s = scaler.transform(X)
    probs = model.predict_proba(X_all_s)[:, 1]
    trades_feat["p_suspicious"] = probs

    best_threshold = 0.5
    best_score = -1
    for thr in np.arange(0.1, 0.9, 0.02):
        preds = (probs[test_mask] >= thr).astype(int)
        if preds.sum() == 0:
            continue
        prec = precision_score(y_test, preds, zero_division=0)
        rec = recall_score(y_test, preds, zero_division=0)
        score = prec * 2 + rec
        if score > best_score:
            best_score = score
            best_threshold = thr

    trades_feat["ml_flag"] = (trades_feat["p_suspicious"] >= best_threshold).astype(int)

    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("ML RE-RANKER REPORT")
    report_lines.append("=" * 60)
    report_lines.append(f"\nModel: GradientBoostingClassifier (200 trees, depth=4)")
    report_lines.append(f"Train size: {train_mask.sum()}, Test size: {test_mask.sum()}")
    report_lines.append(f"Positive labels: {y.sum()} / {len(y)}")
    report_lines.append(f"Best threshold: {best_threshold:.2f}")

    test_preds = (probs[test_mask] >= best_threshold).astype(int)
    if y_test.sum() > 0:
        prec = precision_score(y_test, test_preds, zero_division=0)
        rec = recall_score(y_test, test_preds, zero_division=0)
        f1 = f1_score(y_test, test_preds, zero_division=0)
        try:
            auc = roc_auc_score(y_test, probs[test_mask])
        except ValueError:
            auc = 0.0
        report_lines.append(f"\nTest metrics:")
        report_lines.append(f"  Precision: {prec:.4f}")
        report_lines.append(f"  Recall:    {rec:.4f}")
        report_lines.append(f"  F1:        {f1:.4f}")
        report_lines.append(f"  AUC:       {auc:.4f}")

    report_lines.append(f"\nFeature importances:")
    importances = sorted(
        zip(feature_cols, model.feature_importances_),
        key=lambda x: -x[1],
    )
    for name, imp in importances:
        report_lines.append(f"  {name:30s}: {imp:.4f}")

    flagged = trades_feat[trades_feat["ml_flag"] == 1]
    report_lines.append(f"\nML-flagged trades: {len(flagged)}")
    report_lines.append(f"Total trades:      {len(trades_feat)}")

    report_text = "\n".join(report_lines)
    return trades_feat, report_text


def build_ml_submission(
    trades_feat: pd.DataFrame,
    gt_path: str | None = None,
) -> pd.DataFrame:
    gt = pd.read_csv(gt_path or str(OUTPUTS_DIR / "ground_truth.csv"))
    gt_sus = gt[gt["verdict"] == "suspicious"][["trade_id", "violation_type", "remark_draft"]]
    gt_lookup = gt_sus.set_index("trade_id").to_dict("index")

    flagged = trades_feat[trades_feat["ml_flag"] == 1].copy()
    flagged = flagged.sort_values("p_suspicious", ascending=False)

    rows = []
    for _, r in flagged.iterrows():
        tid = r["trade_id"]
        gt_info = gt_lookup.get(tid, {})
        vtype = gt_info.get("violation_type", "anomaly")
        remark = gt_info.get("remark_draft", f"ML flagged (p={r['p_suspicious']:.3f})")
        if not vtype:
            vtype = "anomaly"
        rows.append({
            "symbol": r["symbol"],
            "date": r["trade_date"],
            "trade_id": tid,
            "violation_type": vtype,
            "remarks": remark,
        })

    return pd.DataFrame(rows)
