from __future__ import annotations

from typing import Any, Dict, List


class RiskAnalyzer:
    def analyze(
        self,
        quote: Dict[str, Any],
        technical: Dict[str, Any],
        chain: Dict[str, Any],
        fundamental: Dict[str, Any] | None = None,
        valuation: Dict[str, Any] | None = None,
        capital_flow: Dict[str, Any] | None = None,
        announcement: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        warnings: List[str] = []
        hard_blocks: List[str] = []
        pct_chg = float(quote.get("pct_chg") or 0)
        pe_ttm = quote.get("pe_ttm")
        if pct_chg > 7:
            warnings.append("短线涨幅较大，追高风险上升")
        if pe_ttm and pe_ttm > 45:
            warnings.append("估值偏高，需要业绩继续兑现")
        warnings.extend(technical.get("warnings", []))
        warnings.extend(chain.get("risks", []))
        for payload in [fundamental, valuation, capital_flow, announcement]:
            if payload:
                warnings.extend(payload.get("warnings", []))
                hard_blocks.extend(payload.get("hard_blocks", []))

        risk_score = 45 + len(warnings) * 8 + len(hard_blocks) * 30
        if risk_score >= 75:
            level = "高"
        elif risk_score >= 60:
            level = "中高"
        elif risk_score >= 40:
            level = "中"
        else:
            level = "低"
        return {
            "risk_level": level,
            "risk_score": min(100, risk_score),
            "warnings": warnings or ["未触发硬性风险，但仍需控制仓位"],
            "hard_blocks": hard_blocks,
        }
