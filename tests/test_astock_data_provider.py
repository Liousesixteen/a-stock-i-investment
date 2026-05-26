from stock_assistant.providers.astock_data import AStockDataLiveProvider


class FakeResponse:
    def __init__(self, payload, text=None):
        self.payload = payload
        self.text = text

    def json(self):
        return self.payload


def test_provider_parses_baidu_concept_blocks(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        return FakeResponse(
            {
                "ResultCode": "0",
                "Result": [
                    {"type": "概念板块", "list": [{"name": "AI算力", "increase": "1.2", "desc": "算力方向"}]},
                    {"type": "行业板块", "list": [{"name": "计算机设备", "increase": "0.5", "desc": ""}]},
                ],
            }
        )

    monkeypatch.setattr("stock_assistant.providers.astock_data.requests.get", fake_get)
    provider = AStockDataLiveProvider()

    blocks = provider.concept_blocks("002415")

    assert blocks["concept_tags"] == ["AI算力"]
    assert blocks["industry"][0]["name"] == "计算机设备"


def test_provider_parses_eastmoney_stock_news(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(
            {},
            text='jQuery_news({"result":{"cmsArticleWebOld":{"list":[{"title":"<em>公司</em>新闻","content":"<p>摘要</p>","date":"2026-05-25","mediaName":"东财","url":"https://example.com"}]}}})',
        )

    monkeypatch.setattr("stock_assistant.providers.astock_data.requests.get", fake_get)
    provider = AStockDataLiveProvider()

    news = provider.stock_news("002415")

    assert news[0]["title"] == "公司新闻"
    assert news[0]["summary"] == "摘要"
    assert news[0]["source"] == "东财"


def test_provider_parses_cninfo_announcements(monkeypatch):
    def fake_post(url, data=None, headers=None, timeout=None):
        return FakeResponse(
            {
                "announcements": [
                    {
                        "announcementTitle": "年度报告",
                        "announcementTypeName": "定期报告",
                        "announcementTime": 1779638400000,
                        "announcementId": "123",
                    }
                ]
            }
        )

    monkeypatch.setattr("stock_assistant.providers.astock_data.requests.post", fake_post)
    provider = AStockDataLiveProvider()

    anns = provider.announcements("002415")

    assert anns[0]["title"] == "年度报告"
    assert anns[0]["announcement_type"] == "定期报告"
    assert anns[0]["source"] == "cninfo"


def test_provider_builds_financial_snapshot_from_sina_report(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(
            {
                "result": {
                    "data": {
                        "lrb": [
                            {
                                "报告日": "2026-03-31",
                                "营业总收入": "1000000",
                                "营业总收入同比增长": "6.5",
                                "净利润": "120000",
                                "净利润同比增长": "8.2",
                                "基本每股收益": "0.25",
                            }
                        ]
                    }
                }
            }
        )

    monkeypatch.setattr("stock_assistant.providers.astock_data.requests.get", fake_get)
    provider = AStockDataLiveProvider()

    snapshot = provider.financial_snapshot("002415")

    assert snapshot["report_date"] == "2026-03-31"
    assert snapshot["revenue"] == 1000000
    assert snapshot["revenue_yoy"] == 6.5
    assert snapshot["net_profit"] == 120000


def test_provider_daily_bars_uses_tencent_when_baidu_empty(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(url)
        if "finance.pae.baidu.com" in url:
            return FakeResponse({"Result": {"newMarketData": {"keys": [], "marketData": ""}}})
        return FakeResponse(
            {
                "data": {
                    "sh603078": {
                        "qfqday": [
                            ["2026-05-25", "30.00", "32.00", "33.00", "29.50", "1000.000"],
                            ["2026-05-26", "32.00", "33.14", "34.43", "32.61", "2000.000"],
                        ]
                    }
                }
            }
        )

    monkeypatch.setattr("stock_assistant.providers.astock_data.requests.get", fake_get)
    provider = AStockDataLiveProvider()

    bars = provider.daily_bars("603078")

    assert bars.iloc[-1]["close"] == 33.14
    assert bars.iloc[-1]["volume"] == 200000
    assert bars.attrs["source"] == "a-stock-data:tencent-kline"
    assert len(calls) == 2
