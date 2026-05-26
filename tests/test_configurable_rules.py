from pathlib import Path

from stock_assistant.config_loader import load_risk_rules
from stock_assistant.analyzers.announcement import AnnouncementAnalyzer
from stock_assistant.analyzers.fundamental import FundamentalAnalyzer
from stock_assistant.analyzers.valuation import ValuationAnalyzer


def test_load_risk_rules_merges_defaults(tmp_path):
    path = tmp_path / "risk_rules.yaml"
    path.write_text("fundamental_rules:\n  warn_if_roe_below: 9\n", encoding="utf-8")

    rules = load_risk_rules(path)

    assert rules["fundamental_rules"]["warn_if_roe_below"] == 9
    assert rules["fundamental_rules"]["warn_if_debt_ratio_above"] == 70
    assert "立案调查" in rules["announcement_rules"]["hard_block_events"]


def test_fundamental_analyzer_uses_configured_thresholds():
    analyzer = FundamentalAnalyzer({"warn_if_roe_below": 15, "strong_roe": 20})

    result = analyzer.analyze(
        {
            "revenue_yoy": 8,
            "net_profit_yoy": 8,
            "roe": 12,
            "debt_ratio": 40,
            "operating_cashflow": 100,
            "net_profit": 80,
        }
    )

    assert "ROE偏低" in result["warnings"]


def test_valuation_analyzer_uses_configured_pe_threshold():
    analyzer = ValuationAnalyzer({"reasonable_pe_max": 15, "high_pe": 20})

    result = analyzer.analyze({"pe_ttm": 18, "pb": 2.0})

    assert "PE偏高，需要业绩兑现" not in result["warnings"]
    assert "PE处于可接受区间" not in result["signals"]


def test_announcement_analyzer_uses_configured_keywords():
    analyzer = AnnouncementAnalyzer({"hard_block_events": ["重大合同终止"], "warn_events": ["减持"]})

    result = analyzer.analyze([{"title": "关于重大合同终止的公告"}])

    assert result["hard_blocks"]
    assert result["event_risk"] == "high"
