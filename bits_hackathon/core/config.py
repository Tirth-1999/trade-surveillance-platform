"""Centralized configuration for all detector thresholds and feature flags.

Load overrides from config.yaml if present, otherwise use defaults.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from bits_hackathon.core.paths import ROOT

_CONFIG_PATH = ROOT / "config.yaml"

DEFAULTS: dict[str, Any] = {
    # ---- P3 crypto detectors ----
    "p3.peg_break.deviation_pct": 0.005,
    "p3.peg_break.min_trade_notional_usdt": 100.0,
    "p3.peg_break.min_bar_volume_usdt": 50.0,

    "p3.liquid_pair_symbols": ["BTCUSDT", "ETHUSDT"],
    "p3.min_notional_liquid_pair_usdt": 1500.0,

    "p3.wash.window_sec": 90,
    "p3.wash.notional_rel_tol": 0.02,
    "p3.wash.min_notional_usdt": 400.0,

    "p3.ramping.min_streak": 6,
    "p3.ramping.max_gap_sec": 300,
    "p3.ramping.max_median_gap_sec": 120.0,

    "p3.aml_structuring.low": 9980,
    "p3.aml_structuring.high": 10000,
    "p3.aml_structuring.min_count": 6,
    "p3.aml_structuring.max_cv": 0.015,

    "p3.threshold_testing.band": 50,
    "p3.threshold_testing.min_below": 4,

    "p3.layering_echo.window_sec": 600,
    "p3.layering_echo.min_burst": 3,
    "p3.layering_echo.max_notional_imbalance": 0.35,

    "p3.coordinated_structuring.low": 9950,
    "p3.coordinated_structuring.high": 10000,
    "p3.coordinated_structuring.min_wallets": 4,
    "p3.coordinated_structuring.max_wallet_mean_cv": 0.08,

    "p3.bat_volume_spike.multiplier": 5.0,
    "p3.bat_volume_spike.min_hour_tradecount": 8,

    "p3.price_bar_violation.min_mid_bps": 35.0,
    "p3.price_bar_violation.min_mid_bps_low_liquidity": 55.0,
    "p3.price_bar_violation.low_liquidity_tradecount": 6,

    "p3.round_trip.window_sec": 120,
    "p3.round_trip.notional_rel_tol": 0.02,
    "p3.round_trip.min_notional_usdt": 500.0,

    "p3.chain_layering.window_sec": 300,
    "p3.chain_layering.notional_tol": 0.1,
    "p3.chain_layering.max_sell_trades": 2500,
    "p3.chain_layering.max_outer_iter": 800,

    "p3.pump_dump.symbols": ["BATUSDT", "DOGEUSDT"],
    "p3.pump_dump.up_thr_default": 0.02,
    "p3.pump_dump.up_thr_doge": 0.025,
    "p3.pump_dump.down_thr": -0.015,
    "p3.pump_dump.vol_mult": 1.5,
    "p3.pump_dump.notional_quantile": 0.72,
    "p3.pump_dump.max_trades_per_bar": 6,

    "p3.placement_smurfing.min_new_wallets": 6,

    "p3.usdc_wash.window_sec": 60,
    "p3.usdc_wash.price_tol": 0.0005,

    # Trim caps
    "p3.trim.pump_and_dump": 35,
    "p3.trim.spoofing": 80,
    "p3.trim.round_trip_wash": 25,

    # Feature flags for gated detectors
    "p3.enable.cross_pair_divergence": False,
    "p3.enable.coordinated_pump": False,
    "p3.enable.manager_consolidation": False,
    "p3.enable.extreme_mid_deviation": False,

    # ---- P1 equity detectors ----
    "p1.obi.z_thr": 3.15,
    "p1.obi.min_run": 5,
    "p1.obi.rolling_window": 30,
    "p1.obi.rolling_minp": 15,
    "p1.obi.max_alerts": 28,
    "p1.obi.min_depth_shares": 50,
    "p1.obi.skip_first_minutes": 0,

    "p1.cancel.win_min": 15,
    "p1.cancel.min_cancels": 4,
    "p1.cancel.max_alerts": 20,

    # ---- P2 SEC/insider ----
    "p2.sec.user_agent": "BITS-Hackathon-Student contact@example.edu",
    "p2.sec.cache_dir": ".cache/sec",
    "p2.sec.retry_count": 2,
    "p2.sec.backoff_sec": 0.5,
    "p2.drift.vol_z_threshold": 2.5,
    "p2.drift.cum_ret_threshold": 0.025,
    "p2.drift.baseline_days": 15,
    "p2.drift.pre_window_days": 5,

    # ---- Committee fusion ----
    "committee.ai_only_conf_default": 0.85,
    "committee.ai_only_conf_wash": 0.80,
    "committee.ai_only_conf_layering": 0.90,
    "committee.rules_only_keep_uncertain": True,
    "committee.rules_only_min_gt_confidence": 0.45,
    "committee.ml_only_include": False,
    "committee.use_staged_ml_types": True,
    # Keep at/below typical stage-1 operating threshold (~0.29–0.45); higher values drop all tier-1 ML rows.
    "committee.tier1_min_ml_probability": 0.30,
    "committee.tier1_rules_ai_min_ai_confidence": 0.5,
    "committee.tier1_require_gates": True,

    # ---- P3 ML (staged) ----
    "ml.labels.high_conf_positive": 0.7,
    "ml.labels.high_conf_negative": 0.3,
    "ml.labels.weight_agreement": 1.0,
    "ml.labels.weight_ai_high": 0.9,
    "ml.labels.weight_ai_low": 0.35,
    "ml.labels.weight_rules_false_positive": 0.85,
    "ml.labels.weight_rules_ambiguous": 0.5,
    "ml.labels.weight_uncertain": 0.25,
    "ml.labels.drop_uncertain_training": False,
    "ml.stage1.train_fraction_by_date": 0.8,
    "ml.stage1.calibration_method": "isotonic",
    "ml.stage1.threshold_metric": "f05",
    "ml.stage1.min_precision_floor": 0.35,
    "ml.stage1.min_samples_leaf": 40,
    "ml.stage1.max_depth": 6,
    "ml.stage1.learning_rate": 0.08,
    "ml.stage1.max_iter": 400,
    "ml.stage2.min_class_count": 8,
    "ml.stage2.min_label_weight": 0.4,
    "ml.stage2.min_confidence": 0.35,
    "ml.stage2.max_depth": 8,
    "ml.stage2.max_iter": 500,
    "ml.stage2.learning_rate": 0.08,
    "ml.stage2.min_samples_leaf": 20,
    "ml.eval.min_precision_improvement": 0.0,
    "ml.eval.max_recall_regression": 0.05,
}

_loaded: dict[str, Any] | None = None


def _load_yaml() -> dict[str, Any]:
    """Load config.yaml if it exists, returning flat dot-separated keys."""
    if not _CONFIG_PATH.exists():
        return {}
    try:
        import yaml
        with open(_CONFIG_PATH) as f:
            raw = yaml.safe_load(f) or {}
    except ImportError:
        return {}

    flat: dict[str, Any] = {}

    def _flatten(d: dict, prefix: str = "") -> None:
        for k, v in d.items():
            key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
            if isinstance(v, dict):
                _flatten(v, key)
            else:
                flat[key] = v

    _flatten(raw)
    return flat


def get(key: str) -> Any:
    """Retrieve a config value by dot-separated key, checking env > yaml > defaults."""
    global _loaded
    if _loaded is None:
        _loaded = _load_yaml()

    env_key = "CFG_" + key.replace(".", "_").upper()
    env_val = os.environ.get(env_key)
    if env_val is not None:
        default = DEFAULTS.get(key)
        if isinstance(default, bool):
            return env_val.lower() in ("1", "true", "yes")
        if isinstance(default, int):
            return int(env_val)
        if isinstance(default, float):
            return float(env_val)
        return env_val

    if key in _loaded:
        return _loaded[key]

    return DEFAULTS.get(key)


def all_config() -> dict[str, Any]:
    """Return full merged config for display/debug."""
    global _loaded
    if _loaded is None:
        _loaded = _load_yaml()
    merged = dict(DEFAULTS)
    merged.update(_loaded)
    return merged
