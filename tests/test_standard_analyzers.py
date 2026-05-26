import pandas as pd

from stock_assistant.analyzers.announcement import AnnouncementAnalyzer
from stock_assistant.analyzers.capital_flow import CapitalFlowAnalyzer
from stock_assistant.analyzers.fundamental import FundamentalAnalyzer
from stock_assistant.analyzers.valuation import ValuationAnalyzer


def test_fundamental_analyzer_scores_profitable_growth():
    analyzer = FundamentalAnalyzer()

    result = analyzer.analyze(
        {
            "revenue_yoy": 12.5,
            "net_profit_yoy": 18.0,
            "roe": 14.0,
            "debt_ratio": 38.0,
            "operating_cashflow": 100,
            "net_profit": 80,
        }
    )

    assert result["fundamental_score"] >= 70
    assert result["quality"] == "基本面偏强"
    assert "营收保持增长" in result["signals"]


def test_fundamental_analyzer_degrades_when_data_missing():
    result = FundamentalAnalyzer().analyze({})

    assert result["fundamental_score"] == 50
    assert result["confidence"] < 0.5
    assert result["warnings"]


def test_valuation_analyzer_scores_reasonable_pe_pb():
    result = ValuationAnalyzer().analyze({"pe_ttm": 18, "pb": 2.2, "market_cap": 1000000000})

    assert result["valuation_score"] >= 60
    assert result["valuation_level"] in {"合理", "合理偏低"}


def test_valuation_analyzer_degrades_when_missing():
    result = ValuationAnalyzer().analyze({"pe_ttm": None, "pb": None})

    assert result["valuation_score"] == 50
    assert result["confidence"] < 0.5


def test_capital_flow_analyzer_detects_positive_flow():
    flow = pd.DataFrame(
        [
            {"date": "2026-05-23", "main_net_inflow": -100},
            {"date": "2026-05-24", "main_net_inflow": 200},
            {"date": "2026-05-25", "main_net_inflow": 300},
        ]
    )

    result = CapitalFlowAnalyzer().analyze(flow)

    assert result["capital_flow_score"] > 60
    assert result["trend"] == "资金净流入"


def test_announcement_analyzer_flags_hard_block_events():
    anns = [{"title": "关于公司被立案调查的公告", "announcement_type": "风险提示"}]

    result = AnnouncementAnalyzer().analyze(anns)

    assert result["event_risk"] == "high"
    assert result["hard_blocks"]
    assert result["announcement_score"] < 40


def test_announcement_analyzer_deduplicates_and_ignores_old_warnings():
    anns = [
        {"title": "关于股东减持股份的公告", "publish_time": "2013-05-01"},
        {"title": "关于股东减持股份的公告", "publish_time": "2026-05-20"},
        {"title": "关于股东减持股份的公告", "publish_time": "2026-05-20"},
    ]

    result = AnnouncementAnalyzer().analyze(anns)

    assert result["event_risk"] == "medium"
    assert len(result["warnings"]) == 1
    assert result["filtered_count"] == 1
