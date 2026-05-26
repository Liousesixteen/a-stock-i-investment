from __future__ import annotations

from typing import Any, Dict, List

from stock_assistant.knowledge.knowledge_store import KnowledgeStore


class IndustryChainAnalyzer:
    def __init__(self, store: KnowledgeStore | None = None) -> None:
        self.store = store or KnowledgeStore()

    def analyze_company_position(self, basic: Dict[str, Any], mode: str = "standard") -> Dict[str, Any]:
        concepts: List[str] = basic.get("concepts", [])
        industry = basic.get("industry", "未知行业")
        symbol = basic.get("symbol", "")
        profile = self.store.match_company(symbol, concepts=concepts, industry=industry)
        if profile and profile.get("chain"):
            confidence = float(profile.get("confidence", 0.55) or 0.55)
            benefit_type = profile.get("benefit_type", "受益类型未知")
            score = 50 + int(confidence * 30)
            if benefit_type == "直接受益":
                score += 8
            elif benefit_type == "间接受益":
                score += 3
            risks = profile.get("risks", []) or ["产业链证据需要动态验证"]
            return {
                "chain": profile.get("chain", industry),
                "segment": profile.get("segment", "行业粗分类"),
                "benefit_type": benefit_type,
                "industry_chain_score": min(88, score),
                "summary": f"知识库定位：{profile.get('name', symbol)}处于{profile.get('chain')}的{profile.get('segment')}环节，{benefit_type}",
                "risks": risks,
                "confidence": confidence,
                "evidence": profile.get("evidence", []),
            }
        if "AI算力" in concepts or "数据中心" in concepts:
            return {
                "chain": "AI算力",
                "segment": "中游算力基础设施",
                "benefit_type": "直接受益",
                "industry_chain_score": 72,
                "summary": "公司与AI算力/数据中心方向相关，属于偏直接受益的基础设施环节",
                "risks": ["若订单和业绩无法验证，可能退化为题材交易"],
                "confidence": 0.65,
            }
        if "人工智能" in concepts or "机器人" in concepts:
            return {
                "chain": "AI应用与智能设备",
                "segment": "下游场景应用",
                "benefit_type": "间接受益",
                "industry_chain_score": 62,
                "summary": "公司处于智能化应用场景，产业链逻辑需要公告、订单和财务继续验证",
                "risks": ["题材相关度高于业绩兑现度，警惕蹭概念风险"],
                "confidence": 0.58,
            }
        return {
            "chain": industry,
            "segment": "行业粗分类",
            "benefit_type": "受益类型未知",
            "industry_chain_score": 50,
            "summary": "产业链匹配不足，暂按行业粗分类处理",
            "risks": ["产业链证据不足"],
            "confidence": 0.35,
        }
