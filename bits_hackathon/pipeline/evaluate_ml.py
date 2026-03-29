"""ML evaluation metrics and simple promotion gate vs prior meta."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, precision_score, recall_score

from bits_hackathon.core.config import get as cfg
from bits_hackathon.core.paths import ARTIFACTS_DIR, OUTPUTS_DIR


def evaluate_stage1_holdout(
    y_true: np.ndarray,
    y_score: np.ndarray,
    threshold: float,
) -> dict:
    y_pred = (y_score >= threshold).astype(int)
    out = {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "n_flagged": int(y_pred.sum()),
        "n_pos": int(y_true.sum()),
    }
    if y_true.sum() > 0 and (1 - y_true).sum() > 0:
        out["pr_auc"] = float(average_precision_score(y_true, y_score))
    else:
        out["pr_auc"] = 0.0
    return out


def run_full_evaluation(
    new_stage1_meta: dict,
    prior_stage1_meta_path: Path | str | None = None,
) -> tuple[str, dict]:
    """Text report + promotion dict."""
    lines = ["=" * 60, "ML EVALUATION / PROMOTION GATE", "=" * 60, ""]
    lines.append("New stage-1 test metrics:")
    for k in ("test_precision", "test_recall", "test_f1", "pr_auc_test", "brier_test"):
        if k in new_stage1_meta:
            lines.append(f"  {k}: {new_stage1_meta[k]:.4f}")

    promote = {"promote": True, "reasons": []}

    prior_path = (
        Path(prior_stage1_meta_path)
        if prior_stage1_meta_path
        else ARTIFACTS_DIR / "stage1_meta_previous.json"
    )

    if prior_path.exists():
        prior = json.loads(prior_path.read_text())
        new_p = new_stage1_meta.get("test_precision", 0)
        old_p = prior.get("test_precision", 0)
        new_r = new_stage1_meta.get("test_recall", 0)
        old_r = prior.get("test_recall", 0)
        min_dp = float(cfg("ml.eval.min_precision_improvement"))
        max_dr = float(cfg("ml.eval.max_recall_regression"))
        lines.append("\nvs prior snapshot:")
        lines.append(f"  precision {old_p:.4f} -> {new_p:.4f}")
        lines.append(f"  recall    {old_r:.4f} -> {new_r:.4f}")
        if new_p + 1e-6 < old_p + min_dp:
            promote["promote"] = False
            promote["reasons"].append("precision did not improve enough vs prior")
        if old_r - new_r > max_dr:
            promote["promote"] = False
            promote["reasons"].append("recall regressed beyond tolerance vs prior")
    else:
        lines.append("\n(no prior stage1_meta_previous.json — promotion defaults to True)")

    lines.append(f"\nPromotion decision: {'YES' if promote['promote'] else 'NO'}")
    if promote["reasons"]:
        lines.append("Reasons: " + "; ".join(promote["reasons"]))
    lines.append("=" * 60)
    return "\n".join(lines), promote


def write_evaluation_report(text: str) -> Path:
    p = OUTPUTS_DIR / "ml_evaluation_report.txt"
    p.write_text(text)
    return p
