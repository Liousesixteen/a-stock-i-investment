from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd


POSITIVE_KEYWORDS = {
    "政策利好": ["降准", "降息", "稳增长", "活跃资本市场", "提振信心", "回购", "增持", "减税", "扩内需", "新质生产力"],
    "流动性利好": ["流动性合理充裕", "净投放", "MLF", "逆回购", "社融超预期", "信贷扩张"],
    "产业利好": ["订单增长", "中标", "突破", "涨价", "景气", "出口增长", "AI", "算力", "半导体", "机器人"],
    "外围利好": ["美股上涨", "纳指上涨", "降息预期升温", "人民币升值", "风险偏好回升"],
}

NEGATIVE_KEYWORDS = {
    "政策/监管压力": ["立案", "处罚", "监管趋严", "问询函", "退市", "减持", "IPO抽血"],
    "宏观利空": ["PMI回落", "CPI低于预期", "PPI下降", "社融低于预期", "地产下行", "出口回落", "通缩"],
    "外围利空": ["美股下跌", "纳指下跌", "加息", "美元走强", "人民币贬值", "地缘冲突", "制裁"],
    "产业利空": ["价格战", "订单取消", "业绩预亏", "毛利率下降", "库存高企", "需求放缓"],
}

RUMOR_KEYWORDS = ["传闻", "网传", "小道消息", "未证实", "市场传言", "据传"]


class MarketSentimentAnalyzer:
    def analyze(
        self,
        snapshot: Dict[str, Any],
        sectors: pd.DataFrame,
        news: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        news = news or []
        score = 50.0
        factors: List[str] = []

        index_score, index_factor = self._score_indices(snapshot.get("indices", []))
        score += index_score
        factors.append(index_factor)

        north_score, north_factor = self._score_northbound(snapshot.get("northbound", {}))
        score += north_score
        factors.append(north_factor)

        sector_score, sector_factor = self._score_sectors(sectors)
        score += sector_score
        factors.append(sector_factor)

        news_result = self._score_news(news)
        score += news_result["score_delta"]
        factors.extend(news_result["factors"])

        bounded = round(max(0, min(100, score)), 1)
        return {
            "sentiment_score": bounded,
            "level": self._level(bounded),
            "factors": factors,
            "news_radar": news_result["radar"],
            "rumors": news_result["rumors"],
            "confidence": self._confidence(snapshot, sectors, news),
        }

    def _score_indices(self, indices: List[Dict[str, Any]]) -> tuple[float, str]:
        if not indices:
            return 0.0, "指数数据缺失，情绪按中性处理"
        pct_values = [self._to_float(item.get("pct_chg")) for item in indices]
        avg_pct = sum(pct_values) / len(pct_values)
        up = sum(1 for value in pct_values if value > 0)
        down = sum(1 for value in pct_values if value < 0)
        delta = avg_pct * 4 + (up - down) * 1.5
        return delta, f"指数平均涨跌幅 {round(avg_pct, 2)}%，上涨指数 {up} 个、下跌指数 {down} 个"

    def _score_northbound(self, northbound: Dict[str, Any]) -> tuple[float, str]:
        net_yi = self._to_float(northbound.get("net_inflow")) / 100000000
        if net_yi >= 50:
            return 8.0, f"北向资金大幅净流入 {round(net_yi, 2)} 亿"
        if net_yi >= 10:
            return 4.0, f"北向资金净流入 {round(net_yi, 2)} 亿"
        if net_yi <= -50:
            return -8.0, f"北向资金大幅净流出 {round(net_yi, 2)} 亿"
        if net_yi <= -10:
            return -4.0, f"北向资金净流出 {round(net_yi, 2)} 亿"
        return 0.0, f"北向资金小幅波动 {round(net_yi, 2)} 亿"

    def _score_sectors(self, sectors: pd.DataFrame) -> tuple[float, str]:
        if sectors.empty or "pct_chg" not in sectors:
            return 0.0, "板块数据缺失，情绪按中性处理"
        pct = pd.to_numeric(sectors["pct_chg"], errors="coerce").dropna()
        if pct.empty:
            return 0.0, "板块涨跌数据缺失，情绪按中性处理"
        strong = int((pct > 1).sum())
        weak = int((pct < -1).sum())
        delta = (strong - weak) * 1.5 + float(pct.mean()) * 2
        return delta, f"强势板块 {strong} 个、弱势板块 {weak} 个，板块平均涨跌幅 {round(float(pct.mean()), 2)}%"

    def _score_news(self, news: List[Dict[str, Any]]) -> Dict[str, Any]:
        radar = {"利好": [], "利空": [], "中性/待验证": []}
        rumors = []
        score_delta = 0.0
        factors = []
        for item in news[:30]:
            text = " ".join(str(item.get(key, "")) for key in ("title", "summary", "content", "raw_text"))
            title = str(item.get("title") or item.get("summary") or "未命名消息")[:80]
            if any(keyword in text for keyword in RUMOR_KEYWORDS):
                rumors.append(title)
                radar["中性/待验证"].append(title)
                continue
            positive_tags = self._match_tags(text, POSITIVE_KEYWORDS)
            negative_tags = self._match_tags(text, NEGATIVE_KEYWORDS)
            if positive_tags and not negative_tags:
                radar["利好"].append(f"{title}（{'/'.join(positive_tags)}）")
                score_delta += 2.0
            elif negative_tags and not positive_tags:
                radar["利空"].append(f"{title}（{'/'.join(negative_tags)}）")
                score_delta -= 2.5
            elif positive_tags or negative_tags:
                radar["中性/待验证"].append(f"{title}（多空交织）")

        if radar["利好"]:
            factors.append(f"消息面利好 {len(radar['利好'])} 条")
        if radar["利空"]:
            factors.append(f"消息面利空 {len(radar['利空'])} 条")
        if rumors:
            factors.append(f"未证实/传闻类消息 {len(rumors)} 条，不能作为交易依据")
        return {"score_delta": max(-12, min(12, score_delta)), "factors": factors, "radar": radar, "rumors": rumors}

    def _match_tags(self, text: str, groups: Dict[str, List[str]]) -> List[str]:
        return [tag for tag, keywords in groups.items() if any(keyword in text for keyword in keywords)]

    def _level(self, score: float) -> str:
        if score >= 70:
            return "情绪偏热"
        if score >= 58:
            return "情绪偏强"
        if score >= 43:
            return "情绪中性"
        if score >= 30:
            return "情绪偏弱"
        return "情绪冰点"

    def _confidence(self, snapshot: Dict[str, Any], sectors: pd.DataFrame, news: List[Dict[str, Any]]) -> float:
        confidence = 0.35
        if snapshot.get("indices"):
            confidence += 0.2
        if snapshot.get("northbound"):
            confidence += 0.15
        if not sectors.empty:
            confidence += 0.15
        if news:
            confidence += 0.15
        return round(min(0.9, confidence), 2)

    def _to_float(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
