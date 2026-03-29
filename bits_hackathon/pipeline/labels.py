"""Weak-supervision labels for P3 ML: binary flag, violation type, weights, confidence bands."""

from __future__ import annotations

import pandas as pd

from bits_hackathon.core.config import get as cfg
from bits_hackathon.core.paths import OUTPUTS_DIR


def _band_from_conf(conf: float | None, high: float, low: float) -> str:
    if conf is None or pd.isna(conf):
        return "uncertain"
    if conf >= high:
        return "high_conf"
    if conf <= low:
        return "low_conf"
    return "uncertain"


def build_per_trade_labels(
    trades: pd.DataFrame,
    comparison_path: str | None = None,
    ground_truth_path: str | None = None,
) -> pd.DataFrame:
    """One row per trade_id in `trades` with label columns.

    Columns:
      label_binary (0/1), label_violation_type (str), label_weight (float),
      label_source (str), pseudo_confidence_band (str)
    """
    comp_path = comparison_path or str(OUTPUTS_DIR / "comparison_report.csv")
    gt_path = ground_truth_path or str(OUTPUTS_DIR / "ground_truth.csv")

    high_pos = float(cfg("ml.labels.high_conf_positive"))
    high_neg = float(cfg("ml.labels.high_conf_negative"))
    w_agree = float(cfg("ml.labels.weight_agreement"))
    w_ai_high = float(cfg("ml.labels.weight_ai_high"))
    w_ai_low = float(cfg("ml.labels.weight_ai_low"))
    w_rules_fp = float(cfg("ml.labels.weight_rules_false_positive"))
    w_rules_amb = float(cfg("ml.labels.weight_rules_ambiguous"))
    w_uncertain = float(cfg("ml.labels.weight_uncertain"))

    comp = pd.read_csv(comp_path)
    comp["gt_confidence"] = pd.to_numeric(comp["gt_confidence"], errors="coerce")

    gt = pd.read_csv(gt_path)
    gt["trade_id"] = gt["trade_id"].astype(str)
    gt["confidence"] = pd.to_numeric(gt.get("confidence", pd.Series(dtype=float)), errors="coerce")

    # Maps trade_id -> fields
    label_binary: dict[str, int] = {}
    vtype: dict[str, str] = {}
    weight: dict[str, float] = {}
    source: dict[str, str] = {}
    band: dict[str, str] = {}

    def set_row(
        tid: str,
        y: int,
        vt: str,
        w: float,
        src: str,
        b: str,
        *,
        overwrite: bool = False,
    ) -> None:
        if not overwrite and tid in label_binary:
            return
        label_binary[tid] = y
        vtype[tid] = vt or ""
        weight[tid] = w
        source[tid] = src
        band[tid] = b

    # From comparison (rules vs AI suspicious alignment)
    comp["trade_id"] = comp["trade_id"].astype(str)
    for _, r in comp.iterrows():
        tid = r["trade_id"]
        ag = r["agreement"]
        gconf = r["gt_confidence"]
        rules_v = str(r.get("rules_violation_type", "") or "")
        gt_v = str(r.get("gt_violation_type", "") or "")
        b = _band_from_conf(gconf, high_pos, high_neg)

        if ag == "both_flag":
            set_row(
                tid,
                1,
                gt_v or rules_v,
                w_agree,
                "agreement",
                "high_conf",
                overwrite=True,
            )
        elif ag == "gt_only":
            if pd.notna(gconf) and gconf >= high_pos:
                set_row(tid, 1, gt_v, w_ai_high, "ai", "high_conf", overwrite=True)
            elif pd.notna(gconf) and gconf <= high_neg:
                set_row(tid, 0, "", w_ai_low, "ai", "low_conf", overwrite=True)
            else:
                set_row(tid, 1, gt_v, w_uncertain, "ai", "uncertain", overwrite=True)
        elif ag == "rules_only":
            if pd.notna(gconf) and gconf < high_neg:
                set_row(tid, 0, rules_v, w_rules_fp, "pseudo_negative", "high_conf", overwrite=True)
            elif pd.notna(gconf) and gconf >= high_pos:
                set_row(tid, 1, rules_v, w_rules_amb, "rules", "uncertain", overwrite=True)
            else:
                set_row(tid, 1, rules_v, w_rules_amb, "rules", "uncertain", overwrite=True)

    # Fill from ground_truth for any trade in `trades` not in comparison
    gt_lookup = gt.set_index("trade_id")
    all_ids = set(trades["trade_id"].astype(str))

    for tid in all_ids:
        if tid in label_binary:
            continue
        if tid not in gt_lookup.index:
            set_row(tid, 0, "", w_uncertain, "missing", "uncertain", overwrite=True)
            continue
        row = gt_lookup.loc[tid]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        verdict = str(row.get("verdict", ""))
        conf = row.get("confidence")
        gtv = str(row.get("violation_type", "") or "")
        b = _band_from_conf(conf, high_pos, high_neg)
        if verdict == "suspicious":
            w = w_ai_high if b == "high_conf" else w_uncertain
            set_row(tid, 1, gtv, w, "ai", b, overwrite=True)
        elif verdict == "benign":
            w = w_ai_high if b == "high_conf" else w_uncertain
            set_row(tid, 0, "", w, "ai", b, overwrite=True)
        else:
            set_row(tid, 0, gtv, w_uncertain, "ai", "uncertain", overwrite=True)

    rows = []
    for tid in trades["trade_id"].astype(str):
        rows.append(
            {
                "trade_id": tid,
                "label_binary": label_binary.get(tid, 0),
                "label_violation_type": vtype.get(tid, ""),
                "label_weight": weight.get(tid, w_uncertain),
                "label_source": source.get(tid, "missing"),
                "pseudo_confidence_band": band.get(tid, "uncertain"),
            }
        )
    return pd.DataFrame(rows)


def build_training_snapshot(
    trades_feat: pd.DataFrame,
    feature_cols: list[str],
    comparison_path: str | None = None,
    ground_truth_path: str | None = None,
    out_path: str | None = None,
) -> pd.DataFrame:
    """Join engineered features with labels; write CSV for reproducibility."""
    lab = build_per_trade_labels(trades_feat, comparison_path, ground_truth_path)
    merged = trades_feat.merge(lab, on="trade_id", how="left")
    merged["label_binary"] = merged["label_binary"].fillna(0).astype(int)
    merged["label_weight"] = merged["label_weight"].fillna(0.25)
    merged["label_violation_type"] = merged["label_violation_type"].fillna("")
    merged["label_source"] = merged["label_source"].fillna("missing")
    merged["pseudo_confidence_band"] = merged["pseudo_confidence_band"].fillna("uncertain")

    path = out_path or str(OUTPUTS_DIR / "training_snapshot.csv")
    merged.to_csv(path, index=False)
    return merged
