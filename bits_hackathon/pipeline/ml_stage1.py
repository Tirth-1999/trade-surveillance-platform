"""Stage-1 binary suspicious classifier: HistGradientBoosting + calibration + artifacts."""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    fbeta_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

from bits_hackathon.core.config import get as cfg
from bits_hackathon.core.paths import ARTIFACTS_DIR, OUTPUTS_DIR
from bits_hackathon.pipeline.labels import build_per_trade_labels, build_training_snapshot
from bits_hackathon.pipeline.ml_data_checks import validate_crypto_frames
from bits_hackathon.pipeline.ml_features import FEATURE_COLS, engineer_features

STAGE1_MODEL = "stage1_model.joblib"
STAGE1_SCALER = "stage1_scaler.joblib"
STAGE1_META = "stage1_meta.json"


def _artifact_paths(root: Path | None = None) -> tuple[Path, Path, Path]:
    r = root or ARTIFACTS_DIR
    return r / STAGE1_MODEL, r / STAGE1_SCALER, r / STAGE1_META


def _data_fingerprint(trades: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(str(len(trades)).encode())
    h.update(str(sorted(trades["trade_id"].astype(str).head(500).tolist())).encode())
    return h.hexdigest()[:16]


def train_stage1(
    trades: pd.DataFrame,
    markets: pd.DataFrame,
    *,
    artifacts_dir: Path | None = None,
    comparison_path: str | None = None,
    ground_truth_path: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any], str]:
    """Train calibrated binary classifier; save artifacts; return (trades_scored, meta_dict, report)."""
    import joblib

    checks = validate_crypto_frames(trades, markets)
    trades_feat, feature_cols = engineer_features(trades, markets)
    labels_df = build_per_trade_labels(trades_feat, comparison_path, ground_truth_path)
    merged = trades_feat.merge(labels_df, on="trade_id", how="left")
    merged["label_binary"] = merged["label_binary"].fillna(0).astype(int)
    merged["label_weight"] = merged["label_weight"].fillna(float(cfg("ml.labels.weight_uncertain")))

    if bool(cfg("ml.labels.drop_uncertain_training")):
        drop_band = merged["pseudo_confidence_band"] == "uncertain"
        merged.loc[drop_band, "label_weight"] = 0.0

    build_training_snapshot(
        trades_feat,
        feature_cols,
        comparison_path,
        ground_truth_path,
    )

    X_df = merged[feature_cols].fillna(0)
    X = X_df.values
    y = merged["label_binary"].values
    sw = merged["label_weight"].values.astype(float)

    dates = pd.to_datetime(merged["trade_date"])
    unique_dates = sorted(dates.unique())
    frac = float(cfg("ml.stage1.train_fraction_by_date"))
    split_idx = max(0, int(len(unique_dates) * frac) - 1)
    split_date = unique_dates[split_idx]
    train_mask = dates <= split_date
    test_mask = dates > split_date

    X_train, y_train, sw_train = X[train_mask], y[train_mask], sw[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    X_all_s = scaler.transform(X)

    base = HistGradientBoostingClassifier(
        max_depth=int(cfg("ml.stage1.max_depth")),
        learning_rate=float(cfg("ml.stage1.learning_rate")),
        max_iter=int(cfg("ml.stage1.max_iter")),
        min_samples_leaf=int(cfg("ml.stage1.min_samples_leaf")),
        random_state=42,
    )
    cal_method = str(cfg("ml.stage1.calibration_method"))
    if cal_method not in ("isotonic", "sigmoid"):
        cal_method = "isotonic"

    calibrated = CalibratedClassifierCV(base, method=cal_method, cv=3)
    calibrated.fit(X_train_s, y_train, sample_weight=sw_train)

    probs_train = calibrated.predict_proba(X_train_s)[:, 1]
    probs_test = calibrated.predict_proba(X_test_s)[:, 1]
    probs_all = calibrated.predict_proba(X_all_s)[:, 1]

    metric = str(cfg("ml.stage1.threshold_metric")).lower().strip()
    prec_floor = float(cfg("ml.stage1.min_precision_floor"))
    best_any_score = -1.0
    best_any_thr = 0.5
    best_floor_score = -1.0
    best_floor_thr: float | None = None
    for thr in np.arange(0.05, 0.95, 0.02):
        preds = (probs_test >= thr).astype(int)
        if preds.sum() == 0 or y_test.sum() == 0:
            continue
        prec = precision_score(y_test, preds, zero_division=0)
        rec = recall_score(y_test, preds, zero_division=0)
        if metric in ("f05", "f_beta_half", "fbeta_half"):
            score = float(fbeta_score(y_test, preds, beta=0.5, zero_division=0))
        elif metric in ("hackathon_proxy", "hackathon"):
            tp = int(np.logical_and(y_test == 1, preds == 1).sum())
            fp = int(np.logical_and(y_test == 0, preds == 1).sum())
            score = float(5 * tp - 2 * fp)
        else:
            score = prec * 2.0 + rec
        if score > best_any_score:
            best_any_score = score
            best_any_thr = float(thr)
        if prec >= prec_floor and score > best_floor_score:
            best_floor_score = score
            best_floor_thr = float(thr)
    best_thr = best_floor_thr if best_floor_thr is not None else best_any_thr

    merged["p_suspicious"] = probs_all
    merged["ml_flag"] = (merged["p_suspicious"] >= best_thr).astype(int)

    brier_test = brier_score_loss(y_test, probs_test) if len(y_test) else 0.0
    pr_auc = (
        average_precision_score(y_test, probs_test) if y_test.sum() > 0 and (1 - y_test).sum() > 0 else 0.0
    )

    meta: dict[str, Any] = {
        "version": 1,
        "data_validation_issues": checks,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "model": "HistGradientBoostingClassifier + CalibratedClassifierCV",
        "calibration_method": cal_method,
        "feature_cols": feature_cols,
        "threshold": best_thr,
        "threshold_metric": metric,
        "threshold_precision_floor": prec_floor,
        "train_rows": int(train_mask.sum()),
        "test_rows": int(test_mask.sum()),
        "positive_rate_train": float(y_train.mean()),
        "positive_rate_test": float(y_test.mean()) if len(y_test) else 0.0,
        "brier_test": float(brier_test),
        "pr_auc_test": float(pr_auc),
        "data_fingerprint": _data_fingerprint(trades),
    }

    if y_test.sum() > 0:
        pt = (probs_test >= best_thr).astype(int)
        meta["test_precision"] = float(precision_score(y_test, pt, zero_division=0))
        meta["test_recall"] = float(recall_score(y_test, pt, zero_division=0))
        meta["test_f1"] = float(f1_score(y_test, pt, zero_division=0))
        try:
            meta["test_roc_auc"] = float(roc_auc_score(y_test, probs_test))
        except ValueError:
            meta["test_roc_auc"] = 0.0
    else:
        meta["test_precision"] = meta["test_recall"] = meta["test_f1"] = meta["test_roc_auc"] = 0.0

    art = artifacts_dir or ARTIFACTS_DIR
    art.mkdir(parents=True, exist_ok=True)
    mpath, spath, jpath = _artifact_paths(art)
    joblib.dump(calibrated, mpath)
    joblib.dump(scaler, spath)
    jpath.write_text(json.dumps(meta, indent=2))

    report_lines = [
        "=" * 60,
        "STAGE-1 ML REPORT (binary triage)",
        "=" * 60,
    ]
    if checks:
        report_lines.append("Data validation warnings:")
        for c in checks:
            report_lines.append(f"  - {c}")
        report_lines.append("")
    report_lines += [
        f"Calibration: {cal_method}",
        f"Train / test rows: {train_mask.sum()} / {test_mask.sum()}",
        f"Best threshold: {best_thr:.3f}",
        f"Test Brier: {brier_test:.4f}  PR-AUC: {pr_auc:.4f}",
        f"Test precision / recall / F1: {meta.get('test_precision', 0):.4f} / "
        f"{meta.get('test_recall', 0):.4f} / {meta.get('test_f1', 0):.4f}",
        f"Precision: {meta.get('test_precision', 0):.4f}",
        f"Recall:    {meta.get('test_recall', 0):.4f}",
        f"F1:        {meta.get('test_f1', 0):.4f}",
        f"AUC:       {meta.get('test_roc_auc', 0):.4f}",
        f"ML-flagged (all data): {int(merged['ml_flag'].sum())} / {len(merged)}",
        f"Artifacts: {mpath}, {spath}, {jpath}",
    ]
    return merged, meta, "\n".join(report_lines)


def load_stage1_artifacts(artifacts_dir: Path | None = None) -> tuple[Any, Any, dict]:
    import joblib

    mpath, spath, jpath = _artifact_paths(artifacts_dir)
    if not mpath.exists() or not spath.exists() or not jpath.exists():
        raise FileNotFoundError(
            f"Missing stage-1 artifacts under {mpath.parent}. Run: python run.py train-ml"
        )
    model = joblib.load(mpath)
    scaler = joblib.load(spath)
    meta = json.loads(jpath.read_text())
    return model, scaler, meta


def infer_stage1(
    trades: pd.DataFrame,
    markets: pd.DataFrame,
    *,
    artifacts_dir: Path | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Score all trades with saved stage-1 model."""
    trades_feat, feature_cols = engineer_features(trades, markets)
    model, scaler, meta = load_stage1_artifacts(artifacts_dir)
    stored_cols = meta.get("feature_cols", feature_cols)
    for c in stored_cols:
        if c not in trades_feat.columns:
            trades_feat[c] = 0.0
    X = trades_feat[stored_cols].fillna(0).values
    Xs = scaler.transform(X)
    probs = model.predict_proba(Xs)[:, 1]
    thr = float(meta.get("threshold", 0.5))
    trades_feat["p_suspicious"] = probs
    trades_feat["ml_flag"] = (trades_feat["p_suspicious"] >= thr).astype(int)
    return trades_feat, meta

