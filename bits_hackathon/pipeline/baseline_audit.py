"""Baseline metrics for rules vs AI vs committee (pre-upgrade reference)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bits_hackathon.core.paths import OUTPUTS_DIR


def run_baseline_audit(
    outputs_dir: Path | None = None,
) -> tuple[str, dict]:
    """Compute summary stats from existing CSVs. Returns (report_text, metrics_dict)."""
    out = outputs_dir or OUTPUTS_DIR
    metrics: dict = {}

    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("ML BASELINE AUDIT (rules / AI / committee)")
    lines.append("=" * 70)

    comp_path = out / "comparison_report.csv"
    if not comp_path.exists():
        lines.append("\nMissing comparison_report.csv — run: python run.py compare")
        return "\n".join(lines), metrics

    comp = pd.read_csv(comp_path)
    counts = comp["agreement"].value_counts().to_dict()
    both = counts.get("both_flag", 0)
    rules_only = counts.get("rules_only", 0)
    gt_only = counts.get("gt_only", 0)
    metrics["comparison_both_flag"] = both
    metrics["comparison_rules_only"] = rules_only
    metrics["comparison_gt_only"] = gt_only

    lines.append("\nComparison report (rules vs AI suspicious):")
    lines.append(f"  both_flag:   {both}")
    lines.append(f"  rules_only:  {rules_only}")
    lines.append(f"  gt_only:     {gt_only}")

    if both + rules_only > 0:
        prec_est = both / (both + rules_only)
        metrics["estimated_rule_precision_vs_ai_suspicious"] = prec_est
        lines.append(f"\nEstimated rule precision vs AI-flagged suspicious: {prec_est:.4f}")

    sub_path = out / "submission.csv"
    ml_path = out / "submission_ml.csv"
    com_path = out / "submission_committee.csv"

    for label, p in [
        ("Rules submission", sub_path),
        ("ML submission", ml_path),
        ("Committee submission", com_path),
    ]:
        if p.exists():
            df = pd.read_csv(p)
            n = len(df)
            metrics[label.lower().replace(" ", "_")] = n
            lines.append(f"\n{label}: {n} rows")
            if "violation_type" in df.columns and n:
                lines.append("  Top violation_type:")
                for v, c in df["violation_type"].value_counts().head(8).items():
                    lines.append(f"    {v}: {c}")
        else:
            lines.append(f"\n{label}: (file missing)")

    gt_path = out / "ground_truth.csv"
    if gt_path.exists():
        gt = pd.read_csv(gt_path)
        sus = (gt["verdict"] == "suspicious").sum()
        metrics["ground_truth_suspicious"] = int(sus)
        metrics["ground_truth_total"] = len(gt)
        lines.append(f"\nGround truth: {sus} suspicious / {len(gt)} labeled trades")

    lines.append("\n" + "=" * 70)
    report = "\n".join(lines)
    return report, metrics


def write_baseline_report(outputs_dir: Path | None = None) -> Path:
    text, _ = run_baseline_audit(outputs_dir)
    path = (outputs_dir or OUTPUTS_DIR) / "ml_baseline_report.txt"
    path.write_text(text)
    return path
