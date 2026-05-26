from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from stock_assistant.utils import clamp


class CapitalFlowAnalyzer:
    def analyze(self, flow: pd.DataFrame | None) -> Dict[str, Any]:
        if flow is None or flow.empty or "main_net_inflow" not in flow:
            return {
                "capital_flow_score": 50,
                "trend": "资金流数据缺失",
                "signals": [],
                "warnings": ["资金流数据缺失，不参与加减分"],
                "confidence": 0.3,
            }

        recent = flow.tail(min(5, len(flow)))
        main_sum = float(recent["main_net_inflow"].fillna(0).sum())
        positive_days = int((recent["main_net_inflow"].fillna(0) > 0).sum())
        score = 50 + min(20, positive_days * 5)
        signals: List[str] = []
        warnings: List[str] = []
        if main_sum > 0:
            score += 8
            trend = "资金净流入"
            signals.append("近期主力资金净流入")
        elif main_sum < 0:
            score -= 12
            trend = "资金净流出"
            warnings.append("近期主力资金净流出")
        else:
            trend = "资金流中性"

        return {
            "capital_flow_score": int(clamp(score)),
            "trend": trend,
            "recent_main_net_inflow": main_sum,
            "signals": signals,
            "warnings": warnings,
            "confidence": 0.65,
        }
