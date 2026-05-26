from __future__ import annotations

from typing import Any, Dict, List

from stock_assistant.data_gateway import AStockDataGateway


class SectorRotationAnalyzer:
    def __init__(self, gateway: AStockDataGateway) -> None:
        self.gateway = gateway

    def analyze_for_stock(self, industry: str) -> Dict[str, Any]:
        sectors = self.gateway.get_sector_performance()
        if sectors.empty:
            return {"sector_score": 50, "sector_status": "板块数据缺失", "strong_sectors": [], "confidence": 0.3}
        strong: List[str] = sectors.sort_values("pct_chg", ascending=False).head(3)["sector"].tolist()
        matched = sectors[sectors["sector"] == industry]
        if matched.empty:
            return {"sector_score": 50, "sector_status": "行业未匹配，板块中性处理", "strong_sectors": strong, "confidence": 0.4}
        pct = float(matched.iloc[0]["pct_chg"])
        return {
            "sector_score": min(85, max(35, 50 + pct * 10)),
            "sector_status": f"{industry}板块{matched.iloc[0].get('strength', '中性')}",
            "strong_sectors": strong,
            "confidence": 0.7,
        }
