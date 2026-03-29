"""Three-way committee fusion: Rules + AI + ML -> final submission.

Reads the three independent detection outputs, computes zone membership
for every flagged trade_id, and applies tiered decision logic to produce
a high-confidence final submission.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from bits_hackathon.core.config import get as cfg
from bits_hackathon.core.paths import OUTPUTS_DIR
from bits_hackathon.core.violation_taxonomy import normalize_violation_type


# Per-violation-type AI confidence thresholds for the AI-only zone (official types + legacy keys)
_AI_ONLY_THRESHOLDS: dict[str, str] = {
    "aml_structuring": "committee.ai_only_conf_default",
    "structuring": "committee.ai_only_conf_default",
    "ramping": "committee.ai_only_conf_default",
    "wash_trading": "committee.ai_only_conf_wash",
    "spoofing": "committee.ai_only_conf_default",
    "layering_echo": "committee.ai_only_conf_layering",
    "layering": "committee.ai_only_conf_layering",
    "peg_break": "committee.ai_only_conf_layering",
    "peg_manipulation": "committee.ai_only_conf_layering",
}

# Violation types to always drop when only rules flag them
_RULES_ONLY_DROP = {"pump_and_dump", "round_trip_wash", "chain_layering"}


def _pick_violation_type(
    rule_vtype: str,
    ai_vtype: str,
    ml_vtype: str,
    *,
    ml_stage2_conf: float | None = None,
) -> str:
    """Pick violation_type; optionally prefer staged ML type when type confidence is high."""
    use_ml_first = bool(cfg("committee.use_staged_ml_types"))
    min_t = float(cfg("ml.stage2.min_confidence"))
    if (
        use_ml_first
        and ml_stage2_conf is not None
        and not pd.isna(ml_stage2_conf)
        and float(ml_stage2_conf) >= min_t
    ):
        for v in (ml_vtype, ai_vtype, rule_vtype):
            if pd.notna(v) and v and v != "anomaly":
                nv = normalize_violation_type(str(v))
                if nv:
                    return nv
    for v in (ai_vtype, rule_vtype, ml_vtype):
        if pd.notna(v) and v and v != "anomaly":
            nv = normalize_violation_type(str(v))
            if nv:
                return nv
    for v in (rule_vtype, ai_vtype, ml_vtype):
        if pd.notna(v) and v:
            nv = normalize_violation_type(str(v))
            if nv:
                return nv
    return ""


def _build_remark(zone: str, sources: dict[str, dict]) -> str:
    """Build a unified remark citing which approaches flagged and why."""
    parts = [f"[Committee: {zone}]"]
    if "rules" in sources:
        parts.append(f"Rules: {sources['rules'].get('violation_type', '?')}")
    if "ai" in sources:
        conf = sources["ai"].get("confidence", "?")
        parts.append(f"AI: {sources['ai'].get('violation_type', '?')} (conf={conf})")
    if "ml" in sources:
        ml = sources["ml"]
        suf = ""
        try:
            if pd.notna(ml.get("ml_p_suspicious")):
                suf += f" p={float(ml['ml_p_suspicious']):.3f}"
        except (TypeError, ValueError):
            pass
        try:
            if pd.notna(ml.get("ml_stage2_confidence")):
                suf += f" type_conf={float(ml['ml_stage2_confidence']):.2f}"
        except (TypeError, ValueError):
            pass
        parts.append(f"ML: {ml.get('violation_type', '?')}{suf}")
    remark = sources.get("ai", {}).get("remark_draft", "")
    if not remark:
        remark = sources.get("rules", {}).get("remarks", "")
    if not remark:
        remark = sources.get("ml", {}).get("remarks", "")
    parts.append(remark)
    return " | ".join(parts)


def build_committee_submission(
    rules_path: str | None = None,
    gt_path: str | None = None,
    ml_path: str | None = None,
) -> tuple[pd.DataFrame, str]:
    """Fuse three detection outputs using tiered committee logic.

    Returns (submission_df, report_text).
    """
    rules = pd.read_csv(rules_path or str(OUTPUTS_DIR / "submission.csv"))
    gt = pd.read_csv(gt_path or str(OUTPUTS_DIR / "ground_truth.csv"))
    ml = pd.read_csv(ml_path or str(OUTPUTS_DIR / "submission_ml.csv"))

    for _df in (rules, gt, ml):
        _df["trade_id"] = _df["trade_id"].astype(str)

    gt["confidence"] = pd.to_numeric(gt["confidence"], errors="coerce").fillna(0.0)

    rule_ids = set(rules["trade_id"])
    ai_sus = gt[gt["verdict"] == "suspicious"]
    ai_ids = set(ai_sus["trade_id"])
    ml_ids = set(ml["trade_id"])

    rules_lookup = rules.set_index("trade_id").to_dict("index")
    ai_lookup = ai_sus.set_index("trade_id").to_dict("index")
    gt_all_lookup = gt.set_index("trade_id").to_dict("index")
    ml_lookup = ml.set_index("trade_id").to_dict("index")

    # Zone membership
    all_three = rule_ids & ai_ids & ml_ids
    rules_ai = (rule_ids & ai_ids) - ml_ids
    rules_ml = (rule_ids & ml_ids) - ai_ids
    ai_ml = (ai_ids & ml_ids) - rule_ids
    rules_only = rule_ids - ai_ids - ml_ids
    ai_only = ai_ids - rule_ids - ml_ids
    ml_only = ml_ids - rule_ids - ai_ids

    tier1_raw = all_three | rules_ai | rules_ml | ai_ml
    require_gates = bool(cfg("committee.tier1_require_gates"))
    min_ml_p = float(cfg("committee.tier1_min_ml_probability"))
    min_ai_ra = float(cfg("committee.tier1_rules_ai_min_ai_confidence"))
    rules_only_min_gt = float(cfg("committee.rules_only_min_gt_confidence"))

    def _ml_prob(tid: str) -> float:
        ml_row = ml_lookup.get(tid, {})
        p = ml_row.get("ml_p_suspicious", 0)
        try:
            return float(p) if pd.notna(p) else 0.0
        except (TypeError, ValueError):
            return 0.0

    def _ai_conf(tid: str) -> float:
        ai_row = ai_lookup.get(tid, {})
        c = ai_row.get("confidence", 0)
        try:
            return float(c) if pd.notna(c) else 0.0
        except (TypeError, ValueError):
            return 0.0

    tier1_ids: set[str] = set()
    for tid in tier1_raw:
        if not require_gates:
            tier1_ids.add(tid)
            continue
        ok = True
        if tid in rules_ml or tid in ai_ml or tid in all_three:
            if min_ml_p > 0 and _ml_prob(tid) < min_ml_p:
                ok = False
        if tid in rules_ai or tid in all_three:
            if min_ai_ra > 0 and _ai_conf(tid) < min_ai_ra:
                ok = False
        if ok:
            tier1_ids.add(tid)

    # --- Tier 2: Rules-only triage ---
    rules_only_keep: set[str] = set()
    rules_only_drop: set[str] = set()
    keep_uncertain = cfg("committee.rules_only_keep_uncertain")

    for tid in rules_only:
        r = rules_lookup.get(tid, {})
        vtype = r.get("violation_type", "")
        if vtype in _RULES_ONLY_DROP:
            rules_only_drop.add(tid)
            continue
        if keep_uncertain:
            gt_row = gt_all_lookup.get(tid, {})
            gt_conf = gt_row.get("confidence", 0.0)
            gt_verdict = gt_row.get("verdict", "benign")
            if gt_verdict == "uncertain" or (
                isinstance(gt_conf, (int, float)) and not pd.isna(gt_conf) and gt_conf >= rules_only_min_gt
            ):
                rules_only_keep.add(tid)
            else:
                rules_only_drop.add(tid)
        else:
            rules_only_drop.add(tid)

    # --- Tier 2: AI-only triage ---
    ai_only_keep: set[str] = set()
    ai_only_drop: set[str] = set()
    ai_drop_types = {"pump_and_dump"}
    include_ai_only = bool(cfg("committee.include_ai_only"))

    for tid in ai_only:
        if not include_ai_only:
            ai_only_drop.add(tid)
            continue
        ai_row = ai_lookup.get(tid, {})
        vtype = str(ai_row.get("violation_type", "") or "")
        conf = ai_row.get("confidence", 0.0)

        if normalize_violation_type(vtype) in ai_drop_types or vtype in ai_drop_types:
            ai_only_drop.add(tid)
            continue

        cfg_key = _AI_ONLY_THRESHOLDS.get(vtype, "committee.ai_only_conf_default")
        threshold = cfg(cfg_key)
        if isinstance(conf, (int, float)) and conf >= threshold:
            ai_only_keep.add(tid)
        else:
            ai_only_drop.add(tid)

    # --- Tier 2: ML-only ---
    include_ml_only = cfg("committee.ml_only_include")
    ml_only_keep = ml_only if include_ml_only else set()

    # --- Assemble final set ---
    final_ids = tier1_ids | rules_only_keep | ai_only_keep | ml_only_keep

    rows: list[dict] = []
    for tid in sorted(final_ids):
        sources: dict[str, dict] = {}
        if tid in rule_ids:
            sources["rules"] = rules_lookup.get(tid, {})
        if tid in ai_ids:
            sources["ai"] = ai_lookup.get(tid, {})
        if tid in ml_ids:
            sources["ml"] = ml_lookup.get(tid, {})

        # Determine zone label
        if tid in all_three:
            zone = "all_three"
        elif tid in rules_ai:
            zone = "rules+ai"
        elif tid in rules_ml:
            zone = "rules+ml"
        elif tid in ai_ml:
            zone = "ai+ml"
        elif tid in rules_only_keep:
            zone = "rules_only_kept"
        elif tid in ai_only_keep:
            zone = "ai_only_kept"
        elif tid in ml_only_keep:
            zone = "ml_only_kept"
        else:
            zone = "unknown"

        r_vtype = sources.get("rules", {}).get("violation_type", "")
        a_vtype = sources.get("ai", {}).get("violation_type", "")
        ml_row = sources.get("ml", {})
        m_vtype = ml_row.get("violation_type", "")
        s2c = ml_row.get("ml_stage2_confidence")
        try:
            s2c_f = float(s2c) if pd.notna(s2c) else None
        except (TypeError, ValueError):
            s2c_f = None
        vtype = _pick_violation_type(r_vtype, a_vtype, m_vtype, ml_stage2_conf=s2c_f)
        vtype = normalize_violation_type(vtype) or normalize_violation_type(
            str(r_vtype or a_vtype or m_vtype or "")
        )

        symbol = (
            sources.get("rules", {}).get("symbol")
            or sources.get("ai", {}).get("symbol")
            or sources.get("ml", {}).get("symbol", "")
        )
        date = (
            sources.get("rules", {}).get("date")
            or sources.get("ai", {}).get("date")
            or sources.get("ml", {}).get("date", "")
        )

        rows.append({
            "symbol": symbol,
            "date": date,
            "trade_id": tid,
            "violation_type": vtype,
            "remarks": _build_remark(zone, sources),
        })

    result = pd.DataFrame(rows)

    # --- Generate report ---
    lines = [
        "=" * 70,
        "THREE-WAY COMMITTEE REPORT",
        "=" * 70,
        "",
        "Input counts:",
        f"  Rules flags:  {len(rule_ids)}",
        f"  AI suspicious: {len(ai_ids)}",
        f"  ML flags:      {len(ml_ids)}",
        "",
        "Zone breakdown:",
        f"  All 3 agree:     {len(all_three)}",
        f"  Rules + AI:      {len(rules_ai)}",
        f"  Rules + ML:      {len(rules_ml)}",
        f"  AI + ML:         {len(ai_ml)}",
        f"  Rules only:      {len(rules_only)}  (kept {len(rules_only_keep)}, dropped {len(rules_only_drop)})",
        f"  AI only:         {len(ai_only)}  (kept {len(ai_only_keep)}, dropped {len(ai_only_drop)})",
        f"  ML only:         {len(ml_only)}  (kept {len(ml_only_keep)}, dropped {len(ml_only - ml_only_keep)})",
        "",
        "Tier summary:",
        f"  Tier 1 (2+ agree, raw):   {len(tier1_raw)}",
        f"  Tier 1 (after ML/AI gates): {len(tier1_ids)}",
        f"  Tier 2 rules-only kept:   {len(rules_only_keep)}",
        f"  Tier 2 AI-only kept:      {len(ai_only_keep)}",
        f"  Tier 2 ML-only kept:      {len(ml_only_keep)}",
        f"  ---",
        f"  FINAL SUBMISSION TOTAL:   {len(result)}",
        "",
    ]

    if not result.empty:
        lines.append("Violation type distribution:")
        for vtype, count in result["violation_type"].value_counts().items():
            lines.append(f"  {vtype:30s}: {count}")
        lines.append("")
        lines.append("Per-symbol breakdown:")
        for sym in sorted(result["symbol"].unique()):
            n = (result["symbol"] == sym).sum()
            lines.append(f"  {sym:12s}: {n}")

    lines.append("")
    lines.append("=" * 70)

    report = "\n".join(lines)
    return result, report
