from __future__ import annotations

from typing import Any, Dict, List

from stock_assistant.utils import clamp


class FundamentalAnalyzer:
    def __init__(self, rules: Dict[str, Any] | None = None) -> None:
        self.rules = rules or {}

    def analyze(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        if not snapshot or (snapshot.get("revenue_yoy") is None and snapshot.get("net_profit_yoy") is None):
            return {
                "fundamental_score": 50,
                "quality": "财务数据缺失",
                "signals": [],
                "warnings": ["财务数据缺失，基本面判断置信度降低"],
                "confidence": 0.3,
            }

        score = 50
        signals: List[str] = []
        warnings: List[str] = []
        revenue_yoy = self._num(snapshot.get("revenue_yoy"))
        profit_yoy = self._num(snapshot.get("net_profit_yoy"))
        roe = self._num(snapshot.get("roe"))
        debt_ratio = self._num(snapshot.get("debt_ratio"))
        ocf = self._num(snapshot.get("operating_cashflow"))
        net_profit = self._num(snapshot.get("net_profit"))

        if revenue_yoy >= self.rules.get("strong_revenue_yoy", 10):
            score += 10
            signals.append("营收保持增长")
        elif revenue_yoy < self.rules.get("warn_if_revenue_yoy_below", 0):
            score -= 10
            warnings.append("营收同比下滑")

        if profit_yoy >= self.rules.get("strong_net_profit_yoy", 10):
            score += 12
            signals.append("净利润保持增长")
        elif profit_yoy < self.rules.get("warn_if_net_profit_yoy_below", 0):
            score -= 12
            warnings.append("净利润同比下滑")

        if roe >= self.rules.get("strong_roe", 12):
            score += 8
            signals.append("ROE水平较好")
        elif roe and roe < self.rules.get("warn_if_roe_below", 5):
            score -= 6
            warnings.append("ROE偏低")

        if debt_ratio > self.rules.get("warn_if_debt_ratio_above", 70):
            score -= 12
            warnings.append("资产负债率偏高")
        elif debt_ratio and debt_ratio < self.rules.get("healthy_debt_ratio_below", 45):
            score += 4
            signals.append("负债率相对可控")

        if self.rules.get("warn_if_ocf_negative", True) and ocf < 0:
            score -= 10
            warnings.append("经营现金流为负")
        elif net_profit and ocf >= net_profit:
            score += 6
            signals.append("经营现金流覆盖利润")

        score = int(clamp(score))
        quality = "基本面偏强" if score >= 70 else "基本面中性" if score >= 45 else "基本面偏弱"
        return {
            "fundamental_score": score,
            "quality": quality,
            "signals": signals,
            "warnings": warnings,
            "confidence": 0.75,
        }

    def _num(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0
