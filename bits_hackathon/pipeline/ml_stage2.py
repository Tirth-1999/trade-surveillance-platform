"""Stage-2 multiclass violation-type classifier on suspicious candidates."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import f1_score, log_loss
from sklearn.preprocessing import LabelEncoder, StandardScaler

from bits_hackathon.core.config import get as cfg
from bits_hackathon.core.paths import ARTIFACTS_DIR
from bits_hackathon.pipeline.ml_features import FEATURE_COLS

STAGE2_MODEL = "stage2_model.joblib"
STAGE2_ENCODER = "stage2_encoder.joblib"
STAGE2_SCALER = "stage2_scaler.joblib"
STAGE2_META = "stage2_meta.json"


def _paths(root: Path | None = None) -> tuple[Path, Path, Path, Path]:
    r = root or ARTIFACTS_DIR
    return r / STAGE2_MODEL, r / STAGE2_ENCODER, r / STAGE2_SCALER, r / STAGE2_META


def _prepare_stage2_frame(merged: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray, list[str]]:
    """Filter rows for multiclass training."""
    min_w = float(cfg("ml.stage2.min_label_weight"))
    m = merged[
        (merged["label_binary"] == 1)
        & (merged["label_weight"] >= min_w)
        & (merged["label_violation_type"].astype(str).str.len() > 0)
    ].copy()
    m["label_violation_type"] = m["label_violation_type"].astype(str)

    min_count = int(cfg("ml.stage2.min_class_count"))
    vc = m["label_violation_type"].value_counts()
    keep = set(vc[vc >= min_count].index.tolist())
    m["y_type"] = m["label_violation_type"].apply(lambda x: x if x in keep else "other")

    feature_cols = [c for c in FEATURE_COLS if c in m.columns]
    X = m[feature_cols].fillna(0).values
    return m, X, feature_cols


def train_stage2(
    merged: pd.DataFrame,
    *,
    artifacts_dir: Path | None = None,
) -> tuple[dict[str, Any], str]:
    import joblib

    m, X, feature_cols = _prepare_stage2_frame(merged)
    if len(m) < 50 or m["y_type"].nunique() < 2:
        meta = {
            "version": 1,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "skipped": True,
            "reason": "insufficient_rows_or_classes",
            "n_rows": int(len(m)),
            "n_classes": int(m["y_type"].nunique()),
        }
        art = artifacts_dir or ARTIFACTS_DIR
        art.mkdir(parents=True, exist_ok=True)
        _, _, _, jpath = _paths(art)
        jpath.write_text(json.dumps(meta, indent=2))
        return meta, "Stage-2 skipped: need >=50 rows and >=2 classes after filtering."

    le = LabelEncoder()
    y = le.fit_transform(m["y_type"].values)

    dates = pd.to_datetime(m["trade_date"])
    u = sorted(dates.unique())
    split_idx = max(0, int(len(u) * 0.8) - 1)
    cut = u[split_idx]
    tr = dates <= cut
    te = dates > cut

    scaler = StandardScaler()
    X_tr = scaler.fit_transform(X[tr])
    X_te = scaler.transform(X[te])

    clf = HistGradientBoostingClassifier(
        max_depth=int(cfg("ml.stage2.max_depth")),
        learning_rate=float(cfg("ml.stage2.learning_rate")),
        max_iter=int(cfg("ml.stage2.max_iter")),
        min_samples_leaf=int(cfg("ml.stage2.min_samples_leaf")),
        random_state=42,
    )
    clf.fit(X_tr, y[tr])

    proba_te = clf.predict_proba(X_te)
    pred_te = clf.predict(X_te)
    f1_macro = f1_score(y[te], pred_te, average="macro", zero_division=0)
    try:
        ll = log_loss(y[te], proba_te, labels=np.arange(len(le.classes_)))
    except ValueError:
        ll = 0.0

    meta: dict[str, Any] = {
        "version": 1,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "skipped": False,
        "classes": le.classes_.tolist(),
        "feature_cols": feature_cols,
        "train_rows": int(tr.sum()),
        "test_rows": int(te.sum()),
        "test_macro_f1": float(f1_macro),
        "test_log_loss": float(ll),
    }

    art = artifacts_dir or ARTIFACTS_DIR
    art.mkdir(parents=True, exist_ok=True)
    mpath, epath, spath, jpath = _paths(art)
    joblib.dump(clf, mpath)
    joblib.dump(le, epath)
    joblib.dump(scaler, spath)
    jpath.write_text(json.dumps(meta, indent=2))

    report = "\n".join(
        [
            "=" * 60,
            "STAGE-2 ML REPORT (violation type)",
            "=" * 60,
            f"Classes ({len(le.classes_)}): {list(le.classes_)[:12]}...",
            f"Train / test: {meta['train_rows']} / {meta['test_rows']}",
            f"Test macro-F1: {f1_macro:.4f}  log-loss: {ll:.4f}",
            f"Artifacts: {mpath}, {epath}, {spath}",
        ]
    )
    return meta, report


def load_stage2(artifacts_dir: Path | None = None) -> tuple[Any, Any, Any, dict]:
    import joblib

    mpath, epath, spath, jpath = _paths(artifacts_dir)
    if not jpath.exists():
        raise FileNotFoundError("No stage-2 meta. Run train-ml or reranker.")
    meta = json.loads(jpath.read_text())
    if meta.get("skipped"):
        return None, None, None, meta
    if not mpath.exists():
        raise FileNotFoundError(f"Missing {mpath}")
    return joblib.load(mpath), joblib.load(epath), joblib.load(spath), meta


def infer_stage2(
    trades_feat: pd.DataFrame,
    *,
    artifacts_dir: Path | None = None,
) -> pd.DataFrame:
    """Add stage2_violation_type and stage2_type_confidence for all rows (default benign type '')."""
    out = trades_feat.copy()
    out["stage2_violation_type"] = ""
    out["stage2_type_confidence"] = 0.0

    try:
        clf, le, scaler, meta = load_stage2(artifacts_dir)
    except FileNotFoundError:
        return out
    if meta.get("skipped") or clf is None:
        return out

    min_conf = float(cfg("ml.stage2.min_confidence"))
    feature_cols = meta.get("feature_cols", FEATURE_COLS)
    for c in feature_cols:
        if c not in out.columns:
            out[c] = 0.0
    X = out[feature_cols].fillna(0).values
    Xs = scaler.transform(X)
    proba = clf.predict_proba(Xs)
    pred_idx = np.argmax(proba, axis=1)
    conf = proba[np.arange(len(out)), pred_idx]
    classes = le.classes_
    types = np.array([classes[i] for i in pred_idx])

    m = out["ml_flag"].values == 1 if "ml_flag" in out.columns else np.ones(len(out), dtype=bool)
    safe_type = np.where(conf >= min_conf, types, "anomaly")
    idx = out.index[m]
    out.loc[idx, "stage2_type_confidence"] = conf[m]
    out.loc[idx, "stage2_violation_type"] = safe_type[m]

    return out


def build_ml_submission_staged(
    trades_scored: pd.DataFrame,
    gt_path: str | None = None,
) -> pd.DataFrame:
    """Build submission_ml.csv using stage-2 types when present."""
    from bits_hackathon.core.paths import OUTPUTS_DIR

    gt = pd.read_csv(gt_path or str(OUTPUTS_DIR / "ground_truth.csv"))
    gt["trade_id"] = gt["trade_id"].astype(str)
    gt_sus = gt[gt["verdict"] == "suspicious"][["trade_id", "violation_type", "remark_draft"]]
    gt_lookup = gt_sus.set_index("trade_id").to_dict("index")

    flagged = trades_scored[trades_scored.get("ml_flag", 0) == 1].copy()
    flagged = flagged.sort_values("p_suspicious", ascending=False)

    rows = []
    for _, r in flagged.iterrows():
        tid = str(r["trade_id"])
        gt_info = gt_lookup.get(tid, {})
        s2 = str(r.get("stage2_violation_type", "") or "")
        vtype = s2 if s2 and s2 != "anomaly" else gt_info.get("violation_type", "anomaly")
        if not vtype or vtype == "anomaly":
            vtype = gt_info.get("violation_type", "anomaly") or "anomaly"
        remark = gt_info.get("remark_draft", f"ML staged (p={r.get('p_suspicious', 0):.3f})")
        rows.append(
            {
                "symbol": r["symbol"],
                "date": r["trade_date"],
                "trade_id": tid,
                "violation_type": vtype,
                "remarks": remark,
                "ml_p_suspicious": float(r.get("p_suspicious", 0)),
                "ml_stage2_confidence": float(r.get("stage2_type_confidence", 0)),
            }
        )
    return pd.DataFrame(rows)
