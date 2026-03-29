"""Compare rule-based submission.csv against ground_truth.csv."""

from __future__ import annotations

import pandas as pd


def load_and_compare(
    submission_path: str | None = None,
    ground_truth_path: str | None = None,
) -> pd.DataFrame:
    from bits_hackathon.core.paths import ROOT, OUTPUTS_DIR

    sub_path = submission_path or str(OUTPUTS_DIR / "submission.csv")
    gt_path = ground_truth_path or str(OUTPUTS_DIR / "ground_truth.csv")

    sub = pd.read_csv(sub_path)
    gt = pd.read_csv(gt_path)

    sub_ids = set(sub["trade_id"])
    gt_suspicious = gt[gt["verdict"] == "suspicious"]
    gt_sus_ids = set(gt_suspicious["trade_id"])

    all_gt_ids = set(gt["trade_id"])

    rows: list[dict] = []

    all_trade_ids = sub_ids | all_gt_ids
    sub_lookup = sub.set_index("trade_id").to_dict("index") if not sub.empty else {}
    gt_lookup = gt.set_index("trade_id").to_dict("index") if not gt.empty else {}

    for tid in sorted(all_trade_ids):
        in_sub = tid in sub_ids
        in_gt_sus = tid in gt_sus_ids
        gt_row = gt_lookup.get(tid, {})
        sub_row = sub_lookup.get(tid, {})

        if in_sub and in_gt_sus:
            agreement = "both_flag"
        elif in_sub and not in_gt_sus:
            agreement = "rules_only"
        elif not in_sub and in_gt_sus:
            agreement = "gt_only"
        else:
            continue

        rules_vtype = sub_row.get("violation_type", "")
        gt_vtype = gt_row.get("violation_type", "")
        type_match = bool(rules_vtype and gt_vtype and rules_vtype == gt_vtype)

        rows.append({
            "trade_id": tid,
            "symbol": sub_row.get("symbol", gt_row.get("symbol", "")),
            "date": sub_row.get("date", gt_row.get("date", "")),
            "agreement": agreement,
            "rules_violation_type": rules_vtype,
            "gt_violation_type": gt_vtype,
            "gt_confidence": gt_row.get("confidence", ""),
            "gt_rationale": gt_row.get("rationale", ""),
            "type_match": type_match,
        })

    return pd.DataFrame(rows)


def print_summary(comp: pd.DataFrame) -> None:
    print("=" * 70)
    print("COMPARISON SUMMARY")
    print("=" * 70)
    print(f"\nTotal compared rows: {len(comp)}")

    counts = comp["agreement"].value_counts()
    for cat in ["both_flag", "rules_only", "gt_only"]:
        print(f"  {cat:20s}: {counts.get(cat, 0):>5d}")

    print(f"\nPer-symbol breakdown:")
    for sym, g in comp.groupby("symbol"):
        vc = g["agreement"].value_counts().to_dict()
        parts = ", ".join(f"{k}={v}" for k, v in sorted(vc.items()))
        print(f"  {sym:12s}: {parts}")

    both = comp[comp["agreement"] == "both_flag"]
    if not both.empty:
        tm = both["type_match"].sum()
        print(f"\nType match among both_flag: {tm}/{len(both)} ({tm/len(both)*100:.1f}%)")

    gt_only = comp[comp["agreement"] == "gt_only"].copy()
    if not gt_only.empty and "gt_confidence" in gt_only.columns:
        gt_only["gt_confidence"] = pd.to_numeric(gt_only["gt_confidence"], errors="coerce")
        top_add = gt_only.nlargest(10, "gt_confidence")
        print(f"\nTop 10 gt_only (candidates to ADD to submission):")
        for _, r in top_add.iterrows():
            print(f"  {r['trade_id']:25s} {r['symbol']:12s} conf={r['gt_confidence']:.2f}  {r['gt_violation_type']}")

    rules_only = comp[comp["agreement"] == "rules_only"].copy()
    if not rules_only.empty and "gt_confidence" in rules_only.columns:
        rules_only["gt_confidence"] = pd.to_numeric(rules_only["gt_confidence"], errors="coerce")
        low_conf = rules_only.nsmallest(10, "gt_confidence")
        print(f"\nTop 10 rules_only with lowest GT confidence (candidates to REMOVE):")
        for _, r in low_conf.iterrows():
            conf_str = f"{r['gt_confidence']:.2f}" if pd.notna(r["gt_confidence"]) else "N/A"
            print(f"  {r['trade_id']:25s} {r['symbol']:12s} conf={conf_str}  {r['rules_violation_type']}")

    print("=" * 70)
