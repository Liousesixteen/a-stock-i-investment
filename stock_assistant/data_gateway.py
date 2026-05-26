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
    "daily_bars",
    "stock_news",
    "financial_statements",
    "sector_performance",
    "concept_blocks",
    "capital_flow_120d",
    "northbound_flow",
    "dragon_tiger",
    "lockup_calendar",
    "announcements",
}

CACHE_TTL_SECONDS = {
    "realtime_quote": 60,
    "market_snapshot": 60,
    "stock_basic": 86400,
    "daily_bars": 300,
    "sector_performance": 300,
    "stock_news": 600,
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
            return "真实数据接口代理连接失败，已使用降级数据"
        if "EOF occurred in violation of protocol" in text or "_ssl" in text:
            return "真实数据接口 SSL 连接失败，已使用降级数据"
        if "Max retries exceeded" in text or "RemoteDisconnected" in text:
            return "真实数据接口连接失败，已使用降级数据"
        if len(text) > 120:
            return text[:117] + "..."
        return text


class AStockDataGateway:
    """Single data boundary for analyzers.

    MVP uses deterministic fallback data. Live integrations can be added behind
    these methods without changing analyzers or workflows.
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
                fallback = self._sample_stock_basic(code)
                if not live_basic.get("concepts") and fallback.get("concepts"):
                    live_basic["concepts"] = fallback["concepts"]
                    live_basic.setdefault("missing_data", []).append(
                        MissingData("local_concepts", "真实概念标签缺失，使用本地标签补充").to_dict()
                    )
                if live_basic.get("industry") in ("", None, "未知行业") and fallback.get("industry"):
                    live_basic["industry"] = fallback["industry"]
                    live_basic.setdefault("missing_data", []).append(
                        MissingData("local_industry", "真实行业标签缺失，使用本地标签补充").to_dict()
                    )
                self._write_cached_dict(f"stock_basic_{code}", live_basic, "stock_basic", live_basic.get("source", "a-stock-data"))
                return live_basic
            except Exception:
                pass
        return self._sample_stock_basic(code)

    def _sample_stock_basic(self, code: str) -> Dict[str, Any]:
        samples = {
            "002415": {
                "symbol": code,
                "name": "海康威视",
                "industry": "计算机设备",
                "concepts": ["人工智能", "安防", "机器人"],
                "market": "深市",
                "missing_data": [],
            },
            "603019": {
                "symbol": code,
                "name": "中科曙光",
                "industry": "计算机设备",
                "concepts": ["AI算力", "数据中心", "国产服务器"],
                "market": "沪市",
                "missing_data": [],
            },
        }
        return samples.get(
            code,
            {
                "symbol": code,
                "name": code,
                "industry": "未知行业",
                "concepts": [],
                "market": "未知市场",
                "missing_data": [MissingData("stock_basic", "基础资料缺失").to_dict()],
            },
        )

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
        if code == "002415":
            quote = {
                "symbol": code,
                "name": basic["name"],
                "price": 31.86,
                "pct_chg": 1.24,
                "open": 31.28,
                "high": 32.15,
                "low": 31.02,
                "pre_close": 31.47,
                "volume": 48230000,
                "amount": 1539000000,
                "turnover_rate": 0.52,
                "pe_ttm": 21.4,
                "pb": 2.88,
                "market_cap": 293000000000,
                "float_market_cap": 274000000000,
                "limit_up": 34.62,
                "limit_down": 28.32,
                "source": "sample",
                "missing_data": [],
            }
            if live_error:
                quote["missing_data"].append(MissingData("live_quote", live_error).to_dict())
            return quote
        return {
            "symbol": code,
            "name": basic["name"],
            "price": 10.0,
            "pct_chg": 0.0,
            "open": 10.0,
            "high": 10.0,
            "low": 10.0,
            "pre_close": 10.0,
            "volume": 0,
            "amount": 0,
            "turnover_rate": 0.0,
            "pe_ttm": None,
            "pb": None,
            "market_cap": None,
            "float_market_cap": None,
            "limit_up": 11.0,
            "limit_down": 9.0,
            "source": "sample",
            "missing_data": [MissingData("realtime_quote", "实时行情使用降级样例").to_dict()],
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
                    self._write_cached_frame(f"daily_bars_{code}", bars, "a-stock-data", ttl_key="daily_bars")
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
        if code == "000000":
            return pd.DataFrame(columns=DAILY_COLUMNS)
        closes = [27.8, 28.1, 28.4, 28.0, 28.8, 29.4, 29.1, 29.8, 30.2, 30.6, 31.0, 31.6, 31.86]
        rows: List[Dict[str, Any]] = []
        for idx, close in enumerate(closes, start=1):
            previous = closes[idx - 2] if idx > 1 else close
            rows.append(
                {
                    "date": f"2026-05-{idx + 10:02d}",
                    "open": round(close * 0.99, 2),
                    "high": round(close * 1.025, 2),
                    "low": round(close * 0.975, 2),
                    "close": close,
                    "volume": 25000000 + idx * 1800000,
                    "amount": int((25000000 + idx * 1800000) * close),
                    "turnover_rate": round(0.35 + idx * 0.02, 2),
                    "pct_chg": round((close - previous) / previous * 100, 2) if previous else 0,
                }
            )
        return pd.DataFrame(rows, columns=DAILY_COLUMNS)

    def get_index_bars(self, index_code: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"date": "2026-05-22", "close": 3150, "pct_chg": 0.42, "amount": 890000000000},
                {"date": "2026-05-25", "close": 3164, "pct_chg": 0.44, "amount": 920000000000},
            ]
        )

    def get_market_snapshot(self) -> Dict[str, Any]:
        cached = self._read_cached_dict("market_snapshot")
        if cached is not None:
            return cached
        indices = []
        if self.use_live and self.live_provider and hasattr(self.live_provider, "index_quotes"):
            try:
                indices = self.live_provider.index_quotes()
            except Exception:
                indices = []
        if not indices:
            indices = [
                {"name": "上证指数", "price": 3150, "pct_chg": 0.42, "amount": 890000000000},
                {"name": "深证成指", "price": 9800, "pct_chg": 0.28, "amount": 920000000000},
                {"name": "创业板指", "price": 1900, "pct_chg": 0.44, "amount": 420000000000},
            ]
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
            "source": "a-stock-data" if self.use_live else "sample",
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
            net = hgt + sgt
            return {"net_inflow": net, "status": "净流入" if net > 0 else "净流出", "hgt": hgt, "sgt": sgt}
        net = self._to_float(northbound.get("net_inflow", 0))
        return {"net_inflow": net, "status": northbound.get("status", "净流入" if net > 0 else "净流出")}

    def _market_summary(self, indices: List[Dict[str, Any]], northbound: Dict[str, Any]) -> str:
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
        if failure:
            return self._sample_sector_performance(failure)
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
        return self._sample_sector_performance()

    def _sample_sector_performance(self, failure: Dict[str, Any] | None = None) -> pd.DataFrame:
        frame = pd.DataFrame(
            [
                {"sector": "计算机设备", "pct_chg": 1.8, "amount": 82000000000, "strength": "强于大盘"},
                {"sector": "新能源", "pct_chg": 0.4, "amount": 64000000000, "strength": "中性"},
                {"sector": "消费电子", "pct_chg": -0.3, "amount": 51000000000, "strength": "弱于大盘"},
            ]
        )
        frame.attrs["source"] = "sample"
        if failure:
            frame.attrs["missing_data"] = [MissingData("sector_performance", failure.get("reason", "真实板块接口冷却中")).to_dict()]
        return frame

    def get_concept_performance(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"concept": "AI算力", "pct_chg": 2.4, "heat": 76},
                {"concept": "机器人", "pct_chg": 1.2, "heat": 63},
                {"concept": "数据中心", "pct_chg": 1.7, "heat": 70},
            ]
        )

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
        snapshot = {
            "report_date": "2026Q1",
            "revenue": 17800000000,
            "revenue_yoy": 6.2,
            "net_profit": 2300000000,
            "net_profit_yoy": 8.1,
            "gross_margin": 44.5,
            "net_margin": 12.9,
            "roe": 3.1,
            "debt_ratio": 39.0,
            "operating_cashflow": 1800000000,
            "free_cashflow": 900000000,
            "eps": 0.25,
            "bps": 8.7,
            "missing_data": [],
        }
        if live_error:
            snapshot["missing_data"].append(MissingData("live_financial_snapshot", live_error).to_dict())
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
        return {"missing_data": [MissingData("financial_statements", "MVP 未启用完整三表").to_dict()]}

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
        row = {"symbol": code, "title": "近期无硬性利空样例公告", "announcement_type": "普通公告"}
        if live_error:
            row["missing_data"] = [MissingData("live_announcements", live_error).to_dict()]
        return [row]

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
        if code == "603019":
            row = {
                "symbol": code,
                "title": "AI算力需求增长带动服务器和数据中心基础设施关注",
                "summary": "服务器 数据中心 AI算力",
                "source": "sample",
            }
        else:
            row = {"symbol": code, "title": "AI 与安防场景融合受到关注", "source": "sample"}
        if live_error:
            row["missing_data"] = [MissingData("live_news", live_error).to_dict()]
        return [row]

    def _fallback_fetch(self, endpoint: str, symbol: str) -> Dict[str, Any]:
        if endpoint not in FRESH_FALLBACK_ENDPOINTS:
            return {"status": "unsupported", "data": None, "message": f"fallback disabled for {endpoint}"}
        for adapter in self.fallback_adapters:
            try:
                result = adapter.fetch(endpoint, symbol)
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

    def _standardize_daily_bars(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        rename = {"日期": "date", "开盘": "open", "最高": "high", "最低": "low", "收盘": "close", "成交量": "volume", "成交额": "amount", "换手率": "turnover_rate", "涨跌幅": "pct_chg"}
        df = df.rename(columns=rename)
        for column in DAILY_COLUMNS:
            if column not in df:
                df[column] = 0
        return df[DAILY_COLUMNS]

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
        fallback = pd.DataFrame(
            [{"symbol": code, "date": "2026-05-25", "main_net_inflow": 86000000, "net_inflow_pct": 3.2}]
        )
        fallback_result = self._fallback_fetch("capital_flow_120d", code) if not failure else {"status": "unavailable", "data": None}
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
        if live_error:
            fallback.attrs["missing_data"] = [MissingData("live_capital_flow", live_error).to_dict()]
            fallback.attrs["missing_data_fields"] = ["live_capital_flow"]
            fallback.attrs["source"] = "sample"
            fallback.attrs["is_fallback"] = True
        return fallback

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
        return {"net_inflow": 1200000000, "status": "温和流入"}

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
