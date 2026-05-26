from typer.testing import CliRunner

from stock_assistant.cli import app
from stock_assistant.knowledge.enrichment import KnowledgeEnricher
from stock_assistant.knowledge.evidence_store import EvidenceStore
from stock_assistant.knowledge.extractor import KnowledgeExtractor


def test_extractor_creates_candidate_relation_from_ai_compute_text():
    extractor = KnowledgeExtractor()

    candidates = extractor.extract(
        {
            "symbol": "603019",
            "title": "公司服务器订单受益于算力需求增长",
            "text": "公司数据中心和服务器业务受益于AI算力需求增长。",
            "source": "news",
        }
    )

    assert candidates
    assert candidates[0]["chain"] == "AI算力"
    assert candidates[0]["segment"] == "算力基础设施"
    assert candidates[0]["status"] == "observed"


def test_evidence_store_deduplicates_and_updates_candidate_status(tmp_path):
    store = EvidenceStore(root=tmp_path)
    evidence = {"symbol": "603019", "source": "news", "title": "算力新闻", "text": "服务器 数据中心 AI算力"}

    first = store.add_evidence(evidence)
    second = store.add_evidence(evidence)
    candidate = store.add_candidate({"symbol": "603019", "chain": "AI算力", "segment": "算力基础设施", "confidence": 0.62})
    store.update_candidate_status(candidate["id"], "verified")

    assert first["id"] == second["id"]
    assert len(store.list_evidence()) == 1
    assert store.list_candidates(status="verified")[0]["id"] == candidate["id"]


class FakeGateway:
    def get_news(self, symbol, days=7):
        return [{"symbol": symbol, "title": "服务器订单增长", "summary": "AI算力 数据中心 服务器"}]

    def get_announcements(self, symbol, days=30):
        return [{"symbol": symbol, "title": "暂无公告", "raw_text": ""}]

    def get_research_reports(self, symbol=None, industry=None):
        return [
            {
                "symbol": symbol,
                "title": "AI算力服务器行业深度",
                "summary": "数据中心 服务器 AI算力",
                "publish_time": "2026-05-20",
                "source": "eastmoney_report",
            }
        ]


def test_enricher_ingests_gateway_news_into_evidence_and_candidates(tmp_path):
    store = EvidenceStore(root=tmp_path)
    enricher = KnowledgeEnricher(store=store, gateway=FakeGateway())

    result = enricher.ingest_symbol("603019", source="news")

    assert result["evidence_count"] == 1
    assert result["candidate_count"] == 1
    assert store.list_candidates()[0]["chain"] == "AI算力"


def test_enricher_ingests_research_reports_into_evidence_and_candidates(tmp_path):
    store = EvidenceStore(root=tmp_path)
    enricher = KnowledgeEnricher(store=store, gateway=FakeGateway())

    result = enricher.ingest_symbol("603019", source="research")

    assert result["evidence_count"] == 1
    assert result["candidate_count"] == 1
    assert store.list_evidence()[0]["evidence_type"] == "research"


def test_cli_knowledge_candidates_outputs_pending_items(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_ASSISTANT_KNOWLEDGE_DIR", str(tmp_path))
    store = EvidenceStore(root=tmp_path)
    store.add_candidate({"symbol": "603019", "chain": "AI算力", "segment": "算力基础设施", "confidence": 0.62})
    runner = CliRunner()

    result = runner.invoke(app, ["knowledge", "candidates"])

    assert result.exit_code == 0
    assert "候选知识" in result.output
    assert "603019" in result.output
