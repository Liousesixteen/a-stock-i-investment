from stock_assistant.knowledge.graph_builder import KnowledgeGraphBuilder
from stock_assistant.knowledge.knowledge_store import KnowledgeStore
from stock_assistant.analyzers.industry_chain import IndustryChainAnalyzer


def test_knowledge_store_loads_company_chain_profile():
    store = KnowledgeStore()

    profile = store.get_company_profile("603019")

    assert profile["name"] == "中科曙光"
    assert profile["chain"] == "AI算力"
    assert profile["segment"] == "算力基础设施"
    assert profile["benefit_type"] == "直接受益"
    assert profile["confidence"] > 0.5


def test_knowledge_store_finds_chain_by_alias():
    store = KnowledgeStore()

    chain = store.find_chain("算力")

    assert chain["name"] == "AI算力"
    assert "midstream" in chain


def test_graph_builder_creates_company_chain_segment_edges():
    store = KnowledgeStore()
    graph = KnowledgeGraphBuilder(store).build()

    assert graph.has_edge("Company:603019", "IndustryChain:AI算力", "BELONGS_TO")
    assert graph.has_edge("Company:603019", "Segment:AI算力:算力基础设施", "IN_SEGMENT")
    assert graph.neighbors("Company:603019", relation="HAS_RISK")


def test_knowledge_store_returns_related_companies_for_chain():
    store = KnowledgeStore()

    companies = store.related_companies("AI算力")

    assert any(company["symbol"] == "603019" for company in companies)


def test_industry_chain_analyzer_uses_knowledge_store_profile():
    analyzer = IndustryChainAnalyzer(store=KnowledgeStore())

    result = analyzer.analyze_company_position({"symbol": "603019", "industry": "计算机设备", "concepts": []})

    assert result["chain"] == "AI算力"
    assert result["segment"] == "算力基础设施"
    assert result["benefit_type"] == "直接受益"
    assert result["confidence"] >= 0.7
