import pandas as pd

from stock_assistant.data_gateway import AStockDataGateway, MissingData


def test_normalize_symbol_accepts_common_a_share_formats():
    gateway = AStockDataGateway(use_live=False)

    assert gateway.normalize_symbol("SZ002415") == "002415"
    assert gateway.normalize_symbol("002415.SZ") == "002415"
    assert gateway.normalize_symbol(" sh600519 ") == "600519"


def test_gateway_returns_missing_quote_when_provider_missing():
    gateway = AStockDataGateway(use_live=False)

    quote = gateway.get_realtime_quote("002415")

    assert quote["symbol"] == "002415"
    assert quote["name"]
    assert quote["price"] is None
    assert "realtime_quote" in {item["field"] for item in quote["missing_data"]}


def test_gateway_marks_missing_daily_bars_without_crashing():
    gateway = AStockDataGateway(use_live=False)

    bars = gateway.get_daily_bars("000000")

    assert isinstance(bars, pd.DataFrame)
    assert list(bars.columns) == [
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "turnover_rate",
        "pct_chg",
    ]
    assert bars.empty


def test_missing_data_payload_is_serializable():
    missing = MissingData(field="daily_bars", reason="K线缺失")

    assert missing.to_dict() == {"field": "daily_bars", "reason": "K线缺失"}
