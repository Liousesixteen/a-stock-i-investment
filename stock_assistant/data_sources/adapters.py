from __future__ import annotations

import importlib
from datetime import date, timedelta
from typing import Any, Callable, Dict

import pandas as pd

from stock_assistant.data_gateway import DAILY_COLUMNS
from stock_assistant.providers.astock_data import AStockDataLiveProvider


class AStockDataAdapter:
    def __init__(self, provider: Any | None = None) -> None:
        self.provider = provider or AStockDataLiveProvider()

    def fetch(self, endpoint: str, symbol: str = "002415", **kwargs: Any) -> Dict[str, Any]:
        call_map: Dict[str, Callable[[], Any]] = {
            "realtime_quote": lambda: self.provider.quote(symbol),
            "daily_bars": lambda: self.provider.daily_bars(symbol),
            "index_bars": lambda: self.provider.index_bars(kwargs.get("index_symbol", "000001"), **{k: v for k, v in kwargs.items() if k != "index_symbol"}),
            "tick_trades": lambda: self.provider.tick_trades(symbol, **kwargs),
            "order_book": lambda: self.provider.order_book(symbol),
            "baidu_kline": lambda: self.provider.baidu_kline(symbol),
            "research_reports": lambda: self.provider.research_reports(symbol, **kwargs),
            "research_pdf": lambda: self.provider.research_pdf(symbol, **kwargs),
            "consensus_eps": lambda: self.provider.consensus_eps(symbol),
            "iwencai_report_search": lambda: self.provider.iwencai_report_search(kwargs.get("query", symbol), **{k: v for k, v in kwargs.items() if k != "query"}),
            "hot_stocks": lambda: self.provider.hot_stocks(**kwargs),
            "northbound_flow": lambda: self.provider.northbound_flow(),
            "stock_basic": lambda: self.provider.stock_basic(symbol),
            "concept_blocks": lambda: self.provider.concept_blocks(symbol),
            "capital_flow_minute": lambda: self.provider.capital_flow_minute(symbol),
            "dragon_tiger": lambda: self.provider.dragon_tiger(symbol, **kwargs),
            "market_dragon_tiger": lambda: self.provider.market_dragon_tiger(**kwargs),
            "lockup_calendar": lambda: self.provider.lockup_calendar(symbol, **kwargs),
            "sector_performance": lambda: self.provider.sector_performance(),
            "margin_trading": lambda: self.provider.margin_trading(symbol, **kwargs),
            "block_trades": lambda: self.provider.block_trades(symbol, **kwargs),
            "shareholder_count": lambda: self.provider.shareholder_count(symbol, **kwargs),
            "dividend_history": lambda: self.provider.dividend_history(symbol, **kwargs),
            "capital_flow_120d": lambda: self.provider.capital_flow(symbol),
            "stock_news": lambda: self.provider.stock_news(symbol),
            "cls_news": lambda: self.provider.cls_news(**kwargs),
            "global_news": lambda: self.provider.global_news(**kwargs),
            "announcements": lambda: self.provider.announcements(symbol),
            "f10_profile": lambda: self.provider.f10_profile(symbol, **kwargs),
            "f10_announcements": lambda: self.provider.f10_announcements(symbol),
            "financial_snapshot": lambda: self.provider.financial_snapshot(symbol),
            "financial_statements": lambda: {
                "income_statement": self.provider.financial_report(symbol, "lrb"),
                "balance_sheet": self.provider.financial_report(symbol, "fzb"),
                "cash_flow": self.provider.financial_report(symbol, "llb"),
            },
        }
        if endpoint not in call_map:
            return {"provider": "a-stock-data", "endpoint": endpoint, "status": "unsupported", "data": None, "message": f"{endpoint} not implemented yet"}
        try:
            data = call_map[endpoint]()
            return {"provider": "a-stock-data", "endpoint": endpoint, "status": "ok", "data": data, "message": ""}
        except Exception as exc:
            return {"provider": "a-stock-data", "endpoint": endpoint, "status": "fail", "data": None, "message": str(exc)}


