from __future__ import annotations

from typing import Any, Dict, List

from stock_assistant.data_gateway import AStockDataGateway
from stock_assistant.knowledge.evidence_store import EvidenceStore
from stock_assistant.knowledge.extractor import KnowledgeExtractor


class KnowledgeEnricher:
    def __init__(
        self,
        store: EvidenceStore | None = None,
        extractor: KnowledgeExtractor | None = None,
        gateway: Any | None = None,
    ) -> None:
        self.store = store or EvidenceStore()
        self.extractor = extractor or KnowledgeExtractor()
        self.gateway = gateway or AStockDataGateway(use_live=False)

    def ingest_symbol(self, symbol: str, source: str = "news") -> Dict[str, int]:
        records = self._load_records(symbol, source)
        evidence_count = 0
        candidate_count = 0
        for record in records:
            evidence = self.store.add_evidence(record)
            evidence_count += 1
            for candidate in self.extractor.extract(evidence):
                candidate["evidence_id"] = evidence["id"]
                self.store.add_candidate(candidate)
                candidate_count += 1
        return {"evidence_count": evidence_count, "candidate_count": candidate_count}

    def _load_records(self, symbol: str, source: str) -> List[Dict[str, Any]]:
        if source == "news":
            rows = self.gateway.get_news(symbol)
            return [
                {
                    "symbol": row.get("symbol", symbol),
                    "source": row.get("source", "news"),
                    "title": row.get("title", ""),
                    "summary": row.get("summary", ""),
                    "text": row.get("raw_text", row.get("summary", "")),
                    "publish_time": row.get("publish_time", ""),
                    "evidence_type": "news",
                }
                for row in rows
            ]
        if source == "announcements":
            rows = self.gateway.get_announcements(symbol)
            return [
                {
                    "symbol": row.get("symbol", symbol),
                    "source": row.get("source", "announcement"),
                    "title": row.get("title", ""),
                    "summary": row.get("announcement_type", ""),
                    "text": row.get("raw_text", ""),
                    "publish_time": row.get("publish_time", ""),
                    "evidence_type": "announcement",
                }
                for row in rows
            ]
        if source == "research":
            rows = self.gateway.get_research_reports(symbol=symbol)
            return [
                {
                    "symbol": row.get("symbol", symbol),
                    "source": row.get("source", "research"),
                    "title": row.get("title", ""),
                    "summary": row.get("summary") or row.get("abstract", "") or row.get("orgSName", ""),
                    "text": row.get("text") or row.get("summary") or row.get("abstract", "") or row.get("title", ""),
                    "publish_time": row.get("publish_time") or row.get("publishDate", ""),
                    "evidence_type": "research",
                }
                for row in rows
            ]
        raise ValueError("source must be news, announcements or research")
