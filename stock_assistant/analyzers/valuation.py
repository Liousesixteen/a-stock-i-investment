from __future__ import annotations

from typing import Any, Dict, List

from stock_assistant.utils import clamp


class ValuationAnalyzer:
    def __init__(self, rules: Dict[str, Any] | None = None) -> None:
        self.rules = rules or {}

    def analyze(self, valuation: Dict[str, Any]) -> Dict[str, Any]:
        pe = self._num_or_none(valuation.get("pe_ttm"))
        pb = self._num_or_none(valuation.get("pb"))
        if pe is None and pb is None:
            return {
                "valuation_score": 50,
                "valuation_level": "估值数据缺失",
                "signals": [],
                "warnings": ["估值数据缺失，无法判断贵贱"],
                "confidence": 0.3,
            }

        score = 50
        signals: List[str] = []
        warnings: List[str] = []
        if pe is not None:
            if 0 < pe <= self.rules.get("reasonable_pe_max", 25):
                score += 12
                signals.append("PE处于可接受区间")
            elif pe > self.rules.get("high_pe", 45):
                score -= 15
                warnings.append("PE偏高，需要业绩兑现")
            elif pe <= 0:
                score -= 8
                warnings.append("PE为负或异常")
        if pb is not None:
            if 0 < pb <= self.rules.get("reasonable_pb_max", 3):
                score += 8
                signals.append("PB处于可接受区间")
            elif pb > self.rules.get("high_pb", 6):
                score -= 10
                warnings.append("PB偏高")

        score = int(clamp(score))
        if score >= 68:
            level = "合理偏低"
        elif score >= 58:
            level = "合理"
        elif score >= 45:
            level = "合理偏高"
        else:
            level = "偏高"
        return {
            "valuation_score": score,
            "valuation_level": level,
            "signals": signals,
            "warnings": warnings,
            "confidence": 0.7,
        }

    def _num_or_none(self, value: Any) -> float | None:
        try:
            if value in (None, "", "-"):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None
