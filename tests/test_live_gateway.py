import pandas as pd

from stock_assistant.cache import JsonCache
from stock_assistant.data_gateway import AStockDataGateway


class FakeLiveProvider:
    def quote(self, symbol):
        return {
            "symbol": symbol,
            "name": "真实样例",
            "price": 12.34,
            "pct_chg": 2.5,
            "open": 12.0,
            "high": 12.5,
            "low": 11.9,
            "pre_close": 12.04,
            "volume": 100,
            "amount": 1234,
            "turnover_rate": 1.2,
            "pe_ttm": 18.5,
            "pb": 2.1,
            "market_cap": 1000000000,
            "float_market_cap": 800000000,
            "limit_up": 13.24,
            "limit_down": 10.84,
            "missing_data": [],
        }

    def daily_bars(self, symbol):
        return pd.DataFrame(
            [
                {
                    "date": "2026-05-25",
                    "open": 12,
                    "high": 13,
                    "low": 11,
                    "close": 12.34,
                    "volume": 100,
                    "amount": 1234,
                    "turnover_rate": 1.2,
                    "pct_chg": 2.5,
                }
            ]
        )

    def stock_basic(self, symbol):
        return {
            "symbol": symbol,
            "name": "真实样例",
            "industry": "计算机设备",
            "concepts": [],
            "market": "深市",
            "missing_data": [],
        }


class BrokenLiveProvider:
    def quote(self, symbol):
        raise RuntimeError("network down")

    def daily_bars(self, symbol):
        raise RuntimeError("network down")

    def financial_snapshot(self, symbol):
        raise RuntimeError("financial down")

    def announcements(self, symbol, page_size=30):
        return []

    def stock_news(self, symbol, page_size=20):
        raise RuntimeError("news down")

    def capital_flow(self, symbol):
        raise RuntimeError("flow down")


class FakeFallbackAdapter:
    def fetch(self, endpoint, symbol):
        if endpoint == "daily_bars":
            return {
                "status": "ok",
                "data": pd.DataFrame(
                    [
                        {
                            "date": "2026-05-25",
                            "open": 20,
                            "high": 21,
                            "low": 19,
                            "close": 20.5,
                            "volume": 1000,
                            "amount": 20000,
                            "turnover_rate": 1.1,
                            "pct_chg": 2.0,
                        }
                    ]
                ),
                "message": "",
            }
        if endpoint == "stock_news":
            return {"status": "ok", "data": pd.DataFrame([{"新闻标题": "fallback news", "新闻内容": "fallback summary"}]), "message": ""}
        if endpoint == "financial_statements":
            return {"status": "ok", "data": pd.DataFrame([{"日期": "2026-03-31", "净利润": 123}]), "message": ""}
        return {"status": "unsupported", "data": None, "message": "unsupported"}


class PolicyFallbackAdapter:
    def __init__(self):
        self.calls = []

    def fetch(self, endpoint, symbol):
        self.calls.append(endpoint)
        if endpoint == "daily_bars":
            return {
                "provider": "akshare",
                "status": "ok",
                "data": pd.DataFrame(
                    [
                        {
                            "date": "2026-05-26",
                            "open": 30,
                            "high": 31,
                            "low": 29,
                            "close": 30.5,
                            "volume": 1000,
                            "amount": 30000,
                            "turnover_rate": 1.1,
                            "pct_chg": 1.0,
                        }
                    ]
                ),
                "message": "",
            }
        if endpoint == "sector_performance":
            return {"provider": "akshare", "status": "ok", "data": pd.DataFrame([{"sector": "计算机设备", "pct_chg": 1.2}]), "message": ""}
        if endpoint == "capital_flow_120d":
            return {"provider": "akshare", "status": "ok", "data": pd.DataFrame([{"main_net_inflow": 123}]), "message": ""}
        if endpoint == "announcements":
            return {"provider": "akshare", "status": "ok", "data": pd.DataFrame([{"公告标题": "fallback announcement"}]), "message": ""}
        return {"provider": "akshare", "status": "unsupported", "data": None, "message": "unsupported"}


def test_gateway_uses_live_provider_when_enabled(tmp_path):
    gateway = AStockDataGateway(cache=JsonCache(tmp_path), use_live=True, live_provider=FakeLiveProvider())

    quote = gateway.get_realtime_quote("002415")
    bars = gateway.get_daily_bars("002415")

    assert quote["name"] == "真实样例"
    assert quote["price"] == 12.34
    assert bars.iloc[-1]["close"] == 12.34


def test_gateway_falls_back_when_live_provider_fails(tmp_path):
    gateway = AStockDataGateway(cache=JsonCache(tmp_path), use_live=True, live_provider=BrokenLiveProvider())

    quote = gateway.get_realtime_quote("002415")
    bars = gateway.get_daily_bars("002415")

    assert quote["name"] == "海康威视"
    assert quote["price"] > 0
    assert "live_quote" in {item["field"] for item in quote["missing_data"]}
    assert not bars.empty


def test_gateway_marks_standard_live_fallbacks(tmp_path):
    gateway = AStockDataGateway(cache=JsonCache(tmp_path), use_live=True, live_provider=BrokenLiveProvider(), fallback_adapters=[])

    financial = gateway.get_financial_snapshot("002415")
    announcements = gateway.get_announcements("002415")
    news = gateway.get_news("002415")
    flow = gateway.get_capital_flow("002415")

    assert "live_financial_snapshot" in {item["field"] for item in financial["missing_data"]}
    assert "live_announcements" in {item["field"] for item in announcements[0]["missing_data"]}
    assert "live_news" in {item["field"] for item in news[0]["missing_data"]}
    assert "live_capital_flow" in set(flow.attrs["missing_data_fields"])


