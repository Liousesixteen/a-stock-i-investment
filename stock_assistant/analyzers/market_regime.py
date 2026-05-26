from __future__ import annotations

from typing import Any, Dict

from stock_assistant.data_gateway import AStockDataGateway


class MarketRegimeAnalyzer:
    def __init__(self, gateway: AStockDataGateway) -> None:
        self.gateway = gateway

    def analyze(self) -> Dict[str, Any]:
        bars = self.gateway.get_index_bars("000001")
        if bars.empty:
            return {"market_score": 50, "regime": "大盘数据缺失", "summary": "大盘环境使用中性处理", "confidence": 0.3}
        latest = bars.iloc[-1]
        score = 55 + float(latest.get("pct_chg", 0)) * 10
        regime = "震荡偏强" if score >= 58 else "震荡" if score >= 45 else "偏弱"
        return {
            "market_score": round(score, 1),
            "regime": regime,
            "summary": f"主要指数最近涨跌幅 {latest.get('pct_chg', 0)}%，市场处于{regime}状态",
            "confidence": 0.7,
        }
