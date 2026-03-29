"""Hackathon-style score proxy: compare a submission CSV to AI ground truth.

Uses GT `verdict == suspicious` as a stand-in for hidden injects. Not identical
to organiser scoring, but repeatable for threshold/detector tuning.

Score proxy (P3-style): sum over flagged trade_ids of (+5 if GT suspicious else -2).
Optional violation_type bonus proxy: +2 per TP where types match exactly.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from bits_hackathon.core.paths import OUTPUTS_DIR
from bits_hackathon.core.violation_taxonomy import normalize_violation_type


def evaluate_submission_vs_gt(
    submission_path: str | Path,
    ground_truth_path: str | Path,
    *,
    type_bonus: bool = True,
) -> dict:
    sub = pd.read_csv(submission_path)
    gt = pd.read_csv(ground_truth_path)
    sub["trade_id"] = sub["trade_id"].astype(str)
    gt["trade_id"] = gt["trade_id"].astype(str)

    gt_sus = gt[gt["verdict"] == "suspicious"].copy()
    sus_ids = set(gt_sus["trade_id"])
    sub_ids = list(sub["trade_id"].unique())
    flagged = set(sub_ids)

    tp_ids = flagged & sus_ids
    fp_ids = flagged - sus_ids
    tp = len(tp_ids)
    fp = len(fp_ids)

    base_score = 5 * tp - 2 * fp
    type_bonus_pts = 0
    matched_types = 0

    if type_bonus and tp > 0:
        gt_type = gt_sus.set_index("trade_id")["violation_type"].to_dict()
        for tid in tp_ids:
            row = sub[sub["trade_id"] == tid].iloc[0]
            st = normalize_violation_type(str(row.get("violation_type", "") or ""))
            gt_t = normalize_violation_type(str(gt_type.get(tid, "") or ""))
            if st and gt_t and st == gt_t:
                type_bonus_pts += 2
                matched_types += 1

    # Reference: suspicious GT not in submission (proxy FN count)
    fn = len(sus_ids - flagged)

    rows = []
    for tid in sorted(flagged):
        in_gt = tid in sus_ids
        rows.append(
            {
                "trade_id": tid,
                "in_gt_suspicious": int(in_gt),
                "violation_type": sub.loc[sub["trade_id"] == tid, "violation_type"].iloc[0]
                if tid in sub["trade_id"].values
                else "",
            }
        )

    by_vtype = (
        sub.groupby("violation_type")["trade_id"]
        .apply(lambda s: set(s.astype(str)))
        .to_dict()
    )
    per_type = []
    for vtype, tids in sorted(by_vtype.items(), key=lambda x: -len(x[1])):
        tids = tids - {""}
        tp_v = len(tids & sus_ids)
        fp_v = len(tids - sus_ids)
        per_type.append(
            {
                "violation_type": vtype,
                "flagged": len(tids),
                "tp_proxy": tp_v,
                "fp_proxy": fp_v,
                "precision_proxy": (tp_v / len(tids)) if tids else 0.0,
                "contrib_5m2": 5 * tp_v - 2 * fp_v,
            }
        )

    return {
        "submission_path": str(submission_path),
        "ground_truth_path": str(ground_truth_path),
        "n_flagged": len(flagged),
        "tp_proxy": tp,
        "fp_proxy": fp,
        "fn_proxy": fn,
        "base_score_proxy": base_score,
        "type_bonus_proxy": type_bonus_pts,
        "type_matches": matched_types,
        "total_score_proxy": base_score + type_bonus_pts,
        "per_violation_type": per_type,
        "rows": rows,
    }


def format_report(ev: dict) -> str:
    lines = [
        "=" * 60,
        "SCORE PROXY (vs ground_truth suspicious)",
        "=" * 60,
        f"Submission: {ev['submission_path']}",
        f"Ground truth: {ev['ground_truth_path']}",
        "",
        f"Flagged trades:     {ev['n_flagged']}",
        f"TP proxy (in GT):   {ev['tp_proxy']}",
        f"FP proxy (not GT):  {ev['fp_proxy']}",
        f"FN proxy (missed):  {ev['fn_proxy']}",
        "",
        f"Base P3 proxy:      {ev['base_score_proxy']}  (= 5·TP − 2·FP)",
        f"Type bonus proxy:   +{ev['type_bonus_proxy']}  ({ev['type_matches']} exact type matches on TPs)",
        f"Total proxy:        {ev['total_score_proxy']}",
        "",
        "Per violation_type (rules labels):",
    ]
    for r in ev["per_violation_type"][:25]:
        lines.append(
            f"  {r['violation_type']!s:28s}  flagged={r['flagged']:4d}  "
            f"TP={r['tp_proxy']:4d}  FP={r['fp_proxy']:4d}  "
            f"prec~={r['precision_proxy']:.3f}  5·TP−2·FP={r['contrib_5m2']}"
        )
    if len(ev["per_violation_type"]) > 25:
        lines.append(f"  ... ({len(ev['per_violation_type']) - 25} more types)")
    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Score proxy vs ground_truth.csv")
    p.add_argument(
        "--submission",
        default=str(OUTPUTS_DIR / "submission.csv"),
        help="Path to submission CSV",
    )
    p.add_argument(
        "--ground-truth",
        default=str(OUTPUTS_DIR / "ground_truth.csv"),
        help="Path to ground_truth.csv",
    )
    p.add_argument("--no-type-bonus", action="store_true", help="Ignore +2 type bonus proxy")
    p.add_argument("--json", action="store_true", help="Print JSON summary")
    args = p.parse_args(argv)

    ev = evaluate_submission_vs_gt(
        args.submission,
        args.ground_truth,
        type_bonus=not args.no_type_bonus,
    )
    if args.json:
        import json

        slim = {k: v for k, v in ev.items() if k != "rows"}
        print(json.dumps(slim, indent=2))
    else:
        print(format_report(ev))


if __name__ == "__main__":
    main()
