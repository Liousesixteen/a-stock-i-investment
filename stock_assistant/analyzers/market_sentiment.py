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

EVENT_RULES = [
    ("国内政策", "全市场", ["降准", "降息", "稳增长", "活跃资本市场", "财政", "货币政策", "扩内需", "新质生产力"]),
    ("宏观数据", "全市场", ["PMI", "CPI", "PPI", "社融", "信贷", "工业增加值", "消费", "出口", "地产"]),
    ("资金流动性", "全市场", ["北向", "融资余额", "ETF", "成交额", "净投放", "逆回购", "MLF"]),
    ("外围市场", "全市场", ["美股", "纳指", "标普", "美元", "人民币", "美债", "降息预期", "加息", "地缘", "制裁"]),
    ("产业事件", "行业/主题", ["AI", "算力", "半导体", "机器人", "新能源", "医药", "订单", "中标", "涨价", "价格战"]),
    ("监管/风险", "个股/行业", ["立案", "处罚", "问询函", "退市", "减持", "业绩预亏", "库存高企"]),
    ("传闻待证", "待验证", RUMOR_KEYWORDS),
]


class MarketSentimentAnalyzer:
    def analyze(
        self,
        snapshot: Dict[str, Any],
        sectors: pd.DataFrame,
        news: List[Dict[str, Any]] | None = None,
        concepts: pd.DataFrame | None = None,
    ) -> Dict[str, Any]:
        news = news or []
        concepts = concepts if concepts is not None else pd.DataFrame()
        factors: List[str] = []
        components = [
            self._score_indices(snapshot.get("indices", [])),
            self._score_liquidity(snapshot),
            self._score_northbound(snapshot.get("northbound", {})),
            self._score_sectors(sectors),
            self._score_concepts(concepts),
        ]
        for component in components:
            factors.append(component["signal"])

        news_result = self._score_news(news)
        components.append(news_result["component"])
        factors.extend(news_result["factors"])

        score = sum(component["score"] for component in components)
        bounded = round(max(0, min(100, score)), 1)
        return {
            "sentiment_score": bounded,
            "level": self._level(bounded),
            "components": components,
            "factors": factors,
            "news_radar": news_result["radar"],
            "events": news_result["events"],
            "rumors": news_result["rumors"],
            "confidence": self._confidence(snapshot, sectors, news, concepts),
        }

    def _score_indices(self, indices: List[Dict[str, Any]]) -> Dict[str, Any]:
        weight = 20.0
        if not indices:
            return self._component("指数表现", weight / 2, weight, "指数数据缺失，按中性处理")
        pct_values = [self._to_float(item.get("pct_chg")) for item in indices]
        avg_pct = sum(pct_values) / len(pct_values)
        up = sum(1 for value in pct_values if value > 0)
        down = sum(1 for value in pct_values if value < 0)
        breadth = up / len(pct_values)
        pct_score = self._scale(avg_pct, -2.0, 2.0) * 12
        breadth_score = breadth * 8
        score = max(0, min(weight, pct_score + breadth_score))
        return self._component(
            "指数表现",
            score,
            weight,
            f"指数平均涨跌幅 {round(avg_pct, 2)}%，上涨指数 {up} 个、下跌指数 {down} 个",
        )

    def _score_liquidity(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        weight = 15.0
        total_yi = self._to_float(snapshot.get("total_amount")) / 100000000
        if total_yi <= 0:
            return self._component("量能流动性", weight / 2, weight, "成交额数据缺失，按中性处理")
        if total_yi >= 20000:
            score = 14.0
            signal = f"主要指数合计成交额 {round(total_yi, 1)} 亿，流动性活跃"
        elif total_yi >= 12000:
            score = 11.0
            signal = f"主要指数合计成交额 {round(total_yi, 1)} 亿，量能尚可"
        elif total_yi >= 8000:
            score = 8.0
            signal = f"主要指数合计成交额 {round(total_yi, 1)} 亿，量能中性"
        else:
            score = 5.0
            signal = f"主要指数合计成交额 {round(total_yi, 1)} 亿，量能偏弱"
        return self._component("量能流动性", score, weight, signal)

    def _score_northbound(self, northbound: Dict[str, Any]) -> Dict[str, Any]:
        weight = 15.0
        net_yi = self._to_float(northbound.get("net_inflow")) / 100000000
        if not northbound:
            return self._component("北向资金", weight / 2, weight, "北向资金缺失，按中性处理")
        if net_yi >= 50:
            score = 14.0
        elif net_yi >= 10:
            score = 11.0
        elif net_yi <= -50:
            score = 2.0
        elif net_yi <= -10:
            score = 5.0
        else:
            score = 8.0
        return self._component("北向资金", score, weight, f"北向资金净流入 {round(net_yi, 2)} 亿")

    def _score_sectors(self, sectors: pd.DataFrame) -> Dict[str, Any]:
        weight = 20.0
        if sectors.empty or "pct_chg" not in sectors:
            return self._component("板块扩散", weight / 2, weight, "板块数据缺失，按中性处理")
        pct = pd.to_numeric(sectors["pct_chg"], errors="coerce").dropna()
        if pct.empty:
            return self._component("板块扩散", weight / 2, weight, "板块涨跌数据缺失，按中性处理")
        strong = int((pct > 1).sum())
        weak = int((pct < -1).sum())
        positive_ratio = float((pct > 0).sum()) / len(pct)
        mean_score = self._scale(float(pct.mean()), -2.0, 2.0) * 8
        diffusion_score = positive_ratio * 8
        strong_weak_score = max(0, min(4, 2 + (strong - weak) * 0.8))
        score = max(0, min(weight, mean_score + diffusion_score + strong_weak_score))
        return self._component(
            "板块扩散",
            score,
            weight,
            f"强势板块 {strong} 个、弱势板块 {weak} 个，板块平均涨跌幅 {round(float(pct.mean()), 2)}%",
        )

    def _score_concepts(self, concepts: pd.DataFrame) -> Dict[str, Any]:
        weight = 10.0
        if concepts.empty:
            return self._component("题材热度", weight / 2, weight, "题材热度数据缺失，按中性处理")
        heat = pd.to_numeric(concepts.get("heat", pd.Series(dtype=float)), errors="coerce").dropna()
        pct = pd.to_numeric(concepts.get("pct_chg", pd.Series(dtype=float)), errors="coerce").dropna()
        heat_score = self._scale(float(heat.mean()) if not heat.empty else 50, 0, 100) * 5
        pct_score = self._scale(float(pct.mean()) if not pct.empty else 0, -3, 3) * 5
        names = concepts.get("concept", pd.Series(dtype=str)).head(3).tolist() if "concept" in concepts else []
        signal = f"热门题材：{'、'.join(str(name) for name in names) if names else '缺失'}"
        return self._component("题材热度", max(0, min(weight, heat_score + pct_score)), weight, signal)

    def _score_news(self, news: List[Dict[str, Any]]) -> Dict[str, Any]:
        weight = 20.0
        radar = {"利好": [], "利空": [], "中性/待验证": []}
        rumors = []
        events = []
        raw_score = weight / 2
        factors = []
        if not news:
            return {
                "component": self._component("消息面", raw_score, weight, "未获取到真实市场新闻，消息面按中性但降低置信度"),
                "factors": ["真实市场新闻缺失，未使用 sample 降级数据"],
                "radar": radar,
                "events": events,
                "rumors": rumors,
            }
        for item in news[:30]:
            text = " ".join(str(item.get(key, "")) for key in ("title", "summary", "content", "raw_text"))
            title = str(item.get("title") or item.get("summary") or "未命名消息")[:80]
            event = self._extract_event(item, text, title)
            events.append(event)
            if any(keyword in text for keyword in RUMOR_KEYWORDS):
                rumors.append(title)
                radar["中性/待验证"].append(title)
                raw_score -= 0.5
                continue
            positive_tags = self._match_tags(text, POSITIVE_KEYWORDS)
            negative_tags = self._match_tags(text, NEGATIVE_KEYWORDS)
            if positive_tags and not negative_tags:
                radar["利好"].append(f"{title}（{'/'.join(positive_tags)}）")
                raw_score += self._news_weight(item, positive_tags)
            elif negative_tags and not positive_tags:
                radar["利空"].append(f"{title}（{'/'.join(negative_tags)}）")
                raw_score -= self._news_weight(item, negative_tags)
            elif positive_tags or negative_tags:
                radar["中性/待验证"].append(f"{title}（多空交织）")

        if radar["利好"]:
            factors.append(f"消息面利好 {len(radar['利好'])} 条")
        if radar["利空"]:
            factors.append(f"消息面利空 {len(radar['利空'])} 条")
        if rumors:
            factors.append(f"未证实/传闻类消息 {len(rumors)} 条，不能作为交易依据")
        news_signal = f"消息面利好 {len(radar['利好'])} 条、利空 {len(radar['利空'])} 条、待验证 {len(radar['中性/待验证'])} 条"
        return {
            "component": self._component("消息面", max(0, min(weight, raw_score)), weight, news_signal),
            "factors": factors,
            "radar": radar,
            "events": events,
            "rumors": rumors,
        }

    def _extract_event(self, item: Dict[str, Any], text: str, title: str) -> Dict[str, Any]:
        positive_tags = self._match_tags(text, POSITIVE_KEYWORDS)
        negative_tags = self._match_tags(text, NEGATIVE_KEYWORDS)
        category = "一般资讯"
        scope = "待判断"
        for matched_category, matched_scope, keywords in EVENT_RULES:
            if any(keyword in text for keyword in keywords):
                category = matched_category
                scope = matched_scope
                break
        if any(keyword in text for keyword in RUMOR_KEYWORDS):
            direction = "待验证"
        elif positive_tags and not negative_tags:
            direction = "利好"
        elif negative_tags and not positive_tags:
            direction = "利空"
        elif positive_tags or negative_tags:
            direction = "多空交织"
        else:
            direction = "中性"
        source_tier = self._source_tier(item)
        confidence = self._event_confidence(direction, source_tier)
        return {
            "title": title,
            "category": category,
            "scope": scope,
            "direction": direction,
            "source": item.get("source", ""),
            "source_tier": source_tier,
            "confidence": confidence,
            "publish_time": item.get("publish_time") or item.get("time") or "",
        }

    def _news_weight(self, item: Dict[str, Any], tags: List[str]) -> float:
        source = str(item.get("source", "")).lower()
        source_weight = 1.0
        if self._source_tier(item) == "official":
            source_weight = 1.8
        elif self._source_tier(item) == "mainstream":
            source_weight = 1.2
        tag_weight = 1.4 if any("政策" in tag or "宏观" in tag or "外围" in tag for tag in tags) else 1.0
        return min(3.0, source_weight * tag_weight)

    def _source_tier(self, item: Dict[str, Any]) -> str:
        source = str(item.get("source", "")).lower()
        text = " ".join(str(item.get(key, "")) for key in ("title", "summary", "content", "raw_text")).lower()
        official_source_names = ["pbc", "csrc", "stats", "gov", "上交所", "深交所", "北交所", "国务院", "证监会", "统计局", "官方"]
        official_text_names = ["中国人民银行", "证监会发布", "国家统计局", "国务院新闻办公室", "上交所发布", "深交所发布", "北交所发布"]
        mainstream_names = ["cls", "eastmoney", "futu", "sina", "ths", "财联社", "东财", "富途", "新浪", "同花顺", "央视"]
        if any(name in source for name in official_source_names) or any(name in text for name in official_text_names):
            return "official"
        if any(name in source or name in text for name in mainstream_names):
            return "mainstream"
        return "unknown"

    def _event_confidence(self, direction: str, source_tier: str) -> float:
        if direction == "待验证":
            return 0.25
        base = {"official": 0.9, "mainstream": 0.72, "unknown": 0.5}.get(source_tier, 0.5)
        return base

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

    def _confidence(self, snapshot: Dict[str, Any], sectors: pd.DataFrame, news: List[Dict[str, Any]], concepts: pd.DataFrame) -> float:
        confidence = 0.35
        if snapshot.get("indices"):
            confidence += 0.15
        if snapshot.get("total_amount"):
            confidence += 0.1
        if snapshot.get("northbound"):
            confidence += 0.15
        if not sectors.empty:
            confidence += 0.15
        if not concepts.empty:
            confidence += 0.1
        if news:
            confidence += 0.15
        return round(min(0.9, confidence), 2)

    def _component(self, name: str, score: float, max_score: float, signal: str) -> Dict[str, Any]:
        return {"name": name, "score": round(score, 1), "max_score": max_score, "signal": signal}

    def _scale(self, value: float, low: float, high: float) -> float:
        if high <= low:
            return 0.5
        return max(0.0, min(1.0, (value - low) / (high - low)))

    def _to_float(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
