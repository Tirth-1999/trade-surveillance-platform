#!/usr/bin/env python3
"""Unified CLI entry point for all BITS Hackathon pipelines.

Usage:
    python run.py p1              # Problem 1: equity order-book alerts
    python run.py p2              # Problem 2: SEC 8-K + drift signals
    python run.py p3              # Problem 3: crypto trade surveillance
    python run.py ground-truth    # AI ground-truth agent
    python run.py compare         # Compare rules vs ground truth
    python run.py reranker        # ML staged pipeline (train + score + submission_ml)
    python run.py ml-baseline     # Write baseline metrics report
    python run.py train-ml        # Train stage-1/2, evaluate, write artifacts + submission_ml
    python run.py infer-ml        # Score with saved artifacts only
    python run.py tune            # Parameter tuning recommendations
    python run.py committee       # Three-way committee fusion
    python run.py all             # Run p3 → p1 → p2 sequentially
"""

from __future__ import annotations

import argparse
import sys
import time


def cmd_p1() -> None:
    from bits_hackathon.core.paths import OUTPUTS_DIR
    from bits_hackathon.detectors.p1_equity import build_p1_alerts

    df, elapsed = build_p1_alerts()
    out = OUTPUTS_DIR / "p1_alerts.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} alerts to {out} (runtime {elapsed:.2f}s)")


def cmd_p2() -> None:
    from bits_hackathon.core.paths import OUTPUTS_DIR
    from bits_hackathon.detectors.p2_sec import build_p2_signals

    df, elapsed = build_p2_signals()
    out = OUTPUTS_DIR / "p2_signals.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} signals to {out} (runtime {elapsed:.2f}s)")


def cmd_p3() -> None:
    from bits_hackathon.core.crypto_load import load_all_markets, load_all_trades
    from bits_hackathon.core.paths import OUTPUTS_DIR
    from bits_hackathon.detectors.p3_crypto import build_submission

    t0 = time.perf_counter()
    trades = load_all_trades()
    markets = load_all_markets()
    sub = build_submission(trades, markets)
    out = OUTPUTS_DIR / "submission.csv"
    sub.to_csv(out, index=False)
    elapsed = time.perf_counter() - t0
    print(f"Wrote {len(sub)} rows to {out} in {elapsed:.2f}s")


def cmd_ground_truth() -> None:
    from dotenv import load_dotenv

    from bits_hackathon.core.paths import ROOT, OUTPUTS_DIR
    from bits_hackathon.pipeline.ground_truth_agent import load_all, run_ground_truth

    load_dotenv(ROOT / ".env")
    t0 = time.perf_counter()
    trades, markets = load_all()
    print(f"Loaded {len(trades)} trades, {len(markets)} market bars")
    gt = run_ground_truth(trades, markets)
    out = OUTPUTS_DIR / "ground_truth.csv"
    gt.to_csv(out, index=False)
    elapsed = time.perf_counter() - t0
    sus = gt[gt["verdict"] == "suspicious"]
    print(f"\nWrote {len(gt)} rows ({len(sus)} suspicious) to {out} in {elapsed:.1f}s")


def cmd_compare() -> None:
    from bits_hackathon.core.paths import OUTPUTS_DIR
    from bits_hackathon.pipeline.compare import load_and_compare, print_summary

    comp = load_and_compare()
    out = OUTPUTS_DIR / "comparison_report.csv"
    comp.to_csv(out, index=False)
    print(f"Wrote {len(comp)} rows to {out}")
    print_summary(comp)


def cmd_ml_baseline() -> None:
    from bits_hackathon.core.paths import OUTPUTS_DIR
    from bits_hackathon.pipeline.baseline_audit import write_baseline_report

    path = write_baseline_report()
    print(path.read_text())
    print(f"\nWrote {path}")


def cmd_train_ml() -> None:
    from bits_hackathon.core.crypto_load import load_all_markets, load_all_trades
    from bits_hackathon.core.paths import ARTIFACTS_DIR, OUTPUTS_DIR
    from bits_hackathon.pipeline.baseline_audit import write_baseline_report
    from bits_hackathon.pipeline.evaluate_ml import run_full_evaluation, write_evaluation_report
    from bits_hackathon.pipeline.ml_stage1 import _artifact_paths
    from bits_hackathon.pipeline.ml_stage1 import train_stage1
    from bits_hackathon.pipeline.ml_stage2 import build_ml_submission_staged, infer_stage2, train_stage2
    from bits_hackathon.pipeline.ml_stage1 import infer_stage1

    write_baseline_report()
    _, _, jpath = _artifact_paths()
    prev = ARTIFACTS_DIR / "stage1_meta_previous.json"
    if jpath.exists():
        prev.write_text(jpath.read_text())

    t0 = time.perf_counter()
    trades = load_all_trades()
    markets = load_all_markets()
    print(f"Loaded {len(trades)} trades, {len(markets)} bars")

    merged, meta1, r1 = train_stage1(trades, markets)
    _meta2, r2 = train_stage2(merged)
    eval_text, promote = run_full_evaluation(meta1)
    write_evaluation_report(eval_text)
    print(eval_text)

    merged_scored, _ = infer_stage1(trades, markets)
    merged_scored = infer_stage2(merged_scored)
    ml_sub = build_ml_submission_staged(merged_scored)
    ml_sub.to_csv(OUTPUTS_DIR / "submission_ml.csv", index=False)
    (OUTPUTS_DIR / "reranker_report.txt").write_text(r1 + "\n\n" + r2 + "\n\n" + eval_text)
    print(f"\nWrote {OUTPUTS_DIR / 'submission_ml.csv'} ({len(ml_sub)} rows)")
    print(f"Promotion: {promote}")
    print(f"Done in {time.perf_counter() - t0:.1f}s")


