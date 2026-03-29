"""Official Problem 3 violation_type strings (case-sensitive) + normalization aliases."""

from __future__ import annotations

# Exact strings from hackathon taxonomy (do not rename).
OFFICIAL_VIOLATION_TYPES: frozenset[str] = frozenset(
    {
        "aml_structuring",
        "coordinated_structuring",
        "threshold_testing",
        "chain_layering",
        "manager_consolidation",
        "placement_smurfing",
        "wash_trading",
        "pump_and_dump",
        "layering_echo",
        "spoofing",
        "ramping",
        "coordinated_pump",
        "round_trip_wash",
        "cross_pair_divergence",
        "peg_break",
        "wash_volume_at_peg",
    }
)

# Map common internal / LLM shorthand → official string (keys lowercased).
_VIOLATION_TYPE_ALIASES: dict[str, str] = {
    "structuring": "aml_structuring",
    "layering": "layering_echo",
    "peg_manipulation": "peg_break",
    "peg manip": "peg_break",
    "wash": "wash_trading",
    "wash trade": "wash_trading",
    "pump": "pump_and_dump",
    "pumpdump": "pump_and_dump",
    "roundtrip": "round_trip_wash",
    "round_trip": "round_trip_wash",
    "coordinated pump": "coordinated_pump",
    "cross pair": "cross_pair_divergence",
    "crosspair": "cross_pair_divergence",
    "aml": "aml_structuring",
    "smurfing": "aml_structuring",
    "placement": "placement_smurfing",
    "chain": "chain_layering",
    "consolidation": "manager_consolidation",
    "anomaly": "",
    "other": "",
    "unknown": "",
    "": "",
}


def normalize_violation_type(raw: str | None) -> str:
    """Return canonical violation_type for CSV output, or '' if unknown / non-scoring.

    Accepts aliases used by legacy prompts, stubs, or ML encoders.
    """
    if raw is None or (isinstance(raw, float) and raw != raw):  # NaN
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    if s in OFFICIAL_VIOLATION_TYPES:
        return_s = s
    else:
        return_s = _VIOLATION_TYPE_ALIASES.get(s.lower(), "")
    return return_s


def is_official_violation_type(v: str) -> bool:
    return bool(v) and v in OFFICIAL_VIOLATION_TYPES
