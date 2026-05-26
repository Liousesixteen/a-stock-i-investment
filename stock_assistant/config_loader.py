from __future__ import annotations

from pathlib import Path
from copy import deepcopy
from typing import Any, Dict

import yaml


def load_yaml(path: str | Path, default: Dict[str, Any] | None = None) -> Dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return default or {}
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    return data or {}


DEFAULT_RISK_RULES: Dict[str, Any] = {
    "fundamental_rules": {
        "strong_revenue_yoy": 10,
        "strong_net_profit_yoy": 10,
        "strong_roe": 12,
        "warn_if_revenue_yoy_below": 0,
        "warn_if_net_profit_yoy_below": 0,
        "warn_if_roe_below": 5,
        "warn_if_debt_ratio_above": 70,
        "healthy_debt_ratio_below": 45,
        "warn_if_ocf_negative": True,
    },
    "valuation_rules": {
        "reasonable_pe_max": 25,
        "high_pe": 45,
        "reasonable_pb_max": 3,
        "high_pb": 6,
    },
    "announcement_rules": {
        "hard_block_events": ["立案调查", "退市风险", "重大违法", "财务造假"],
        "warn_events": ["减持", "解禁", "诉讼", "监管问询", "业绩预亏"],
    },
}


def load_risk_rules(path: str | Path = "config/risk_rules.yaml") -> Dict[str, Any]:
    loaded = load_yaml(path, {})
    merged = deepcopy(DEFAULT_RISK_RULES)
    return _deep_merge(merged, loaded)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base
