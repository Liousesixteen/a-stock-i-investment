import types

import pandas as pd

from stock_assistant.data_sources.adapters import AkShareAdapter, AStockDataAdapter
from stock_assistant.data_sources.catalog import ENDPOINTS, endpoint_names


class FakeAStockProvider:
    def __getattr__(self, name):
        def fake_method(*args, **kwargs):
            return [{"method": name}]

        return fake_method

    def quote(self, symbol):
        return {"symbol": symbol, "price": 10}

    def daily_bars(self, symbol):
        return pd.DataFrame([{"close": 10}])

    def stock_news(self, symbol, page_size=20):
        return [{"title": "news"}]


def test_catalog_covers_astock_data_endpoint_surface():
    names = endpoint_names()

    assert len(ENDPOINTS) >= 28
    assert "realtime_quote" in names
    assert "daily_bars" in names
    assert "research_reports" in names
    assert "dragon_tiger" in names
    assert "financial_statements" in names
    assert "announcements" in names


def test_astock_adapter_fetches_implemented_endpoint_and_marks_unknown_one():
    adapter = AStockDataAdapter(provider=FakeAStockProvider())

    quote = adapter.fetch("realtime_quote", "002415")
    reports = adapter.fetch("research_reports", "002415")
    missing = adapter.fetch("not_a_real_endpoint", "002415")

    assert quote["status"] == "ok"
    assert quote["data"]["price"] == 10
    assert reports["status"] == "ok"
    assert missing["status"] == "unsupported"
    assert "not_a_real_endpoint" in missing["message"]


def test_astock_adapter_maps_every_catalog_endpoint():
    adapter = AStockDataAdapter(provider=FakeAStockProvider())

    results = [adapter.fetch(endpoint, "002415") for endpoint in endpoint_names()]

    assert all(result["status"] != "unsupported" for result in results)


def test_akshare_adapter_is_optional_when_package_missing(monkeypatch):
    def fake_import(name):
        raise ImportError("not installed")

    monkeypatch.setattr("stock_assistant.data_sources.adapters.importlib.import_module", fake_import)
    adapter = AkShareAdapter()

    result = adapter.fetch("daily_bars", "002415")

    assert result["status"] == "unavailable"
    assert "akshare" in result["message"]


def test_akshare_adapter_can_fetch_daily_bars_with_fake_module(monkeypatch):
    fake_akshare = types.SimpleNamespace(
        stock_zh_a_hist=lambda symbol, period, adjust: pd.DataFrame(
            [{"日期": "2026-05-25", "开盘": 1, "最高": 2, "最低": 1, "收盘": 2, "成交量": 100, "成交额": 200, "换手率": 1.2, "涨跌幅": 3.4}]
        )
    )

    monkeypatch.setattr("stock_assistant.data_sources.adapters.importlib.import_module", lambda name: fake_akshare)
    adapter = AkShareAdapter()

    result = adapter.fetch("daily_bars", "002415")

    assert result["status"] == "ok"
    assert result["data"].iloc[0]["close"] == 2


def test_akshare_adapter_supports_market_and_signal_endpoints(monkeypatch):
    calls = []

    def record(name, payload):
        calls.append(name)
        return pd.DataFrame([payload])

    fake_akshare = types.SimpleNamespace(
        stock_zh_a_spot_em=lambda: pd.DataFrame([{"代码": "002415", "最新价": 10.5}, {"代码": "000001", "最新价": 9.9}]),
        stock_bid_ask_em=lambda symbol: record("bid_ask", {"symbol": symbol}),
        stock_board_industry_name_em=lambda: record("industry", {"板块": "计算机设备"}),
        stock_board_concept_name_em=lambda: record("concept", {"板块": "人工智能"}),
        stock_hsgt_hist_em=lambda symbol: record("northbound", {"name": symbol}),
        stock_individual_fund_flow=lambda stock, market: record("fund_flow", {"stock": stock, "market": market}),
        stock_market_fund_flow=lambda: record("market_flow", {"净流入": 1}),
        stock_lhb_stock_detail_em=lambda symbol, date, flag: record("lhb_stock", {"symbol": symbol, "flag": flag}),
        stock_lhb_detail_em=lambda start_date, end_date: record("lhb_market", {"start": start_date, "end": end_date}),
        stock_restricted_release_detail_em=lambda start_date, end_date: record("lockup", {"start": start_date, "end": end_date}),
    )

    monkeypatch.setattr("stock_assistant.data_sources.adapters.importlib.import_module", lambda name: fake_akshare)
    adapter = AkShareAdapter()

    assert adapter.fetch("realtime_quote", "002415")["data"].iloc[0]["最新价"] == 10.5
    assert adapter.fetch("order_book", "002415")["status"] == "ok"
    assert adapter.fetch("sector_performance", "002415")["status"] == "ok"
    assert adapter.fetch("concept_blocks", "002415")["status"] == "ok"
    assert adapter.fetch("northbound_flow", "002415")["status"] == "ok"
    assert adapter.fetch("capital_flow_120d", "002415")["data"].iloc[0]["market"] == "sz"
    assert adapter.fetch("capital_flow_minute", "002415")["status"] == "ok"
    assert adapter.fetch("dragon_tiger", "002415", date="20260525")["status"] == "ok"
    assert adapter.fetch("market_dragon_tiger", "002415", start_date="20260501", end_date="20260525")["status"] == "ok"
    assert adapter.fetch("lockup_calendar", "002415", start_date="20260501", end_date="20260601")["status"] == "ok"
    assert {"bid_ask", "industry", "concept", "northbound", "fund_flow", "market_flow", "lhb_stock", "lhb_market", "lockup"}.issubset(set(calls))


def test_akshare_adapter_supports_capital_structure_endpoints(monkeypatch):
    fake_akshare = types.SimpleNamespace(
        stock_margin_detail_sse=lambda date: pd.DataFrame([{"市场": "沪市", "日期": date}]),
        stock_margin_detail_szse=lambda date: pd.DataFrame([{"市场": "深市", "日期": date}]),
        stock_fund_flow_big_deal=lambda: pd.DataFrame([{"名称": "海康威视"}]),
        stock_shareholder_change_ths=lambda symbol: pd.DataFrame([{"代码": symbol, "股东户数": 1000}]),
        stock_dividend_cninfo=lambda symbol: pd.DataFrame([{"代码": symbol, "分红": 1.0}]),
        stock_individual_notice_report=lambda security, symbol, begin_date, end_date: pd.DataFrame([{"代码": security, "公告类型": symbol}]),
    )

    monkeypatch.setattr("stock_assistant.data_sources.adapters.importlib.import_module", lambda name: fake_akshare)
    adapter = AkShareAdapter()

    margin = adapter.fetch("margin_trading", "002415", date="20260525")

    assert margin["status"] == "ok"
    assert sorted(margin["data"].keys()) == ["sse", "szse"]
    assert adapter.fetch("block_trades", "002415")["status"] == "ok"
    assert adapter.fetch("shareholder_count", "002415")["data"].iloc[0]["股东户数"] == 1000
    assert adapter.fetch("dividend_history", "002415")["status"] == "ok"
    assert adapter.fetch("announcements", "002415", notice_type="业绩")["data"].iloc[0]["公告类型"] == "业绩"