def test_gateway_merges_local_concepts_when_live_basic_lacks_them(tmp_path):
    gateway = AStockDataGateway(cache=JsonCache(tmp_path), use_live=True, live_provider=FakeLiveProvider())

    basic = gateway.get_stock_basic("002415")

    assert "人工智能" in basic["concepts"]
    assert "local_concepts" in {item["field"] for item in basic["missing_data"]}


def test_gateway_merges_local_industry_when_live_basic_lacks_it(tmp_path):
    class NoIndustryProvider(FakeLiveProvider):
        def stock_basic(self, symbol):
            payload = super().stock_basic(symbol)
            payload["industry"] = "未知行业"
            return payload

    gateway = AStockDataGateway(cache=JsonCache(tmp_path), use_live=True, live_provider=NoIndustryProvider())

    basic = gateway.get_stock_basic("002415")

    assert basic["industry"] == "计算机设备"
    assert "local_industry" in {item["field"] for item in basic["missing_data"]}


def test_gateway_uses_fallback_adapter_for_daily_bars_news_and_financials(tmp_path):
    gateway = AStockDataGateway(cache=JsonCache(tmp_path), use_live=True, live_provider=BrokenLiveProvider(), fallback_adapters=[FakeFallbackAdapter()])

    bars = gateway.get_daily_bars("002415")
    news = gateway.get_news("002415")
    statements = gateway.get_financial_statements("002415")

    assert bars.iloc[-1]["close"] == 20.5
    assert news[0]["title"] == "fallback news"
    assert statements["fallback_provider"] == "FakeFallbackAdapter"


def test_gateway_marks_fresh_fallback_source_on_daily_bars(tmp_path):
    adapter = PolicyFallbackAdapter()
    gateway = AStockDataGateway(cache=JsonCache(tmp_path), use_live=True, live_provider=BrokenLiveProvider(), fallback_adapters=[adapter])

    bars = gateway.get_daily_bars("002415")

    assert bars.iloc[-1]["close"] == 30.5
    assert bars.attrs["source"] == "akshare"
    assert bars.attrs["is_fallback"] is True
    assert "daily_bars" in adapter.calls


def test_gateway_uses_policy_fallback_for_sector_and_capital_flow(tmp_path):
    adapter = PolicyFallbackAdapter()
    gateway = AStockDataGateway(cache=JsonCache(tmp_path), use_live=True, live_provider=BrokenLiveProvider(), fallback_adapters=[adapter])

    sectors = gateway.get_sector_performance()
    flow = gateway.get_capital_flow("002415")

    assert sectors.iloc[0]["sector"] == "计算机设备"
    assert sectors.attrs["source"] == "akshare"
    assert flow.iloc[0]["main_net_inflow"] == 123
    assert flow.attrs["source"] == "akshare"


def test_gateway_standardizes_announcement_fallback(tmp_path):
    adapter = PolicyFallbackAdapter()
    gateway = AStockDataGateway(cache=JsonCache(tmp_path), use_live=True, live_provider=BrokenLiveProvider(), fallback_adapters=[adapter])

    announcements = gateway.get_announcements("002415")

    assert announcements[0]["title"] == "fallback announcement"
    assert announcements[0]["source"] == "akshare"
    assert announcements[0]["is_fallback"] is True


def test_gateway_reuses_fresh_sector_cache(tmp_path):
    class CountingProvider(FakeLiveProvider):
        def __init__(self):
            self.calls = 0

        def sector_performance(self):
            self.calls += 1
            return pd.DataFrame([{"sector": "计算机设备", "pct_chg": 1.8, "amount": 1, "strength": "强于大盘"}])

    provider = CountingProvider()
    gateway = AStockDataGateway(cache=JsonCache(tmp_path), use_live=True, live_provider=provider, fallback_adapters=[])

    first = gateway.get_sector_performance()
    second = gateway.get_sector_performance()

    assert provider.calls == 1
    assert first.iloc[0]["sector"] == "计算机设备"
    assert second.attrs["source"] == "a-stock-data"
    assert second.attrs["is_cached"] is True


def test_gateway_reuses_fresh_news_and_announcement_cache(tmp_path):
    class CountingProvider(FakeLiveProvider):
        def __init__(self):
            self.news_calls = 0
            self.announcement_calls = 0

        def stock_news(self, symbol, page_size=20):
            self.news_calls += 1
            return [{"symbol": symbol, "title": "fresh news", "source": "a-stock-data"}]

        def announcements(self, symbol, page_size=30):
            self.announcement_calls += 1
            return [{"symbol": symbol, "title": "fresh announcement", "announcement_type": "普通公告"}]

    provider = CountingProvider()
    gateway = AStockDataGateway(cache=JsonCache(tmp_path), use_live=True, live_provider=provider, fallback_adapters=[])

    assert gateway.get_news("002415")[0]["title"] == "fresh news"
    assert gateway.get_news("002415")[0]["is_cached"] is True
    assert gateway.get_announcements("002415")[0]["title"] == "fresh announcement"
    assert gateway.get_announcements("002415")[0]["is_cached"] is True
    assert provider.news_calls == 1
    assert provider.announcement_calls == 1
