from __future__ import annotations

import re
from datetime import datetime
from typing import Any


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def clamp(value: float, lower: float = 0, upper: float = 100) -> float:
    return max(lower, min(upper, value))


def normalize_symbol(symbol: str) -> str:
    cleaned = symbol.strip().upper()
    cleaned = re.sub(r"^(SH|SZ|BJ)", "", cleaned)
    cleaned = re.sub(r"\.(SH|SZ|BJ)$", "", cleaned)
    if not re.fullmatch(r"\d{6}", cleaned):
        raise ValueError(f"Invalid A-share symbol: {symbol}")
    return cleaned


def market_prefix(symbol: str) -> str:
    code = normalize_symbol(symbol)
    if code.startswith(("6", "9")):
        return "sh"
    if code.startswith("8"):
        return "bj"
    return "sz"


def pct(value: Any, default: float = 0.0) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return default
