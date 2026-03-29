"""ML re-ranker: staged stage-1 + stage-2 pipeline (legacy API preserved for run.py)."""

from __future__ import annotations

import pandas as pd

from bits_hackathon.pipeline.ml_features import FEATURE_COLS, engineer_features
from bits_hackathon.pipeline.ml_stage1 import infer_stage1, train_stage1
from bits_hackathon.pipeline.ml_stage2 import build_ml_submission_staged, infer_stage2, train_stage2

# Re-export for callers that still import engineer_features from reranker
__all__ = [
    "engineer_features",
    "FEATURE_COLS",
    "train_and_predict",
    "build_ml_submission",
]


def train_and_predict(
    trades: pd.DataFrame,
    markets: pd.DataFrame,
    comparison_path: str | None = None,
) -> tuple[pd.DataFrame, str]:
    """Train calibrated stage-1 + stage-2, then score full universe via saved artifacts."""
    merged, _meta1, report1 = train_stage1(trades, markets, comparison_path=comparison_path)
    _meta2, report2 = train_stage2(merged)
    merged_scored, _ = infer_stage1(trades, markets)
    merged_scored = infer_stage2(merged_scored)
    report = report1 + "\n\n" + report2
    return merged_scored, report


def build_ml_submission(
    trades_feat: pd.DataFrame,
    gt_path: str | None = None,
) -> pd.DataFrame:
    return build_ml_submission_staged(trades_feat, gt_path=gt_path)
