from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from stock_assistant.config_loader import load_yaml


class KnowledgeStore:
    def __init__(
        self,
        industry_path: str | Path = "config/industry_chains.yaml",
        company_path: str | Path = "config/company_tags.yaml",
        relations_path: str | Path = "config/supply_chain_relations.yaml",
    ) -> None:
        self.industry_path = Path(industry_path)
        self.company_path = Path(company_path)
        self.relations_path = Path(relations_path)
        self._industry_data = load_yaml(self.industry_path, {"industries": {}})
        self._company_data = load_yaml(self.company_path, {"companies": {}})
        self._relation_data = load_yaml(self.relations_path, {"relations": []})

    @property
    def industries(self) -> Dict[str, Any]:
        return self._industry_data.get("industries", {})

    @property
    def companies(self) -> Dict[str, Any]:
        return self._company_data.get("companies", {})

    @property
    def relations(self) -> List[Dict[str, Any]]:
        return self._relation_data.get("relations", [])

    def get_company_profile(self, symbol: str) -> Dict[str, Any]:
        return self.companies.get(symbol, {})

    def find_chain(self, query: str) -> Dict[str, Any]:
        for key, chain in self.industries.items():
            aliases = chain.get("aliases", [])
            if query == key or query == chain.get("name") or query in aliases:
                return chain
        return {}

    def related_companies(self, chain_query: str) -> List[Dict[str, Any]]:
        chain = self.find_chain(chain_query)
        chain_name = chain.get("name", chain_query)
        rows = []
        for symbol, profile in self.companies.items():
            if profile.get("chain") == chain_name:
                rows.append({"symbol": symbol, **profile})
        return rows

    def match_company(self, symbol: str, concepts: List[str] | None = None, industry: str = "") -> Dict[str, Any]:
        profile = self.get_company_profile(symbol)
        if profile:
            return {"symbol": symbol, **profile}
        concept_set = set(concepts or [])
        for known_symbol, known in self.companies.items():
            if concept_set.intersection(set(known.get("concepts", []))):
                return {"symbol": known_symbol, **known, "matched_by": "concept"}
        for chain in self.industries.values():
            if industry and industry == chain.get("name"):
                return {"chain": chain["name"], "segment": "行业粗分类", "benefit_type": "受益类型未知", "confidence": 0.4}
        return {}
