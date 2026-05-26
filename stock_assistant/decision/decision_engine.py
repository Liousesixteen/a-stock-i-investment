from __future__ import annotations

from typing import Any, Dict

from stock_assistant.decision.position_sizer import PositionSizer


class DecisionEngine:
    def __init__(self) -> None:
        self.position_sizer = PositionSizer()

    def decide(
        self,
        technical: Dict[str, Any],
        market: Dict[str, Any],
        sector: Dict[str, Any],
        chain: Dict[str, Any],
        risk: Dict[str, Any],
        fundamental: Dict[str, Any] | None = None,
        valuation: Dict[str, Any] | None = None,
        capital_flow: Dict[str, Any] | None = None,
        announcement: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        fundamental = fundamental or {"fundamental_score": 50}
        valuation = valuation or {"valuation_score": 50}
        capital_flow = capital_flow or {"capital_flow_score": 50}
        announcement = announcement or {"announcement_score": 50}
        score = (
            technical["technical_score"] * 0.22
            + market["market_score"] * 0.14
            + sector["sector_score"] * 0.14
            + chain["industry_chain_score"] * 0.14
            + fundamental["fundamental_score"] * 0.12
            + valuation["valuation_score"] * 0.08
            + capital_flow["capital_flow_score"] * 0.08
            + announcement["announcement_score"] * 0.04
            + (100 - risk["risk_score"]) * 0.04
        )
        if risk["hard_blocks"] or risk["risk_level"] == "高":
            action = "avoid"
            conclusion = "风险优先，暂不参与"
        elif score >= 70 and risk["risk_level"] in {"低", "中"}:
            action = "buy_with_plan"
            conclusion = "可小仓位按计划试错"
        elif score >= 58:
            action = "watch"
            conclusion = "观察为主，等待回踩或确认信号"
        else:
            action = "avoid"
            conclusion = "胜率和赔率都不清晰，暂不操作"
        position = self.position_sizer.suggest(risk["risk_level"], action)
        return {
            "overall_score": round(score, 1),
            "action": action,
            "conclusion": conclusion,
            "position": position,
            "invalid_conditions": [
                "跌破关键支撑位并放量",
                "所属板块明显转弱",
                "出现减持、监管、业绩不及预期等重大利空",
            ],
        }
