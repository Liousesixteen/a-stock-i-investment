from __future__ import annotations

from stock_assistant.analyzers.market_regime import MarketRegimeAnalyzer
from stock_assistant.analyzers.market_sentiment import MarketSentimentAnalyzer
from stock_assistant.data_gateway import AStockDataGateway


class MorningBriefWorkflow:
    def __init__(self, gateway: AStockDataGateway | None = None) -> None:
        self.gateway = gateway or AStockDataGateway()

    def refresh_market_cache(self) -> str:
        market = MarketRegimeAnalyzer(self.gateway).analyze()
        sectors = self.gateway.get_sector_performance().to_dict("records")
        self.gateway.cache.write("market_context", {"market": market, "sectors": sectors}, 60 * 30, "AStockDataGateway")
        return "market_context refreshed"

    def render(self) -> str:
        market = MarketRegimeAnalyzer(self.gateway).analyze()
        sectors = self.gateway.get_sector_performance().sort_values("pct_chg", ascending=False).head(3)
        sector_text = "、".join(sectors["sector"].tolist())
        return f"""# 盘前简报

## 今日市场状态

{market['summary']}

## 建议总仓位

震荡偏强时仍控制节奏，建议权益仓位不超过 50%-60%，单票严格按风险等级限制。

## 强势板块

{sector_text}

## 今日纪律

不追高、不满仓、不因单一消息重仓，所有交易必须先写失效条件。
"""

    def close_review(self) -> str:
        snapshot = self.gateway.get_market_snapshot() if hasattr(self.gateway, "get_market_snapshot") else None
        sectors = self.gateway.get_sector_performance().sort_values("pct_chg", ascending=False)
        concepts = self.gateway.get_concept_performance() if hasattr(self.gateway, "get_concept_performance") else None
        news = self.gateway.get_market_news() if hasattr(self.gateway, "get_market_news") else []
        sentiment = MarketSentimentAnalyzer().analyze(snapshot or {}, sectors, news, concepts)
        strong_names = sectors.head(3)["sector"].tolist()
        weak_names = [name for name in sectors.tail(3)["sector"].tolist() if name not in strong_names]
        strong = "、".join(str(name) for name in strong_names) or "板块数据不足"
        weak = "、".join(str(name) for name in weak_names) or "板块数据不足"
        if snapshot:
            indices = "\n".join(
                f"- {item['name']}：{item['price']}（{item['pct_chg']}%）"
                for item in snapshot.get("indices", [])
            )
            north = snapshot.get("northbound", {})
            north_text = f"{north.get('status', '未知')}（{round(float(north.get('net_inflow', 0)) / 100000000, 2)} 亿）"
            scenarios = snapshot.get("scenarios", {})
            return f"""# 盘后复盘

## 今日市场状态

{snapshot.get('summary', '市场状态待确认')}

## 指数表现

{indices}

## 资金与量能

- 北向资金：{north_text}
- 主要指数合计成交额：{round(float(snapshot.get('total_amount', 0)) / 100000000, 1)} 亿

## 市场情绪与消息面

- 情绪评分：{sentiment['sentiment_score']}/100，{sentiment['level']}
- 主要驱动：{"；".join(sentiment['factors'][:3]) if sentiment['factors'] else "暂无明显情绪驱动因子"}
- 评分拆解：{"；".join(f"{item['name']} {item['score']}/{item['max_score']}" for item in sentiment['components'][:4])}
- 消息面：利好 {len(sentiment['news_radar'].get('利好', []))} 条，利空 {len(sentiment['news_radar'].get('利空', []))} 条，传闻/待验证 {len(sentiment.get('rumors', []))} 条

## 强弱板块

- 强势板块：{strong}
- 弱势板块：{weak}

## 明日情景

- 基准：{scenarios.get('base', '震荡观察')}
- 偏强：{scenarios.get('bull', '放量突破则转强')}
- 偏弱：{scenarios.get('bear', '跌破支撑则控风险')}

## 明日计划

只观察强势板块中回踩不破的标的；不追涨，不因盘中情绪临时加仓。
"""
        market = MarketRegimeAnalyzer(self.gateway).analyze()
        return f"""# 盘后复盘

## 今日市场状态

{market['summary']}

## 强弱板块

- 强势板块：{strong}
- 弱势板块：{weak}

## 持仓风险

检查单票是否跌破计划止损位，若板块退潮或放量破位，优先降低风险敞口。

## 明日计划

只观察强势板块中回踩不破的标的；不追涨，不因盘中情绪临时加仓。
"""
