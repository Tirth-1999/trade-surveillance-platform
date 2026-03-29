"""Parameter tuning: analyse comparison results and suggest threshold changes."""

from __future__ import annotations

import pandas as pd

from bits_hackathon.core.paths import ROOT, OUTPUTS_DIR


def analyse_and_suggest(
    comparison_path: str | None = None,
    ground_truth_path: str | None = None,
) -> str:
    comp = pd.read_csv(comparison_path or str(OUTPUTS_DIR / "comparison_report.csv"))
    gt = pd.read_csv(ground_truth_path or str(OUTPUTS_DIR / "ground_truth.csv"))
    gt["gt_confidence"] = pd.to_numeric(gt.get("confidence", pd.Series(dtype=float)), errors="coerce")

    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("PARAMETER TUNING RECOMMENDATIONS")
    lines.append("=" * 70)

    # --- FP analysis: rules_only with low GT confidence ---
    rules_only = comp[comp["agreement"] == "rules_only"].copy()
    rules_only["gt_confidence"] = pd.to_numeric(rules_only["gt_confidence"], errors="coerce")
    fp_candidates = rules_only[rules_only["gt_confidence"] < 0.3]

    lines.append(f"\n1. LIKELY FALSE POSITIVES (rules_only, GT confidence < 0.3): {len(fp_candidates)}")
    if not fp_candidates.empty:
        fp_by_vtype = fp_candidates["rules_violation_type"].value_counts()
        lines.append("   By violation type:")
        for vtype, count in fp_by_vtype.items():
            lines.append(f"     {vtype:30s}: {count}")
            syms = fp_candidates[fp_candidates["rules_violation_type"] == vtype]["symbol"].value_counts()
            for sym, sc in syms.head(3).items():
                lines.append(f"       → {sym}: {sc} trades")

        lines.append("\n   SUGGESTIONS:")
        for vtype, count in fp_by_vtype.items():
            if count >= 3:
                lines.append(f"   - Consider raising threshold for '{vtype}' detector")
                top_sym = fp_candidates[fp_candidates["rules_violation_type"] == vtype]["symbol"].mode()
                if len(top_sym):
                    lines.append(f"     especially for symbol {top_sym.iloc[0]}")

    # --- FN analysis: gt_only with high GT confidence ---
    gt_only = comp[comp["agreement"] == "gt_only"].copy()
    gt_only["gt_confidence"] = pd.to_numeric(gt_only["gt_confidence"], errors="coerce")
    fn_candidates = gt_only[gt_only["gt_confidence"] >= 0.7]

    lines.append(f"\n2. LIKELY MISSED VIOLATIONS (gt_only, GT confidence >= 0.7): {len(fn_candidates)}")
    if not fn_candidates.empty:
        fn_by_vtype = fn_candidates["gt_violation_type"].value_counts()
        lines.append("   By violation type:")
        for vtype, count in fn_by_vtype.items():
            lines.append(f"     {vtype:30s}: {count}")
            syms = fn_candidates[fn_candidates["gt_violation_type"] == vtype]["symbol"].value_counts()
            for sym, sc in syms.head(3).items():
                lines.append(f"       → {sym}: {sc} trades")

        lines.append("\n   SUGGESTIONS:")
        for vtype, count in fn_by_vtype.items():
            if count >= 2:
                lines.append(f"   - Consider lowering threshold for '{vtype}' or adding new detector")
            elif count == 1:
                lines.append(f"   - Review single missed '{vtype}' case for possible edge case")

    # --- Agreement analysis ---
    both = comp[comp["agreement"] == "both_flag"]
    lines.append(f"\n3. AGREEMENT STATS")
    lines.append(f"   Both flag (true positives likely): {len(both)}")
    lines.append(f"   Rules only:                       {len(rules_only)}")
    lines.append(f"   GT only:                          {len(gt_only)}")
    if len(both) + len(rules_only) > 0:
        precision_est = len(both) / (len(both) + len(rules_only))
        lines.append(f"   Estimated rule precision:         {precision_est:.2%}")
    if len(both) + len(fn_candidates) > 0:
        recall_est = len(both) / (len(both) + len(fn_candidates))
        lines.append(f"   Estimated recall vs GT:           {recall_est:.2%}")

    # --- Per-symbol summary ---
    lines.append(f"\n4. PER-SYMBOL PERFORMANCE")
    for sym in sorted(comp["symbol"].unique()):
        sc = comp[comp["symbol"] == sym]
        b = (sc["agreement"] == "both_flag").sum()
        ro = (sc["agreement"] == "rules_only").sum()
        go = (sc["agreement"] == "gt_only").sum()
        lines.append(f"   {sym:12s}: both={b:3d}  rules_only={ro:3d}  gt_only={go:3d}")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def main() -> None:
    report = analyse_and_suggest()
    print(report)
    out = OUTPUTS_DIR / "tuning_report.txt"
    out.write_text(report)
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
