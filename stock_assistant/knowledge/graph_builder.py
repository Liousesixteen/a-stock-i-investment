from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

from stock_assistant.knowledge.knowledge_store import KnowledgeStore


@dataclass
class KnowledgeGraph:
    nodes: Set[str] = field(default_factory=set)
    edges: List[Dict[str, str]] = field(default_factory=list)

    def add_node(self, node: str) -> None:
        self.nodes.add(node)

    def add_edge(self, source: str, target: str, relation: str) -> None:
        self.add_node(source)
        self.add_node(target)
        self.edges.append({"source": source, "target": target, "relation": relation})

    def has_edge(self, source: str, target: str, relation: str) -> bool:
        return any(edge == {"source": source, "target": target, "relation": relation} for edge in self.edges)

    def neighbors(self, source: str, relation: str | None = None) -> List[str]:
        return [
            edge["target"]
            for edge in self.edges
            if edge["source"] == source and (relation is None or edge["relation"] == relation)
        ]


class KnowledgeGraphBuilder:
    def __init__(self, store: KnowledgeStore) -> None:
        self.store = store

    def build(self) -> KnowledgeGraph:
        graph = KnowledgeGraph()
        for symbol, profile in self.store.companies.items():
            company_node = f"Company:{symbol}"
            chain = profile.get("chain", "")
            segment = profile.get("segment", "")
            if chain:
                graph.add_edge(company_node, f"IndustryChain:{chain}", "BELONGS_TO")
            if chain and segment:
                graph.add_edge(company_node, f"Segment:{chain}:{segment}", "IN_SEGMENT")
            for product in profile.get("products", []):
                graph.add_edge(company_node, f"Product:{product}", "HAS_PRODUCT")
            for risk in profile.get("risks", []):
                graph.add_edge(company_node, f"Risk:{risk}", "HAS_RISK")
            for evidence in profile.get("evidence", []):
                graph.add_edge(company_node, f"Evidence:{evidence.get('source', 'local')}:{evidence.get('updated_at', '')}", "VERIFIED_BY")
        for relation in self.store.relations:
            source = f"Company:{relation.get('from')}" if str(relation.get("from", "")).isdigit() else str(relation.get("from"))
            target = f"IndustryChain:{relation.get('to')}"
            graph.add_edge(source, target, relation.get("relation", "RELATED_TO"))
        return graph
