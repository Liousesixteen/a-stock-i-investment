from typer.testing import CliRunner

from stock_assistant.cli import app
from stock_assistant.data_health import DataHealthChecker, FULL_CHECKS, QUICK_CHECKS
from stock_assistant.data_sources.catalog import endpoint_names


class MostlyHealthyProvider:
    def quote(self, symbol):
        return {"price": 10}

    def stock_basic(self, symbol):
        return {"name": "测试股份"}

    def daily_bars(self, symbol):
        class Bars:
            empty = False

            def __len__(self):
                return 3

        return Bars()

    def stock_news(self, symbol, page_size=20):
        return [{"title": "新闻"}]

    def announcements(self, symbol, page_size=30):
        return []


def test_data_health_checker_records_ok_and_empty_results():
    checker = DataHealthChecker(provider=MostlyHealthyProvider())

    result = checker.check("002415", checks=["quote", "daily_bars", "news", "announcements"])

    assert result["symbol"] == "002415"
    assert result["summary"]["ok"] == 3
    assert result["summary"]["empty"] == 1
    assert result["checks"]["quote"]["status"] == "ok"
    assert result["checks"]["announcements"]["status"] == "empty"


def test_data_health_markdown_contains_statuses():
    checker = DataHealthChecker(provider=MostlyHealthyProvider())
    result = checker.check("002415", checks=["quote", "announcements"])

    markdown = checker.to_markdown(result)

    assert "数据源健康检查" in markdown
    assert "quote" in markdown
    assert "announcements" in markdown
    assert "empty" in markdown


def test_cli_data_health_outputs_markdown(monkeypatch):
    class FakeChecker:
        def check(self, symbol, checks=None):
            return {"symbol": symbol, "summary": {"ok": 1, "empty": 0, "fail": 0}, "checks": {"quote": {"status": "ok", "latency_ms": 1, "sample_size": 1, "message": ""}}}

        def to_markdown(self, result):
            return "# 数据源健康检查\n\nquote ok"

    monkeypatch.setattr("stock_assistant.cli.build_data_health_checker", lambda provider: FakeChecker())
    runner = CliRunner()

    result = runner.invoke(app, ["data", "health", "002415"])

    assert result.exit_code == 0
    assert "quote ok" in result.output


def test_cli_data_health_uses_quick_profile_by_default(monkeypatch):
    captured = {}

    class FakeChecker:
        def check(self, symbol, checks=None):
            captured["checks"] = checks
            return {"symbol": symbol, "summary": {"ok": 1, "empty": 0, "fail": 0}, "checks": {"quote": {"status": "ok", "latency_ms": 1, "sample_size": 1, "message": ""}}}

        def to_markdown(self, result):
            return "# 数据源健康检查"

    monkeypatch.setattr("stock_assistant.cli.build_data_health_checker", lambda provider: FakeChecker())
    runner = CliRunner()

    result = runner.invoke(app, ["data", "health", "002415"])

    assert result.exit_code == 0
    assert captured["checks"] == QUICK_CHECKS


def test_cli_data_health_accepts_full_profile_and_explicit_checks(monkeypatch):
    captured = []

    class FakeChecker:
        def check(self, symbol, checks=None):
            captured.append(checks)
            return {"symbol": symbol, "summary": {"ok": 1, "empty": 0, "fail": 0}, "checks": {"quote": {"status": "ok", "latency_ms": 1, "sample_size": 1, "message": ""}}}

        def to_markdown(self, result):
            return "# 数据源健康检查"

    monkeypatch.setattr("stock_assistant.cli.build_data_health_checker", lambda provider: FakeChecker())
    runner = CliRunner()

    full = runner.invoke(app, ["data", "health", "002415", "--profile", "full"])
    explicit = runner.invoke(app, ["data", "health", "002415", "--checks", "stock_news, financial_statements"])

    assert full.exit_code == 0
    assert explicit.exit_code == 0
    assert captured[0] == FULL_CHECKS
    assert captured[1] == ["stock_news", "financial_statements"]


def test_cli_data_health_accepts_provider_option(monkeypatch):
    created = {}

    class FakeChecker:
        def __init__(self, provider=None):
            created["provider"] = provider.__class__.__name__

        def check(self, symbol, checks=None):
            return {"symbol": symbol, "summary": {"ok": 1, "empty": 0, "fail": 0}, "checks": {"daily_bars": {"status": "ok", "latency_ms": 1, "sample_size": 1, "message": ""}}}

        def to_markdown(self, result):
            return "# 数据源健康检查\n\ndaily_bars ok"

    monkeypatch.setattr("stock_assistant.cli.DataHealthChecker", FakeChecker, raising=False)
    runner = CliRunner()

    result = runner.invoke(app, ["data", "health", "002415", "--provider", "akshare"])

    assert result.exit_code == 0
    assert "AkShareAdapter" == created["provider"]


def test_data_health_can_check_full_catalog_with_router_style_provider():
    class RouterProvider:
        def fetch(self, endpoint, symbol):
            if endpoint == "realtime_quote":
                return {"status": "ok", "data": {"price": 10}, "message": ""}
            return {"status": "unsupported", "data": None, "message": "not implemented"}

    checker = DataHealthChecker(provider=RouterProvider())

    result = checker.check("002415", checks=endpoint_names()[:4])

    assert result["summary"]["ok"] == 1
    assert result["summary"]["unsupported"] == 3
    assert result["checks"]["realtime_quote"]["status"] == "ok"


def test_cli_data_report_outputs_health_and_cache_status(tmp_path, monkeypatch):
    class FakeChecker:
        def check(self, symbol, checks=None):
            return {
                "symbol": symbol,
                "summary": {"ok": 1, "empty": 0, "fail": 1, "unsupported": 0, "unavailable": 0},
                "checks": {
                    "daily_bars": {"status": "ok", "latency_ms": 1, "sample_size": 1, "message": ""},
                    "stock_news": {"status": "fail", "latency_ms": 2, "sample_size": 0, "message": "代理连接失败"},
                },
            }

    cache_file = tmp_path / "stock_news_002415.json"
    cache_file.write_text('{"generated_at":"2026-05-26T09:30:00","ttl_seconds":600,"source":"a-stock-data","data":[]}', encoding="utf-8")
    monkeypatch.setattr("stock_assistant.cli.build_data_health_checker", lambda provider: FakeChecker())
    monkeypatch.setattr("stock_assistant.cli.JsonCache", lambda: __import__("stock_assistant.cache", fromlist=["JsonCache"]).JsonCache(tmp_path), raising=False)
    runner = CliRunner()

    result = runner.invoke(app, ["data", "report", "002415"])

    assert result.exit_code == 0
    assert "数据源状态报告" in result.output
    assert "代理连接失败" in result.output
    assert "stock_news_002415" in result.output
