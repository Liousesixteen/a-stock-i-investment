from typer.testing import CliRunner

from stock_assistant.analyzers.technical import TechnicalAnalyzer
from stock_assistant.cli import app
from stock_assistant.data_gateway import AStockDataGateway
from stock_assistant.workflows.stock_deep_dive import StockDeepDiveWorkflow


def test_technical_analyzer_returns_neutral_when_bars_missing():
    gateway = AStockDataGateway(use_live=False)
    analyzer = TechnicalAnalyzer()

    result = analyzer.analyze(gateway.get_daily_bars("000000"))

    assert result["technical_score"] == 50
    assert result["trend"] == "K线缺失"
    assert result["confidence"] < 0.5
    assert result["warnings"]


def test_quick_stock_report_contains_required_sections():
    workflow = StockDeepDiveWorkflow(gateway=AStockDataGateway(use_live=False))

    result = workflow.analyze("002415", mode="quick")
    report = result.markdown

    assert "核心结论" in report
    assert "大盘状态" in report
    assert "产业链定位" in report
    assert "技术状态" in report
    assert "风险等级" in report
    assert "仓位建议" in report
    assert "止损参考" in report
    assert "反向失效条件" in report


def test_standard_stock_report_includes_data_limitations():
    workflow = StockDeepDiveWorkflow(gateway=AStockDataGateway(use_live=False))

    result = workflow.analyze("002415", mode="standard")

    assert result.mode == "standard"
    assert "公告新闻与资金流" in result.markdown
    assert "数据限制" in result.markdown


def test_standard_workflow_includes_structured_standard_scores():
    workflow = StockDeepDiveWorkflow(gateway=AStockDataGateway(use_live=False))

    result = workflow.analyze("002415", mode="standard")

    assert "fundamental_analysis" in result.evidence
    assert "valuation_analysis" in result.evidence
    assert "announcement_analysis" in result.evidence
    assert "capital_flow_analysis" in result.evidence
    assert "基本面评分" in result.markdown
    assert "估值评分" in result.markdown
    assert "资金流评分" in result.markdown
    assert "公告风险" in result.markdown


def test_deep_workflow_includes_chain_comparison_and_scenarios():
    workflow = StockDeepDiveWorkflow(gateway=AStockDataGateway(use_live=False))

    result = workflow.analyze("603019", mode="deep")

    assert result.mode == "deep"
    assert "deep_analysis" in result.evidence
    assert result.evidence["deep_analysis"]["peer_companies"]
    assert "深度产业链比较" in result.markdown
    assert "同链公司横向比较" in result.markdown
    assert "风险情景" in result.markdown
    assert "寒武纪" in result.markdown


def test_cli_analyze_quick_outputs_markdown():
    runner = CliRunner()

    result = runner.invoke(app, ["analyze", "002415", "--mode", "quick"])

    assert result.exit_code == 0
    assert "个股快速分析" in result.output
    assert "不构成投资建议" in result.output


def test_cli_accepts_live_flag(monkeypatch):
    created = {}

    class FakeGateway:
        def __init__(self, use_live=False):
            created["use_live"] = use_live

    class FakeWorkflow:
        def __init__(self, gateway):
            self.gateway = gateway

        def analyze(self, symbol, mode):
            class Result:
                markdown = "# live ok"

            return Result()

    monkeypatch.setattr("stock_assistant.cli.AStockDataGateway", FakeGateway)
    monkeypatch.setattr("stock_assistant.cli.StockDeepDiveWorkflow", FakeWorkflow)
    runner = CliRunner()

    result = runner.invoke(app, ["analyze", "002415", "--mode", "quick", "--live"])

    assert result.exit_code == 0
    assert created["use_live"] is True
    assert "live ok" in result.output


def test_cli_cache_refresh_market_outputs_status():
    runner = CliRunner()

    result = runner.invoke(app, ["cache", "refresh-market"])

    assert result.exit_code == 0
    assert "market_context" in result.output


def test_cli_morning_accepts_live_flag():
    runner = CliRunner()

    result = runner.invoke(app, ["morning", "--live"])

    assert result.exit_code == 0
    assert "盘前简报" in result.output
    assert "今日纪律" in result.output


def test_cli_close_review_outputs_required_sections():
    runner = CliRunner()

    result = runner.invoke(app, ["close-review"])

    assert result.exit_code == 0
    assert "盘后复盘" in result.output
    assert "今日市场状态" in result.output
    assert "市场情绪与消息面" in result.output
    assert "明日计划" in result.output


def test_cli_sentiment_outputs_market_news_radar():
    runner = CliRunner()

    result = runner.invoke(app, ["sentiment"])

    assert result.exit_code == 0
    assert "A 股市场情绪与消息面雷达" in result.output
    assert "情绪评分" in result.output
    assert "最新消息雷达" in result.output
    assert "小道消息/传闻" in result.output


def test_close_review_uses_market_snapshot_when_available():
    class SnapshotGateway:
        def get_market_snapshot(self):
            return {
                "indices": [
                    {"name": "上证指数", "price": 4145.37, "pct_chg": -0.17, "amount": 1461685380000},
                    {"name": "创业板指", "price": 4043.07, "pct_chg": 0.54, "amount": 837209300000},
                ],
                "northbound": {"net_inflow": -4038000000, "status": "净流出"},
                "total_amount": 2298894680000,
                "summary": "指数分化",
                "scenarios": {
                    "base": "震荡分化",
                    "bull": "放量站上压力位",
                    "bear": "跌破支撑位",
                },
            }

        def get_sector_performance(self):
            import pandas as pd

            return pd.DataFrame(
                [
                    {"sector": "计算机设备", "pct_chg": 1.8, "amount": 1, "strength": "强于大盘"},
                    {"sector": "新能源", "pct_chg": -0.4, "amount": 1, "strength": "弱于大盘"},
                ]
            )

        def get_market_news(self):
            return [
                {"title": "稳增长政策继续发力", "summary": "政策利好 稳增长"},
                {"title": "外围市场波动加大", "summary": "外围利空"},
            ]

    from stock_assistant.workflows.morning_brief import MorningBriefWorkflow

    output = MorningBriefWorkflow(gateway=SnapshotGateway()).close_review()

    assert "上证指数：4145.37（-0.17%）" in output
    assert "北向资金：净流出" in output
    assert "情绪评分" in output
    assert "震荡分化" in output


def test_market_snapshot_uses_last_valid_northbound_values():
    import pandas as pd

    from stock_assistant.data_gateway import AStockDataGateway

    gateway = AStockDataGateway()
    northbound = {
        "data": pd.DataFrame(
            [
                {"time": "14:58", "hgt_yi": -10.52, "sgt_yi": -36.24},
                {"time": "14:59", "hgt_yi": -10.03, "sgt_yi": -36.00},
                {"time": "15:00", "hgt_yi": -9.28, "sgt_yi": None},
            ]
        )
    }

    result = gateway._standardize_northbound(northbound)

    assert round(result["net_inflow"] / 100000000, 2) == -45.28
    assert result["status"] == "净流出"
