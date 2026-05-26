from __future__ import annotations

from typing import Any, Dict, List

from stock_assistant.analyzers.market_sentiment import MarketSentimentAnalyzer
from stock_assistant.data_gateway import AStockDataGateway


class MarketSentimentWorkflow:
    def __init__(self, gateway: AStockDataGateway | None = None) -> None:
        self.gateway = gateway or AStockDataGateway()
        self.analyzer = MarketSentimentAnalyzer()

    def analyze(self) -> Dict[str, Any]:
        snapshot = self.gateway.get_market_snapshot()
        sectors = self.gateway.get_sector_performance()
        news = self.gateway.get_market_news() if hasattr(self.gateway, "get_market_news") else []
        result = self.analyzer.analyze(snapshot, sectors, news)
        result["snapshot"] = snapshot
        result["news"] = news
        return result

    def render(self) -> str:
        result = self.analyze()
        snapshot = result["snapshot"]
        radar = result["news_radar"]
        factors = "\n".join(f"- {item}" for item in result["factors"]) or "- 暂无明显情绪驱动因子"
        good = self._render_items(radar.get("利好", []))
        bad = self._render_items(radar.get("利空", []))
        neutral = self._render_items(radar.get("中性/待验证", []))
        rumors = self._render_items(result.get("rumors", []))
        return f"""# A 股市场情绪与消息面雷达

## 情绪结论

- 情绪评分：{result['sentiment_score']}/100
- 情绪状态：{result['level']}
- 置信度：{result['confidence']}
- 大盘摘要：{snapshot.get('summary', '市场摘要缺失')}

## 主要驱动

{factors}

## 最新消息雷达

### 利好

{good}

### 利空

{bad}

### 中性/待验证

{neutral}

### 小道消息/传闻

{rumors}

## 需要持续跟踪的影响变量

- 国内政策：货币政策、财政发力、资本市场制度、地产/消费/科技产业政策。
- 宏观数据：PMI、社融信贷、CPI/PPI、工业增加值、消费、出口、地产链数据。
- 资金面：北向资金、两融余额、ETF 申赎、成交额、主线板块资金持续性。
- 外围市场：美股/港股、美元指数、人民币汇率、美债利率、商品价格、地缘事件。
- 市场微观结构：涨跌家数、连板高度、跌停数量、龙虎榜机构席位、热门题材退潮信号。

## 使用纪律

传闻和未证实消息只作为观察项，不能单独作为买卖依据；情绪偏热时降低追涨，情绪偏弱时先看止跌和量能修复。
"""

    def _render_items(self, items: List[str], limit: int = 5) -> str:
        if not items:
            return "- 暂无"
        return "\n".join(f"- {item}" for item in items[:limit])