def cmd_infer_ml() -> None:
    from bits_hackathon.core.crypto_load import load_all_markets, load_all_trades
    from bits_hackathon.core.paths import OUTPUTS_DIR
    from bits_hackathon.pipeline.ml_stage1 import infer_stage1
    from bits_hackathon.pipeline.ml_stage2 import build_ml_submission_staged, infer_stage2

    t0 = time.perf_counter()
    trades = load_all_trades()
    markets = load_all_markets()
    merged, _ = infer_stage1(trades, markets)
    merged = infer_stage2(merged)
    ml_sub = build_ml_submission_staged(merged)
    ml_sub.to_csv(OUTPUTS_DIR / "submission_ml.csv", index=False)
    print(f"Wrote {len(ml_sub)} rows to submission_ml.csv in {time.perf_counter() - t0:.1f}s")


def cmd_reranker() -> None:
    from bits_hackathon.core.crypto_load import load_all_markets, load_all_trades
    from bits_hackathon.core.paths import OUTPUTS_DIR
    from bits_hackathon.pipeline.reranker import train_and_predict, build_ml_submission

    t0 = time.perf_counter()
    trades = load_all_trades()
    markets = load_all_markets()
    print(f"Loaded {len(trades)} trades, {len(markets)} bars")

    trades_feat, report = train_and_predict(trades, markets)

    ml_sub = build_ml_submission(trades_feat)
    ml_sub_path = OUTPUTS_DIR / "submission_ml.csv"
    ml_sub.to_csv(ml_sub_path, index=False)
    print(f"\nWrote {len(ml_sub)} ML-flagged rows to {ml_sub_path}")

    report_path = OUTPUTS_DIR / "reranker_report.txt"
    report_path.write_text(report)
    print(f"Wrote report to {report_path}")
    print(report)

    elapsed = time.perf_counter() - t0
    print(f"\nDone in {elapsed:.1f}s")


def cmd_tune() -> None:
    from bits_hackathon.pipeline.parameter_tuning import analyse_and_suggest
    from bits_hackathon.core.paths import OUTPUTS_DIR

    report = analyse_and_suggest()
    print(report)
    out = OUTPUTS_DIR / "tuning_report.txt"
    out.write_text(report)
    print(f"\nSaved to {out}")


def cmd_committee() -> None:
    from bits_hackathon.core.paths import OUTPUTS_DIR
    from bits_hackathon.pipeline.committee import build_committee_submission

    result, report = build_committee_submission()
    out_csv = OUTPUTS_DIR / "submission_committee.csv"
    result.to_csv(out_csv, index=False)
    out_report = OUTPUTS_DIR / "committee_report.txt"
    out_report.write_text(report)
    print(report)
    print(f"\nWrote {len(result)} trades to {out_csv}")
    print(f"Wrote report to {out_report}")


def cmd_all() -> None:
    for label, fn in [("P3", cmd_p3), ("P1", cmd_p1), ("P2", cmd_p2)]:
        print(f"\n{'='*60}")
        print(f"  Running {label}")
        print(f"{'='*60}\n")
        fn()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="BITS Hackathon — Trade Surveillance Pipelines",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("p1", help="Problem 1: equity order-book alerts")
    sub.add_parser("p2", help="Problem 2: SEC 8-K + drift signals")
    sub.add_parser("p3", help="Problem 3: crypto trade surveillance")
    sub.add_parser("ground-truth", help="AI ground-truth agent")
    sub.add_parser("compare", help="Compare rules vs ground truth")
    sub.add_parser("reranker", help="ML re-ranker pipeline")
    sub.add_parser("ml-baseline", help="Write ml_baseline_report.txt from current outputs")
    sub.add_parser("train-ml", help="Train stage-1/2 ML and write artifacts + submission_ml")
    sub.add_parser("infer-ml", help="Infer submission_ml using saved artifacts")
    sub.add_parser("tune", help="Parameter tuning recommendations")
    sub.add_parser("committee", help="Three-way committee fusion submission")
    sub.add_parser("all", help="Run p3 → p1 → p2 sequentially")

    args = parser.parse_args()

    commands = {
        "p1": cmd_p1,
        "p2": cmd_p2,
        "p3": cmd_p3,
        "ground-truth": cmd_ground_truth,
        "compare": cmd_compare,
        "reranker": cmd_reranker,
        "ml-baseline": cmd_ml_baseline,
        "train-ml": cmd_train_ml,
        "infer-ml": cmd_infer_ml,
        "tune": cmd_tune,
        "committee": cmd_committee,
        "all": cmd_all,
    }

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands[args.command]()


if __name__ == "__main__":
    main()