class AkShareAdapter:
    def __init__(self) -> None:
        self._akshare = None
        self._import_error = None

    @property
    def akshare(self) -> Any | None:
        if self._akshare is None and self._import_error is None:
            try:
                self._akshare = importlib.import_module("akshare")
            except ImportError as exc:
                self._import_error = exc
        return self._akshare

    def fetch(self, endpoint: str, symbol: str = "002415", **kwargs: Any) -> Dict[str, Any]:
        ak = self.akshare
        if ak is None:
            return {"provider": "akshare", "endpoint": endpoint, "status": "unavailable", "data": None, "message": "akshare not installed"}
        call_map: Dict[str, Callable[[], Any]] = {
            "realtime_quote": lambda: self._realtime_quote(symbol),
            "daily_bars": lambda: self._daily_bars(symbol),
            "index_bars": lambda: self._index_bars(symbol, **kwargs),
            "order_book": lambda: self._order_book(symbol),
            "sector_performance": lambda: self._sector_performance(),
            "concept_blocks": lambda: self._concept_blocks(),
            "northbound_flow": lambda: self._northbound_flow(),
            "capital_flow_120d": lambda: self._capital_flow_120d(symbol),
            "capital_flow_minute": lambda: self._market_fund_flow(),
            "dragon_tiger": lambda: self._dragon_tiger(symbol, **kwargs),
            "market_dragon_tiger": lambda: self._market_dragon_tiger(**kwargs),
            "lockup_calendar": lambda: self._lockup_calendar(**kwargs),
            "margin_trading": lambda: self._margin_trading(**kwargs),
            "block_trades": lambda: self._block_trades(),
            "shareholder_count": lambda: self._shareholder_count(symbol),
            "dividend_history": lambda: self._dividend_history(symbol),
            "financial_statements": lambda: self._financial_indicators(symbol),
            "stock_news": lambda: self._stock_news(symbol),
            "announcements": lambda: self._announcements(symbol, **kwargs),
        }
        if endpoint not in call_map:
            return {"provider": "akshare", "endpoint": endpoint, "status": "unsupported", "data": None, "message": f"{endpoint} not supported by AkShare adapter"}
        try:
            data = call_map[endpoint]()
            return {"provider": "akshare", "endpoint": endpoint, "status": "ok", "data": data, "message": ""}
        except Exception as exc:
            return {"provider": "akshare", "endpoint": endpoint, "status": "fail", "data": None, "message": str(exc)}

    def _daily_bars(self, symbol: str) -> pd.DataFrame:
        raw = self.akshare.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
        rename = {"日期": "date", "开盘": "open", "最高": "high", "最低": "low", "收盘": "close", "成交量": "volume", "成交额": "amount", "换手率": "turnover_rate", "涨跌幅": "pct_chg"}
        df = raw.rename(columns=rename)
        for column in DAILY_COLUMNS:
            if column not in df:
                df[column] = 0
        return df[DAILY_COLUMNS]

    def _financial_indicators(self, symbol: str) -> Any:
        if hasattr(self.akshare, "stock_financial_analysis_indicator"):
            return self.akshare.stock_financial_analysis_indicator(symbol=symbol)
        raise RuntimeError("akshare stock_financial_analysis_indicator unavailable")

    def _stock_news(self, symbol: str) -> Any:
        if hasattr(self.akshare, "stock_news_em"):
            return self.akshare.stock_news_em(symbol=symbol)
        raise RuntimeError("akshare stock_news_em unavailable")

    def _realtime_quote(self, symbol: str) -> Any:
        self._require("stock_zh_a_spot_em")
        raw = self.akshare.stock_zh_a_spot_em()
        if not hasattr(raw, "loc") or "代码" not in raw:
            return raw
        return raw.loc[raw["代码"].astype(str) == symbol]

    def _index_bars(self, symbol: str, **kwargs: Any) -> Any:
        self._require("stock_zh_index_hist_csindex")
        start_date = kwargs.get("start_date") or self._date_str(days_ago=365)
        end_date = kwargs.get("end_date") or self._date_str()
        return self.akshare.stock_zh_index_hist_csindex(symbol=symbol, start_date=start_date, end_date=end_date)

    def _order_book(self, symbol: str) -> Any:
        self._require("stock_bid_ask_em")
        return self.akshare.stock_bid_ask_em(symbol=symbol)

    def _sector_performance(self) -> Any:
        self._require("stock_board_industry_name_em")
        return self.akshare.stock_board_industry_name_em()

    def _concept_blocks(self) -> Any:
        self._require("stock_board_concept_name_em")
        return self.akshare.stock_board_concept_name_em()

    def _northbound_flow(self) -> Any:
        if hasattr(self.akshare, "stock_hsgt_hist_em"):
            return self.akshare.stock_hsgt_hist_em(symbol="北向资金")
        if hasattr(self.akshare, "stock_hsgt_fund_flow_summary_em"):
            return self.akshare.stock_hsgt_fund_flow_summary_em()
        raise RuntimeError("akshare northbound flow endpoint unavailable")

    def _capital_flow_120d(self, symbol: str) -> Any:
        self._require("stock_individual_fund_flow")
        return self.akshare.stock_individual_fund_flow(stock=symbol, market=self._market(symbol))

    def _market_fund_flow(self) -> Any:
        self._require("stock_market_fund_flow")
        return self.akshare.stock_market_fund_flow()

    def _dragon_tiger(self, symbol: str, **kwargs: Any) -> Any:
        self._require("stock_lhb_stock_detail_em")
        trade_date = kwargs.get("date") or self._date_str()
        return self.akshare.stock_lhb_stock_detail_em(symbol=symbol, date=trade_date, flag=kwargs.get("flag", "买入"))

    def _market_dragon_tiger(self, **kwargs: Any) -> Any:
        self._require("stock_lhb_detail_em")
        start_date = kwargs.get("start_date") or self._date_str(days_ago=30)
        end_date = kwargs.get("end_date") or self._date_str()
        return self.akshare.stock_lhb_detail_em(start_date=start_date, end_date=end_date)

    def _lockup_calendar(self, **kwargs: Any) -> Any:
        self._require("stock_restricted_release_detail_em")
        start_date = kwargs.get("start_date") or self._date_str(days_ago=30)
        end_date = kwargs.get("end_date") or self._date_str(days_ago=-180)
        return self.akshare.stock_restricted_release_detail_em(start_date=start_date, end_date=end_date)

    def _margin_trading(self, **kwargs: Any) -> Dict[str, Any]:
        trade_date = kwargs.get("date") or self._date_str(days_ago=1)
        data: Dict[str, Any] = {}
        if hasattr(self.akshare, "stock_margin_detail_sse"):
            data["sse"] = self.akshare.stock_margin_detail_sse(date=trade_date)
        if hasattr(self.akshare, "stock_margin_detail_szse"):
            data["szse"] = self.akshare.stock_margin_detail_szse(date=trade_date)
        if not data:
            raise RuntimeError("akshare margin trading endpoint unavailable")
        return data

    def _block_trades(self) -> Any:
        self._require("stock_fund_flow_big_deal")
        return self.akshare.stock_fund_flow_big_deal()

    def _shareholder_count(self, symbol: str) -> Any:
        self._require("stock_shareholder_change_ths")
        return self.akshare.stock_shareholder_change_ths(symbol=symbol)

    def _dividend_history(self, symbol: str) -> Any:
        if hasattr(self.akshare, "stock_dividend_cninfo"):
            return self.akshare.stock_dividend_cninfo(symbol=symbol)
        self._require("stock_history_dividend")
        raw = self.akshare.stock_history_dividend()
        if hasattr(raw, "loc") and "代码" in raw:
            return raw.loc[raw["代码"].astype(str) == symbol]
        return raw

    def _announcements(self, symbol: str, **kwargs: Any) -> Any:
        if hasattr(self.akshare, "stock_individual_notice_report"):
            return self.akshare.stock_individual_notice_report(
                security=symbol,
                symbol=kwargs.get("notice_type", "全部"),
                begin_date=kwargs.get("begin_date"),
                end_date=kwargs.get("end_date"),
            )
        self._require("stock_notice_report")
        return self.akshare.stock_notice_report(symbol=kwargs.get("notice_type", "全部"), date=kwargs.get("date") or self._date_str())

    def _require(self, name: str) -> None:
        if not hasattr(self.akshare, name):
            raise RuntimeError(f"akshare {name} unavailable")

    def _market(self, symbol: str) -> str:
        return "sh" if symbol.startswith(("6", "9")) else "sz"

    def _date_str(self, days_ago: int = 0) -> str:
        return (date.today() - timedelta(days=days_ago)).strftime("%Y%m%d")
