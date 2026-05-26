from __future__ import annotations

import time
from typing import Any, Callable, Dict, Iterable, List

from stock_assistant.data_sources.adapters import AStockDataAdapter
from stock_assistant.data_sources.catalog import endpoint_names


QUICK_CHECKS = ["daily_bars", "stock_news", "financial_statements"]
FULL_CHECKS = endpoint_names()
PROFILE_CHECKS = {"quick": QUICK_CHECKS, "full": FULL_CHECKS}
DEFAULT_CHECKS = QUICK_CHECKS


class DataHealthChecker:
    def __init__(self, provider: Any | None = None) -> None:
        self.provider = provider or AStockDataAdapter()

    def check(self, symbol: str, checks: Iterable[str] | None = None) -> Dict[str, Any]:
        selected = list(checks or DEFAULT_CHECKS)
        results: Dict[str, Dict[str, Any]] = {}
        summary: Dict[str, int] = {"ok": 0, "empty": 0, "fail": 0, "unsupported": 0, "unavailable": 0}
        for name in selected:
            results[name] = self._run_one(name, symbol)
            summary.setdefault(results[name]["status"], 0)
            summary[results[name]["status"]] += 1
        return {"symbol": symbol, "summary": summary, "checks": results}

    def _run_one(self, name: str, symbol: str) -> Dict[str, Any]:
        started = time.perf_counter()
        try:
            value = self._call(name, symbol)
            if isinstance(value, dict) and {"status", "data", "message"}.issubset(value.keys()):
                status = value["status"]
                sample_size = self._sample_size(value.get("data"))
                message = self._clean_reason(value.get("message", ""))
            else:
                sample_size = self._sample_size(value)
                status = "ok" if sample_size > 0 else "empty"
                message = "" if status == "ok" else "接口返回空结果"
        except Exception as exc:
            sample_size = 0
            status = "fail"
            message = self._clean_reason(str(exc))
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {"status": status, "latency_ms": latency_ms, "sample_size": sample_size, "message": message}

    def _call(self, name: str, symbol: str) -> Any:
        call_map: Dict[str, Callable[[], Any]] = {
            "realtime_quote": lambda: self.provider.quote(symbol),
            "quote": lambda: self.provider.quote(symbol),
            "stock_basic": lambda: self.provider.stock_basic(symbol),
            "daily_bars": lambda: self.provider.daily_bars(symbol),
            "sector_performance": lambda: self.provider.sector_performance(),
            "concept_blocks": lambda: self.provider.concept_blocks(symbol),
            "financial_snapshot": lambda: self.provider.financial_snapshot(symbol),
            "announcements": lambda: self.provider.announcements(symbol),
            "stock_news": lambda: self.provider.stock_news(symbol),
            "news": lambda: self.provider.stock_news(symbol),
            "capital_flow": lambda: self.provider.capital_flow(symbol),
        }
        if hasattr(self.provider, "fetch"):
            return self.provider.fetch(name, symbol)
        if name not in call_map:
            raise ValueError(f"Unknown data health check: {name}")
        return call_map[name]()

    def _sample_size(self, value: Any) -> int:
        if value is None:
            return 0
        if hasattr(value, "empty"):
            return 0 if value.empty else len(value)
        if isinstance(value, dict):
            return len(value)
        if isinstance(value, (list, tuple, set)):
            return len(value)
        return 1

    def to_markdown(self, result: Dict[str, Any]) -> str:
        summary = result["summary"]
        lines: List[str] = [
            f"# 数据源健康检查：{result['symbol']}",
            "",
            f"- ok：{summary['ok']}",
            f"- empty：{summary['empty']}",
            f"- fail：{summary['fail']}",
            f"- unsupported：{summary.get('unsupported', 0)}",
            f"- unavailable：{summary.get('unavailable', 0)}",
            "",
            "| 接口 | 状态 | 耗时ms | 样本数 | 说明 |",
            "|---|---:|---:|---:|---|",
        ]
        for name, item in result["checks"].items():
            lines.append(
                f"| {name} | {item['status']} | {item['latency_ms']} | {item['sample_size']} | {item['message']} |"
            )
        return "\n".join(lines)

    def _clean_reason(self, reason: str) -> str:
        text = str(reason).replace("\n", " ").strip()
        if "ProxyError" in text:
            return "代理连接失败"
        if "Expecting value" in text and "char 0" in text:
            return "接口返回非 JSON，可能为空响应、被代理拦截或上游反爬"
        if "Max retries exceeded" in text or "RemoteDisconnected" in text:
            return "接口连接失败"
        if len(text) > 90:
            return text[:87] + "..."
        return text
