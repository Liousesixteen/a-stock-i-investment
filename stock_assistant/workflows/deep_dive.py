from __future__ import annotations

from typing import Any, Dict, List

from stock_assistant.knowledge.knowledge_store import KnowledgeStore


class DeepDiveEnhancer:
    def __init__(self, store: KnowledgeStore | None = None) -> None:
        self.store = store or KnowledgeStore()

    def analyze(self, symbol: str, chain_result: Dict[str, Any]) -> Dict[str, Any]:
        chain_name = chain_result.get("chain", "")
        chain = self.store.find_chain(chain_name)
        peers = self.store.related_companies(chain_name) if chain_name else []
        target_profile = self.store.get_company_profile(symbol)
        return {
            "chain_name": chain_name,
            "chain_segments": self._segments(chain),
            "peer_companies": self._peer_rows(peers, symbol),
            "target_evidence": target_profile.get("evidence", []) if target_profile else chain_result.get("evidence", []),
            "tracking_metrics": self._tracking_metrics(chain_name),
            "risk_scenarios": self._risk_scenarios(chain.get("risks", []), chain_result.get("risks", [])),
        }

    def _segments(self, chain: Dict[str, Any]) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        for section in ["upstream", "midstream", "downstream"]:
            for item in chain.get(section, []) if chain else []:
                rows.append(
                    {
                        "layer": {"upstream": "上游", "midstream": "中游", "downstream": "下游"}[section],
                        "segment": item.get("segment", ""),
                        "description": item.get("description", ""),
                    }
                )
        return rows

    def _peer_rows(self, peers: List[Dict[str, Any]], target_symbol: str) -> List[Dict[str, Any]]:
        rows = []
        for peer in peers:
            rows.append(
                {
                    "symbol": peer.get("symbol", ""),
                    "name": peer.get("name", ""),
                    "segment": peer.get("segment", ""),
                    "benefit_type": peer.get("benefit_type", ""),
                    "confidence": peer.get("confidence", 0),
                    "is_target": peer.get("symbol") == target_symbol,
                }
            )
        return sorted(rows, key=lambda item: (not item["is_target"], -float(item.get("confidence") or 0)))

    def _tracking_metrics(self, chain_name: str) -> List[str]:
        common = ["板块成交额和涨跌扩散", "核心公司公告/订单验证", "资金流是否持续流入"]
        if chain_name == "AI算力":
            return ["云厂商资本开支", "服务器/芯片订单", "数据中心建设进度", *common]
        return common

    def _risk_scenarios(self, chain_risks: List[str], company_risks: List[str]) -> List[str]:
        risks = list(dict.fromkeys([*company_risks, *chain_risks]))
        if not risks:
            risks = ["题材退潮", "业绩兑现不及预期"]
        return [f"{risk}：若出现该情形，需要降低产业链逻辑权重和仓位上限" for risk in risks[:5]]
