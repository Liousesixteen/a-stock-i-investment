from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import pandas as pd

from stock_assistant.cache import JsonCache
from stock_assistant.utils import normalize_symbol


DAILY_COLUMNS = [
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

FRESH_FALLBACK_ENDPOINTS = {
    "realtime_quote",
    "stock_basic",
    "index_bars",
    "daily_bars",
    "stock_news",
    "cls_news",
    "global_news",
    "financial_statements",
    "sector_performance",
    "concept_blocks",
    "capital_flow_minute",
    "capital_flow_120d",
    "northbound_flow",
    "dragon_tiger",
    "market_dragon_tiger",
    "lockup_calendar",
    "margin_trading",
    "block_trades",
    "shareholder_count",
    "dividend_history",
    "announcements",
}

CACHE_TTL_SECONDS = {
    "realtime_quote": 60,
    "market_snapshot": 60,
    "stock_basic": 86400,
    "daily_bars": 300,
    "sector_performance": 300,
    "stock_news": 600,
    "market_news": 600,
    "announcements": 86400,
    "capital_flow_120d": 300,
    "financial_snapshot": 86400,
    "financial_statements": 86400,
}

FAILURE_COOLDOWN_SECONDS = 300


@dataclass
class MissingData:
    field: str
    reason: str

    def to_dict(self) -> Dict[str, str]:
        return {"field": self.field, "reason": self._clean_reason(self.reason)}

    def _clean_reason(self, reason: str) -> str:
        text = str(reason).replace("\n", " ").strip()
        if "ProxyError" in text:
            return "真实数据接口代理连接失败，已尝试真实备用源"
        if "EOF occurred in violation of protocol" in text or "_ssl" in text:
            return "真实数据接口 SSL 连接失败，已尝试真实备用源"
        if "Max retries exceeded" in text or "RemoteDisconnected" in text:
            return "真实数据接口连接失败，已尝试真实备用源"
        if len(text) > 120:
            return text[:117] + "..."
        return text


class AStockDataGateway:
    """Single data boundary for analyzers.

    Returns real live data, real fallback data, cache, or explicit missing-data
    placeholders. It must not invent synthetic market data.
    """

    def __init__(
        self,
        cache: JsonCache | None = None,
        use_live: bool = False,
        live_provider: Any | None = None,
        fallback_adapters: List[Any] | None = None,
    ) -> None:
        self.cache = cache or JsonCache()
        self.use_live = use_live
        self.fallback_adapters = fallback_adapters if fallback_adapters is not None else []
        if live_provider is not None:
            self.live_provider = live_provider
        elif use_live:
            from stock_assistant.providers.astock_data import AStockDataLiveProvider

            self.live_provider = AStockDataLiveProvider()
        else:
            self.live_provider = None
        if use_live and fallback_adapters is None:
            try:
                from stock_assistant.data_sources.adapters import AkShareAdapter

                self.fallback_adapters = [AkShareAdapter()]
            except Exception:
                self.fallback_adapters = []

    def normalize_symbol(self, symbol: str) -> str:
        return normalize_symbol(symbol)

    def get_stock_basic(self, symbol: str) -> Dict[str, Any]:
        code = normalize_symbol(symbol)
        cached = self._read_cached_dict(f"stock_basic_{code}")
        if cached is not None:
            return cached
        if self.use_live and self.live_provider and hasattr(self.live_provider, "stock_basic"):
            try:
                live_basic = self.live_provider.stock_basic(code)
                self._write_cached_dict(f"stock_basic_{code}", live_basic, "stock_basic", live_basic.get("source", "a-stock-data"))
                return live_basic
            except Exception:
                pass
        fallback = self._fallback_fetch("stock_basic", code)
        if fallback.get("status") == "ok" and fallback.get("data") is not None:
            basic = self._standardize_stock_basic(fallback["data"], code, self._fallback_provider_name(fallback))
            self._write_cached_dict(f"stock_basic_{code}", basic, "stock_basic", basic.get("source", "fallback"))
            return basic
        return {
            "symbol": code,
            "name": code,
            "industry": "",
            "concepts": [],
            "market": "",
            "missing_data": [MissingData("stock_basic", "真实基础资料缺失").to_dict()],
        }

    def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        code = normalize_symbol(symbol)
        cached = self._read_cached_dict(f"stock_realtime_{code}")
        if cached is not None:
            return cached
        live_error = None
        if self.use_live and self.live_provider:
            try:
                quote = self.live_provider.quote(code)
                self.cache.write(f"stock_realtime_{code}", quote, 60, "a-stock-data")
                return quote
            except Exception as exc:
                live_error = str(exc)
        basic = self.get_stock_basic(code)
        fallback = self._fallback_fetch("realtime_quote", code)
        if fallback.get("status") == "ok" and fallback.get("data") is not None:
            quote = self._standardize_realtime_quote(fallback["data"], code, self._fallback_provider_name(fallback))
            if live_error:
                quote.setdefault("missing_data", []).append(MissingData("live_quote", live_error).to_dict())
            return quote
        missing = [MissingData("realtime_quote", "真实实时行情缺失").to_dict()]
        if live_error:
            missing.append(MissingData("live_quote", live_error).to_dict())
        return {
            "symbol": code,
            "name": basic["name"],
            "price": None,
            "pct_chg": None,
            "open": None,
            "high": None,
            "low": None,
            "pre_close": None,
            "volume": 0,
            "amount": 0,
            "turnover_rate": None,
            "pe_ttm": None,
            "pb": None,
            "market_cap": None,
            "float_market_cap": None,
            "limit_up": None,
            "limit_down": None,
            "source": "missing",
            "missing_data": missing,
        }

    def get_daily_bars(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        code = normalize_symbol(symbol)
        cached = self._read_cached_frame(f"daily_bars_{code}")
        if cached is not None:
            return cached
        if self.use_live and self.live_provider:
            try:
                bars = self.live_provider.daily_bars(code)
                if not bars.empty:
                    bars = bars.copy()
                    source = bars.attrs.get("source", "a-stock-data")
                    bars.attrs["source"] = source
                    self._write_cached_frame(f"daily_bars_{code}", bars, source, ttl_key="daily_bars")
                    return bars
            except Exception:
                pass
        fallback = self._fallback_fetch("daily_bars", code)
        if fallback.get("status") == "ok" and fallback.get("data") is not None:
            data = fallback["data"]
            if isinstance(data, pd.DataFrame) and not data.empty:
                frame = self._mark_fallback_frame(self._standardize_daily_bars(data), fallback)
                self._write_cached_frame(f"daily_bars_{code}", frame, self._fallback_provider_name(fallback), ttl_key="daily_bars")
                return frame
        return pd.DataFrame(columns=DAILY_COLUMNS)

    def get_index_bars(self, index_code: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        fallback = self._fallback_fetch("index_bars", "000000", index_symbol=index_code, start_date=start, end_date=end)
        if fallback.get("status") == "ok" and isinstance(fallback.get("data"), pd.DataFrame) and not fallback["data"].empty:
            return self._mark_fallback_frame(self._standardize_index_bars(fallback["data"]), fallback)
        return pd.DataFrame(columns=["date", "close", "pct_chg", "amount"])

    def get_market_snapshot(self) -> Dict[str, Any]:
        cached = self._read_cached_dict("market_snapshot")
        if cached is not None:
            return cached
        indices = []
        indices_source = "missing"
        if self.use_live and self.live_provider and hasattr(self.live_provider, "index_quotes"):
            try:
                indices = self.live_provider.index_quotes()
                if indices:
                    indices_source = "a-stock-data"
            except Exception:
                indices = []
        if not indices:
            indices = self._fallback_index_quotes()
            if indices:
                indices_source = "fallback"
        northbound = self.get_northbound_flow()
        total_amount = sum(float(item.get("amount") or 0) for item in indices)
        summary = self._market_summary(indices, northbound)
        scenarios = self._market_scenarios(indices, northbound)
        snapshot = {
            "indices": indices,
            "northbound": self._standardize_northbound(northbound),
            "total_amount": total_amount,
            "summary": summary,
            "scenarios": scenarios,
            "source": indices_source,
            "missing_data": [] if indices else [MissingData("market_snapshot", "真实指数快照缺失").to_dict()],
        }
        if self.use_live:
            self._write_cached_dict("market_snapshot", snapshot, "market_snapshot", snapshot["source"])
        return snapshot

    def _standardize_northbound(self, northbound: Dict[str, Any]) -> Dict[str, Any]:
        data = northbound.get("data")
        if isinstance(data, pd.DataFrame) and not data.empty:
            hgt_series = data["hgt_yi"].dropna() if "hgt_yi" in data else pd.Series(dtype=float)
            sgt_series = data["sgt_yi"].dropna() if "sgt_yi" in data else pd.Series(dtype=float)
            hgt = self._to_float(hgt_series.iloc[-1] if not hgt_series.empty else 0) * 100000000
            sgt = self._to_float(sgt_series.iloc[-1] if not sgt_series.empty else 0) * 100000000
            if hgt == 0 and sgt == 0:
                north_rows = data
                if "资金方向" in data:
                    north_rows = data.loc[data["资金方向"].astype(str).str.contains("北向", na=False)]
                if not north_rows.empty and "板块" in north_rows:
                    hgt_rows = north_rows.loc[north_rows["板块"].astype(str).str.contains("沪股通", na=False)]
                    sgt_rows = north_rows.loc[north_rows["板块"].astype(str).str.contains("深股通", na=False)]
                    hgt = self._latest_yi_value(hgt_rows, "成交净买额", "资金净流入", "当日资金流入")
                    sgt = self._latest_yi_value(sgt_rows, "成交净买额", "资金净流入", "当日资金流入")
                if hgt == 0 and sgt == 0:
                    net_yi = self._latest_yi_value(north_rows, "当日成交净买额", "成交净买额", "资金净流入", "当日资金流入")
                    hgt = net_yi
            net = hgt + sgt
            return {"net_inflow": net, "status": "净流入" if net > 0 else "净流出", "hgt": hgt, "sgt": sgt}
        net = self._to_float(northbound.get("net_inflow", 0))
        status = northbound.get("status")
        if not status or status == "live":
            status = "净流入" if net > 0 else "净流出" if net < 0 else "持平"
        return {"net_inflow": net, "status": status}

    def _market_summary(self, indices: List[Dict[str, Any]], northbound: Dict[str, Any]) -> str:
        if not indices:
            return "指数快照缺失，无法判断大盘状态"
        pct_values = [self._to_float(item.get("pct_chg")) for item in indices]
        up_count = sum(1 for value in pct_values if value > 0)
        down_count = sum(1 for value in pct_values if value < 0)
        growth = next((item for item in indices if item.get("name") == "创业板指"), {})
        tech = next((item for item in indices if item.get("name") == "科创50"), {})
        north = self._standardize_northbound(northbound)
        if up_count > down_count and self._to_float(growth.get("pct_chg")) >= 0:
            tone = "指数分化但成长方向有承接"
        elif down_count > up_count:
            tone = "指数偏弱，风险偏好下降"
        else:
            tone = "指数震荡分化"
        if self._to_float(tech.get("pct_chg")) < -1:
            tone += "，科创方向承压"
        if north.get("net_inflow", 0) < 0:
            tone += "，北向资金净流出"
        return tone

    def _market_scenarios(self, indices: List[Dict[str, Any]], northbound: Dict[str, Any]) -> Dict[str, str]:
        if not indices:
            return {
                "base": "指数快照缺失，先等待真实数据恢复",
                "bull": "真实指数和量能恢复后再判断偏强情景",
                "bear": "真实指数缺失时不扩大风险敞口",
            }
        sh = next((item for item in indices if item.get("name") == "上证指数"), {})
        sh_price = self._to_float(sh.get("price"))
        north = self._standardize_northbound(northbound)
        support = round(sh_price * 0.99, 0) if sh_price else "关键支撑"
        pressure = round(sh_price * 1.01, 0) if sh_price else "上方压力"
        base = f"大概率围绕 {support}-{pressure} 震荡分化，观察量能和北向资金是否修复"
        bull = f"若上证放量站上 {pressure} 且北向流出收窄，指数有望震荡上修"
        bear = f"若跌破 {support} 且{north.get('status', '北向资金')}扩大，需防题材退潮和高弹性方向补跌"
        return {"base": base, "bull": bull, "bear": bear}

    def get_sector_performance(self) -> pd.DataFrame:
        cached = self._read_cached_frame("sector_performance")
        if cached is not None:
            return cached
        failure = self._read_failure("sector_performance")
        if self.use_live and self.live_provider and hasattr(self.live_provider, "sector_performance"):
            try:
                sectors = self.live_provider.sector_performance()
                if not sectors.empty:
                    self._write_cached_frame("sector_performance", sectors, "a-stock-data")
                    return sectors
            except Exception:
                pass
        fallback = self._fallback_fetch("sector_performance", "000000")
        if fallback.get("status") == "ok" and isinstance(fallback.get("data"), pd.DataFrame) and not fallback["data"].empty:
            frame = self._mark_fallback_frame(self._standardize_sector_performance(fallback["data"]), fallback)
            self._write_cached_frame("sector_performance", frame, self._fallback_provider_name(fallback))
            return frame
        self._write_failure("sector_performance", fallback.get("message", "sector source unavailable"))
        frame = pd.DataFrame(columns=["sector", "pct_chg", "amount", "strength"])
        reason = fallback.get("message") or (failure or {}).get("reason") or "真实板块数据缺失"
        frame.attrs["missing_data"] = [MissingData("sector_performance", reason).to_dict()]
        frame.attrs["source"] = "missing"
        return frame

    def get_concept_performance(self) -> pd.DataFrame:
        fallback = self._fallback_fetch("concept_blocks", "000000")
        if fallback.get("status") == "ok" and isinstance(fallback.get("data"), pd.DataFrame) and not fallback["data"].empty:
            return self._standardize_concept_performance(fallback["data"])
        frame = pd.DataFrame(columns=["concept", "pct_chg", "heat"])
        frame.attrs["missing_data"] = [MissingData("concept_blocks", fallback.get("message", "真实题材热度缺失")).to_dict()]
        frame.attrs["source"] = "missing"
        return frame

    def get_stock_valuation(self, symbol: str) -> Dict[str, Any]:
        quote = self.get_realtime_quote(symbol)
        return {
            "pe_ttm": quote.get("pe_ttm"),
            "pb": quote.get("pb"),
            "market_cap": quote.get("market_cap"),
            "valuation_level": "合理偏高" if quote.get("pe_ttm") else "未知",
            "missing_data": [] if quote.get("pe_ttm") else [MissingData("valuation", "估值数据缺失").to_dict()],
        }

    def get_financial_snapshot(self, symbol: str) -> Dict[str, Any]:
        code = normalize_symbol(symbol)
        cached = self._read_cached_dict(f"financial_snapshot_{code}")
        if cached is not None:
            return cached
        failure = self._read_failure(f"financial_snapshot_{code}")
        live_error = None
        if not failure and self.use_live and self.live_provider and hasattr(self.live_provider, "financial_snapshot"):
            try:
                snapshot = self.live_provider.financial_snapshot(symbol)
                self._write_cached_dict(f"financial_snapshot_{code}", snapshot, "financial_snapshot", snapshot.get("source", "a-stock-data"))
                return snapshot
            except Exception as exc:
                live_error = str(exc)
                self._write_failure(f"financial_snapshot_{code}", live_error)
        elif failure:
            live_error = failure.get("reason")
        statements = self.get_financial_statements(code)
        snapshot = self._snapshot_from_financial_statements(statements)
        snapshot.setdefault("missing_data", [])
        if live_error:
            snapshot["missing_data"].append(MissingData("live_financial_snapshot", live_error).to_dict())
        if snapshot.get("revenue_yoy") is None and snapshot.get("net_profit_yoy") is None:
            snapshot["missing_data"].append(MissingData("financial_snapshot", "真实财务快照缺失").to_dict())
        return snapshot

    def get_financial_statements(self, symbol: str) -> Dict[str, Any]:
        if self.use_live and self.live_provider and hasattr(self.live_provider, "financial_report"):
            statements = {}
            missing = []
            for report_type, name in [("lrb", "income_statement"), ("fzb", "balance_sheet"), ("llb", "cash_flow")]:
                try:
                    statements[name] = self.live_provider.financial_report(symbol, report_type)
                except Exception as exc:
                    statements[name] = []
                    missing.append(MissingData(name, str(exc)).to_dict())
            statements["missing_data"] = missing
            if any(statements.get(name) for name in ["income_statement", "balance_sheet", "cash_flow"]):
                return statements
            fallback = self._fallback_fetch("financial_statements", symbol)
            if fallback.get("status") == "ok":
                return {"fallback_provider": fallback.get("provider", self._fallback_provider_name(fallback)), "data": fallback.get("data"), "missing_data": missing}
            return statements
        fallback = self._fallback_fetch("financial_statements", symbol)
        if fallback.get("status") == "ok":
            return {"fallback_provider": fallback.get("provider", self._fallback_provider_name(fallback)), "data": fallback.get("data"), "missing_data": []}
        return {"missing_data": [MissingData("financial_statements", "真实财务三表缺失").to_dict()]}

    def get_announcements(self, symbol: str, days: int = 30) -> List[Dict[str, Any]]:
        code = normalize_symbol(symbol)
        cached = self._read_cached_list(f"announcements_{code}")
        if cached is not None:
            return cached
        live_error = None
        if self.use_live and self.live_provider and hasattr(self.live_provider, "announcements"):
            try:
                rows = self.live_provider.announcements(symbol, page_size=30)
                if rows:
                    self._write_cached_list(f"announcements_{code}", rows, "a-stock-data", "announcements")
                    return rows
                live_error = "真实公告接口返回空结果"
            except Exception as exc:
                live_error = str(exc)
        fallback = self._fallback_fetch("announcements", code)
        if fallback.get("status") == "ok" and fallback.get("data") is not None:
            rows = self._standardize_announcements(fallback["data"], code, self._fallback_provider_name(fallback))
            if rows:
                self._write_cached_list(f"announcements_{code}", rows, self._fallback_provider_name(fallback), "announcements")
                return rows
        return [{"symbol": code, "title": "", "announcement_type": "", "missing_data": [MissingData("announcements", live_error or "真实公告缺失").to_dict()]}]

    def get_news(self, symbol: str, days: int = 7) -> List[Dict[str, Any]]:
        code = normalize_symbol(symbol)
        cached = self._read_cached_list(f"stock_news_{code}")
        if cached is not None:
            return cached
        live_error = None
        if self.use_live and self.live_provider and hasattr(self.live_provider, "stock_news"):
            try:
                rows = self.live_provider.stock_news(symbol, page_size=20)
                if rows:
                    self._write_cached_list(f"stock_news_{code}", rows, "a-stock-data", "stock_news")
                    return rows
                live_error = "真实新闻接口返回空结果"
            except Exception as exc:
                live_error = str(exc)
        fallback = self._fallback_fetch("stock_news", code)
        if fallback.get("status") == "ok" and fallback.get("data") is not None:
            rows = self._standardize_news(fallback["data"], code)
            if rows:
                for row in rows:
                    row["source"] = self._fallback_provider_name(fallback)
                    row["is_fallback"] = True
                self._write_cached_list(f"stock_news_{code}", rows, self._fallback_provider_name(fallback), "stock_news")
                return rows
        return [{"symbol": code, "title": "", "source": "missing", "missing_data": [MissingData("stock_news", live_error or "真实个股新闻缺失").to_dict()]}]

    def get_market_news(self, page_size: int = 50) -> List[Dict[str, Any]]:
        cached = self._read_cached_list("market_news")
        if cached is not None:
            return cached
        rows: List[Dict[str, Any]] = []
        if self.use_live and self.live_provider:
            if hasattr(self.live_provider, "cls_news"):
                try:
                    rows.extend(self._standardize_market_news(self.live_provider.cls_news(page_size=page_size), "cls"))
                except Exception:
                    pass
            if hasattr(self.live_provider, "global_news"):
                try:
                    rows.extend(self._standardize_market_news(self.live_provider.global_news(page_size=page_size), "eastmoney_global"))
                except Exception:
                    pass
        if rows:
            self._write_cached_list("market_news", rows, "a-stock-data", "market_news")
            return rows
        for endpoint in ("cls_news", "global_news"):
            fallback = self._fallback_fetch(endpoint, "000000")
            if fallback.get("status") == "ok" and fallback.get("data") is not None:
                rows.extend(self._standardize_market_news(fallback["data"], self._fallback_provider_name(fallback)))
        if rows:
            self._write_cached_list("market_news", rows, "market_news", "live_fallback")
        return rows

    def _fallback_fetch(self, endpoint: str, symbol: str, **kwargs: Any) -> Dict[str, Any]:
        if endpoint not in FRESH_FALLBACK_ENDPOINTS:
            return {"status": "unsupported", "data": None, "message": f"fallback disabled for {endpoint}"}
        for adapter in self.fallback_adapters:
            try:
                result = adapter.fetch(endpoint, symbol, **kwargs)
                if result.get("status") == "ok":
                    result.setdefault("provider", adapter.__class__.__name__)
                    return result
            except Exception:
                continue
        return {"status": "unavailable", "data": None, "message": "no fallback data"}

    def _fallback_provider_name(self, fallback: Dict[str, Any]) -> str:
        return str(fallback.get("provider", "fallback"))

    def _mark_fallback_frame(self, data: pd.DataFrame, fallback: Dict[str, Any]) -> pd.DataFrame:
        frame = data.copy()
        frame.attrs["source"] = self._fallback_provider_name(fallback)
        frame.attrs["is_fallback"] = True
        frame.attrs["freshness"] = "live_fallback"
        return frame

    def _read_cached_frame(self, key: str) -> pd.DataFrame | None:
        payload = self.cache.read_fresh(key)
        if not payload:
            return None
        data = payload.get("data")
        if not isinstance(data, list):
            return None
        frame = pd.DataFrame(data)
        frame.attrs["source"] = payload.get("source", "cache")
        frame.attrs["is_cached"] = True
        frame.attrs["generated_at"] = payload.get("generated_at", "")
        return frame

    def _write_cached_frame(self, key: str, frame: pd.DataFrame, source: str, ttl_key: str | None = None) -> None:
        ttl = CACHE_TTL_SECONDS.get(ttl_key or key)
        if not ttl:
            return
        self.cache.write(key, frame.to_dict("records"), ttl, source)

    def _read_cached_dict(self, key: str) -> Dict[str, Any] | None:
        payload = self.cache.read_fresh(key)
        if not payload or not isinstance(payload.get("data"), dict):
            return None
        data = payload["data"].copy()
        data.setdefault("source", payload.get("source", "cache"))
        data["is_cached"] = True
        data["cache_generated_at"] = payload.get("generated_at", "")
        return data

    def _write_cached_dict(self, key: str, data: Dict[str, Any], ttl_key: str, source: str) -> None:
        ttl = CACHE_TTL_SECONDS.get(ttl_key)
        if ttl:
            self.cache.write(key, data, ttl, source)

    def _read_cached_list(self, key: str) -> List[Dict[str, Any]] | None:
        payload = self.cache.read_fresh(key)
        if not payload or not isinstance(payload.get("data"), list):
            return None
        rows = []
        for item in payload["data"]:
            if isinstance(item, dict):
                row = item.copy()
                row.setdefault("source", payload.get("source", "cache"))
                row["is_cached"] = True
                row["cache_generated_at"] = payload.get("generated_at", "")
                rows.append(row)
        return rows

    def _write_cached_list(self, key: str, rows: List[Dict[str, Any]], source: str, ttl_key: str) -> None:
        ttl = CACHE_TTL_SECONDS.get(ttl_key)
        if ttl and rows:
            self.cache.write(key, rows, ttl, source)

    def _read_failure(self, key: str) -> Dict[str, Any] | None:
        payload = self.cache.read_fresh(f"failure_{key}")
        if payload and isinstance(payload.get("data"), dict):
            return payload["data"]
        return None

    def _write_failure(self, key: str, reason: str) -> None:
        self.cache.write(f"failure_{key}", {"reason": reason}, FAILURE_COOLDOWN_SECONDS, "failure")

    def _standardize_stock_basic(self, data: Any, symbol: str, provider: str) -> Dict[str, Any]:
        row = self._first_record(data)
        name = row.get("name") or row.get("名称") or row.get("股票简称") or row.get("简称") or symbol
        industry = row.get("industry") or row.get("行业") or row.get("所属行业") or ""
        market = row.get("market") or row.get("市场") or ("沪市" if symbol.startswith(("6", "9")) else "深市" if symbol.startswith(("0", "3")) else "")
        concepts = row.get("concepts") or row.get("概念") or []
        if isinstance(concepts, str):
            concepts = [item.strip() for item in concepts.replace("，", ",").split(",") if item.strip()]
        return {
            "symbol": normalize_symbol(symbol),
            "name": name,
            "industry": industry,
            "concepts": concepts if isinstance(concepts, list) else [],
            "market": market,
            "source": provider,
            "is_fallback": True,
            "missing_data": [] if name != symbol else [MissingData("stock_basic_detail", "备用源仅获取到有限基础资料").to_dict()],
        }

    def _standardize_realtime_quote(self, data: Any, symbol: str, provider: str) -> Dict[str, Any]:
        row = self._first_record(data)
        basic = self.get_stock_basic(symbol)
        return {
            "symbol": normalize_symbol(symbol),
            "name": row.get("name") or row.get("名称") or basic.get("name", symbol),
            "price": self._value(row, "price", "最新价", "现价"),
            "pct_chg": self._value(row, "pct_chg", "涨跌幅"),
            "open": self._value(row, "open", "今开", "开盘"),
            "high": self._value(row, "high", "最高"),
            "low": self._value(row, "low", "最低"),
            "pre_close": self._value(row, "pre_close", "昨收"),
            "volume": self._value(row, "volume", "成交量"),
            "amount": self._value(row, "amount", "成交额"),
            "turnover_rate": self._value(row, "turnover_rate", "换手率"),
            "pe_ttm": self._value(row, "pe_ttm", "市盈率-动态", "市盈率"),
            "pb": self._value(row, "pb", "市净率"),
            "market_cap": self._value(row, "market_cap", "总市值"),
            "float_market_cap": self._value(row, "float_market_cap", "流通市值"),
            "limit_up": self._value(row, "limit_up", "涨停"),
            "limit_down": self._value(row, "limit_down", "跌停"),
            "source": provider,
            "is_fallback": True,
            "missing_data": [],
        }

    def _fallback_index_quotes(self) -> List[Dict[str, Any]]:
        mapping = [("上证指数", "000001"), ("深证成指", "399001"), ("创业板指", "399006")]
        rows = []
        for name, code in mapping:
            bars = self.get_index_bars(code)
            if bars.empty:
                continue
            latest = bars.iloc[-1]
            rows.append(
                {
                    "name": name,
                    "price": self._value(latest.to_dict(), "close", "收盘"),
                    "pct_chg": self._value(latest.to_dict(), "pct_chg", "涨跌幅"),
                    "amount": self._value(latest.to_dict(), "amount", "成交额"),
                }
            )
        return rows

    def _standardize_daily_bars(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        rename = {"日期": "date", "开盘": "open", "最高": "high", "最低": "low", "收盘": "close", "成交量": "volume", "成交额": "amount", "换手率": "turnover_rate", "涨跌幅": "pct_chg"}
        df = df.rename(columns=rename)
        for column in DAILY_COLUMNS:
            if column not in df:
                df[column] = 0
        return df[DAILY_COLUMNS]

    def _standardize_index_bars(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        rename = {"日期": "date", "收盘": "close", "涨跌幅": "pct_chg", "成交额": "amount"}
        df = df.rename(columns=rename)
        for column in ["date", "close", "pct_chg", "amount"]:
            if column not in df:
                df[column] = 0
        return df[["date", "close", "pct_chg", "amount"]]

    def _standardize_news(self, data: Any, symbol: str) -> List[Dict[str, Any]]:
        if isinstance(data, pd.DataFrame):
            rows = data.to_dict("records")
        elif isinstance(data, list):
            rows = data
        else:
            rows = []
        normalized = []
        for row in rows:
            normalized.append(
                {
                    "symbol": normalize_symbol(symbol),
                    "title": row.get("title") or row.get("新闻标题") or row.get("标题") or "",
                    "summary": row.get("summary") or row.get("新闻内容") or row.get("内容") or "",
                    "source": row.get("source") or row.get("文章来源") or "fallback",
                    "publish_time": row.get("publish_time") or row.get("发布时间") or "",
                    "url": row.get("url") or row.get("新闻链接") or "",
                    "raw_text": row.get("raw_text") or row.get("新闻内容") or "",
                }
            )
        return normalized

    def _standardize_concept_performance(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        rename = {
            "板块名称": "concept",
            "名称": "concept",
            "概念": "concept",
            "涨跌幅": "pct_chg",
            "最新价": "heat",
        }
        df = df.rename(columns=rename)
        if "concept" not in df:
            df["concept"] = ""
        if "pct_chg" not in df:
            df["pct_chg"] = 0
        if "heat" not in df:
            df["heat"] = 50
        df["pct_chg"] = df["pct_chg"].apply(self._to_float)
        df["heat"] = df["heat"].apply(self._to_float)
        return df[["concept", "pct_chg", "heat"]]

    def _standardize_market_news(self, data: Any, default_source: str) -> List[Dict[str, Any]]:
        if isinstance(data, pd.DataFrame):
            rows = data.to_dict("records")
        elif isinstance(data, list):
            rows = data
        else:
            rows = []
        normalized = []
        seen = set()
        for row in rows:
            title = row.get("title") or row.get("新闻标题") or row.get("标题") or row.get("brief") or ""
            if not title or title in seen:
                continue
            seen.add(title)
            normalized.append(
                {
                    "title": title,
                    "summary": row.get("summary") or row.get("content") or row.get("新闻内容") or row.get("内容") or "",
                    "source": row.get("source") or row.get("文章来源") or default_source,
                    "publish_time": row.get("publish_time") or row.get("发布时间") or row.get("time") or "",
                    "url": row.get("url") or row.get("新闻链接") or "",
                    "raw_text": row.get("raw_text") or row.get("content") or row.get("新闻内容") or "",
                }
            )
        return normalized

    def _standardize_sector_performance(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        rename = {
            "板块名称": "sector",
            "名称": "sector",
            "行业": "sector",
            "涨跌幅": "pct_chg",
            "涨跌幅%": "pct_chg",
            "最新涨跌幅": "pct_chg",
            "成交额": "amount",
        }
        df = df.rename(columns=rename)
        if "sector" not in df:
            df["sector"] = ""
        if "pct_chg" not in df:
            df["pct_chg"] = 0
        if "amount" not in df:
            df["amount"] = 0
        if "strength" not in df:
            df["strength"] = df["pct_chg"].apply(lambda value: "强于大盘" if self._to_float(value) > 0 else "弱于大盘")
        df["pct_chg"] = df["pct_chg"].apply(self._to_float)
        return df[["sector", "pct_chg", "amount", "strength"]]

    def _to_float(self, value: Any) -> float:
        try:
            if value in ("", "-", None):
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _value(self, row: Dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in row and row[key] not in ("", "-", None):
                return row[key]
        return None

    def _latest_yi_value(self, data: pd.DataFrame, *columns: str) -> float:
        for column in columns:
            if column not in data:
                continue
            series = pd.to_numeric(data[column], errors="coerce").dropna()
            if not series.empty:
                return float(series.iloc[-1]) * 100000000
        return 0.0

    def _value_by_alias(self, row: Dict[str, Any], *aliases: str) -> Any:
        for alias in aliases:
            if alias in row and row[alias] not in ("", "-", None):
                return row[alias]
        for alias in aliases:
            for key, value in row.items():
                if alias in str(key) and value not in ("", "-", None):
                    return value
        return None

    def _first_record(self, data: Any) -> Dict[str, Any]:
        if isinstance(data, pd.DataFrame):
            if data.empty:
                return {}
            return data.iloc[0].to_dict()
        if isinstance(data, list):
            return data[0] if data and isinstance(data[0], dict) else {}
        if isinstance(data, dict):
            return data
        return {}

    def _snapshot_from_financial_statements(self, statements: Dict[str, Any]) -> Dict[str, Any]:
        data = statements.get("data")
        frame = data if isinstance(data, pd.DataFrame) else None
        row = self._first_record(frame) if frame is not None else self._first_record(data)
        if isinstance(frame, pd.DataFrame) and {"指标", "选项"}.issubset(frame.columns):
            row = self._financial_metric_matrix_row(frame)
        return {
            "report_date": self._value_by_alias(row, "报告期", "报告日", "REPORT_DATE", "report_date", "日期"),
            "revenue": self._value_by_alias(row, "营业收入", "营业总收入", "TOTALOPERATEREVE", "revenue"),
            "revenue_yoy": self._value_by_alias(row, "营业收入同比增长率", "营业总收入同比增长率", "TOTALOPERATEREVETZ", "revenue_yoy"),
            "net_profit": self._value_by_alias(row, "归母净利润", "净利润", "PARENTNETPROFIT", "net_profit"),
            "net_profit_yoy": self._value_by_alias(row, "净利润同比增长率", "PARENTNETPROFITTZ", "net_profit_yoy"),
            "gross_margin": self._value_by_alias(row, "销售毛利率", "XSMLL", "gross_margin"),
            "net_margin": self._value_by_alias(row, "销售净利率", "XSJLL", "net_margin"),
            "roe": self._value_by_alias(row, "净资产收益率", "ROEJQ", "roe"),
            "debt_ratio": self._value_by_alias(row, "资产负债率", "ZCFZL", "debt_ratio"),
            "operating_cashflow": self._value_by_alias(row, "经营活动产生的现金流量净额", "每股经营现金流", "MGJYXJJE", "operating_cashflow"),
            "free_cashflow": self._value_by_alias(row, "FCFF_FORWARD", "free_cashflow"),
            "eps": self._value_by_alias(row, "基本每股收益", "每股收益", "EPSJB", "eps"),
            "bps": self._value_by_alias(row, "每股净资产", "BPS", "bps"),
            "source": statements.get("fallback_provider") or statements.get("source") or "missing",
            "missing_data": statements.get("missing_data", []),
        }

    def _financial_metric_matrix_row(self, frame: pd.DataFrame) -> Dict[str, Any]:
        periods = [str(column) for column in frame.columns if str(column).isdigit()]
        if not periods:
            return {}
        latest_period = sorted(periods, reverse=True)[0]
        row: Dict[str, Any] = {"报告期": latest_period}
        for _, item in frame.iterrows():
            metric = str(item.get("指标", ""))
            if metric:
                row[metric] = item.get(latest_period)
        return row


    def _standardize_announcements(self, data: Any, symbol: str, provider: str) -> List[Dict[str, Any]]:
        if isinstance(data, pd.DataFrame):
            rows = data.to_dict("records")
        elif isinstance(data, list):
            rows = data
        else:
            rows = []
        normalized = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            normalized.append(
                {
                    "symbol": normalize_symbol(symbol),
                    "title": row.get("title") or row.get("公告标题") or row.get("标题") or row.get("announcementTitle") or "",
                    "announcement_type": row.get("announcement_type") or row.get("公告类型") or row.get("类型") or "",
                    "publish_time": row.get("publish_time") or row.get("公告日期") or row.get("发布时间") or row.get("date") or "",
                    "url": row.get("url") or row.get("公告链接") or "",
                    "source": provider,
                    "is_fallback": True,
                }
            )
        return [row for row in normalized if row["title"]]

    def get_research_reports(self, symbol: str | None = None, industry: str | None = None) -> List[Dict[str, Any]]:
        if self.use_live and self.live_provider and symbol and hasattr(self.live_provider, "research_reports"):
            try:
                rows = self.live_provider.research_reports(symbol, max_pages=1)
                normalized = []
                for row in rows:
                    normalized.append(
                        {
                            "symbol": normalize_symbol(symbol),
                            "source": "eastmoney_report",
                            "title": row.get("title", ""),
                            "summary": row.get("orgSName", ""),
                            "publish_time": row.get("publishDate", ""),
                            "info_code": row.get("infoCode", ""),
                            "rating": row.get("emRatingName", ""),
                        }
                    )
                if normalized:
                    return normalized
            except Exception:
                pass
        return []

    def get_capital_flow(self, symbol: str) -> pd.DataFrame:
        live_error = None
        code = normalize_symbol(symbol)
        failure = self._read_failure(f"capital_flow_120d_{code}")
        if not failure and self.use_live and self.live_provider and hasattr(self.live_provider, "capital_flow"):
            try:
                flow = self.live_provider.capital_flow(symbol)
                if not flow.empty:
                    return flow
                live_error = "真实资金流接口返回空结果"
            except Exception as exc:
                live_error = str(exc)
                self._write_failure(f"capital_flow_120d_{code}", live_error)
        elif failure:
            live_error = failure.get("reason")
        fallback_result = self._fallback_fetch("capital_flow_120d", code)
        if fallback_result.get("status") == "ok" and isinstance(fallback_result.get("data"), pd.DataFrame) and not fallback_result["data"].empty:
            flow = fallback_result["data"].copy()
            rename = {
                "main_net": "main_net_inflow",
                "日期": "date",
                "主力净流入": "main_net_inflow",
                "主力净流入-净额": "main_net_inflow",
                "主力净流入净额": "main_net_inflow",
            }
            flow = flow.rename(columns=rename)
            if "main_net_inflow" not in flow:
                flow["main_net_inflow"] = 0
            return self._mark_fallback_frame(flow, fallback_result)
        empty = pd.DataFrame(columns=["symbol", "date", "main_net_inflow", "net_inflow_pct"])
        empty.attrs["missing_data"] = [MissingData("capital_flow_120d", live_error or "真实资金流缺失").to_dict()]
        empty.attrs["missing_data_fields"] = ["capital_flow_120d"]
        empty.attrs["source"] = "missing"
        return empty

    def get_northbound_flow(self) -> Dict[str, Any]:
        if self.use_live and self.live_provider and hasattr(self.live_provider, "northbound_flow"):
            try:
                data = self.live_provider.northbound_flow()
                if hasattr(data, "empty") and not data.empty:
                    return {"source": "a-stock-data", "data": data, "status": "live"}
            except Exception:
                pass
        fallback = self._fallback_fetch("northbound_flow", "000000")
        if fallback.get("status") == "ok":
            return {"source": self._fallback_provider_name(fallback), "data": fallback.get("data"), "status": "live_fallback"}
        return {"net_inflow": None, "status": "缺失", "missing_data": [MissingData("northbound_flow", "真实北向资金缺失").to_dict()]}

    def get_dragon_tiger(self, symbol: str, days: int = 30) -> List[Dict[str, Any]]:
        if self.use_live and self.live_provider and hasattr(self.live_provider, "dragon_tiger"):
            try:
                data = self.live_provider.dragon_tiger(symbol, look_back=days)
                records = data.get("records", []) if isinstance(data, dict) else data
                if records:
                    return records
            except Exception:
                pass
        fallback = self._fallback_fetch("dragon_tiger", normalize_symbol(symbol))
        if fallback.get("status") == "ok" and fallback.get("data") is not None:
            data = fallback["data"].to_dict("records") if isinstance(fallback["data"], pd.DataFrame) else fallback["data"]
            return data if isinstance(data, list) else [data]
        return []

    def get_lockup_calendar(self, symbol: str, days: int = 180) -> List[Dict[str, Any]]:
        if self.use_live and self.live_provider and hasattr(self.live_provider, "lockup_calendar"):
            try:
                data = self.live_provider.lockup_calendar(symbol, forward_days=days)
                rows = data.get("upcoming", []) if isinstance(data, dict) else data
                if rows:
                    return rows
            except Exception:
                pass
        fallback = self._fallback_fetch("lockup_calendar", normalize_symbol(symbol))
        if fallback.get("status") == "ok" and fallback.get("data") is not None:
            data = fallback["data"].to_dict("records") if isinstance(fallback["data"], pd.DataFrame) else fallback["data"]
            return data if isinstance(data, list) else [data]
        return []
