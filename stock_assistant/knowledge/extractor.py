from __future__ import annotations

from typing import Any, Dict, List


class KnowledgeExtractor:
    RULES = [
        {
            "keywords": ["AI算力", "算力", "服务器", "数据中心"],
            "chain": "AI算力",
            "segment": "算力基础设施",
            "confidence": 0.62,
        },
        {
            "keywords": ["AI芯片", "智能处理器", "国产算力"],
            "chain": "AI算力",
            "segment": "AI芯片",
            "confidence": 0.64,
        },
        {
            "keywords": ["动力电池", "储能", "电芯"],
            "chain": "新能源车",
            "segment": "动力电池/整车",
            "confidence": 0.65,
        },
        {
            "keywords": ["减速器", "丝杠", "机器人本体"],
            "chain": "机器人",
            "segment": "核心零部件",
            "confidence": 0.6,
        },
        {
            "keywords": ["固态电解质", "半固态", "固态电池"],
            "chain": "固态电池",
            "segment": "材料体系",
            "confidence": 0.6,
        },
    ]

    def extract(self, evidence: Dict[str, Any]) -> List[Dict[str, Any]]:
        text = f"{evidence.get('title', '')} {evidence.get('summary', '')} {evidence.get('text', '')} {evidence.get('raw_text', '')}"
        rows = []
        for rule in self.RULES:
            matched = [keyword for keyword in rule["keywords"] if keyword in text]
            if matched:
                rows.append(
                    {
                        "symbol": evidence.get("symbol", ""),
                        "source": evidence.get("source", ""),
                        "chain": rule["chain"],
                        "segment": rule["segment"],
                        "relation": "BELONGS_TO",
                        "matched_keywords": matched,
                        "confidence": rule["confidence"],
                        "status": "observed",
                        "evidence_title": evidence.get("title", ""),
                    }
                )
        return rows
