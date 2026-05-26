from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List


class AnnouncementAnalyzer:
    HARD_BLOCK_KEYWORDS = ["立案调查", "退市风险", "重大违法", "财务造假"]
    WARN_KEYWORDS = ["减持", "解禁", "诉讼", "监管问询", "业绩预亏"]

    def __init__(self, rules: Dict[str, Any] | None = None) -> None:
        self.hard_block_keywords = list((rules or {}).get("hard_block_events", self.HARD_BLOCK_KEYWORDS))
        self.warn_keywords = list((rules or {}).get("warn_events", self.WARN_KEYWORDS))

    def analyze(self, announcements: List[Dict[str, Any]]) -> Dict[str, Any]:
        filtered_announcements = self._recent_unique(announcements)
        if not filtered_announcements:
            return {
                "announcement_score": 50,
                "event_risk": "unknown",
                "signals": [],
                "warnings": ["未获取到近期公告，事件风险未知"],
                "hard_blocks": [],
                "confidence": 0.3,
                "filtered_count": 0,
            }

        hard_blocks: List[str] = []
        warnings: List[str] = []
        signals: List[str] = []
        for item in filtered_announcements:
            title = item.get("title", "")
            for keyword in self.hard_block_keywords:
                if keyword in title:
                    hard_blocks.append(f"{keyword}: {title}")
            for keyword in self.warn_keywords:
                if keyword in title:
                    warnings.append(f"{keyword}: {title}")
        hard_blocks = hard_blocks[:5]
        warnings = warnings[:5]
        if hard_blocks:
            score = 25
            event_risk = "high"
        elif warnings:
            score = 42
            event_risk = "medium"
        else:
            score = 60
            event_risk = "low"
            signals.append("近期公告未发现硬性利空关键词")
        return {
            "announcement_score": score,
            "event_risk": event_risk,
            "signals": signals,
            "warnings": warnings,
            "hard_blocks": hard_blocks,
            "confidence": 0.65,
            "filtered_count": len(filtered_announcements),
        }

    def _recent_unique(self, announcements: List[Dict[str, Any]], days: int = 365) -> List[Dict[str, Any]]:
        cutoff = datetime.now() - timedelta(days=days)
        seen = set()
        rows: List[Dict[str, Any]] = []
        for item in announcements:
            title = item.get("title", "")
            if not title:
                continue
            publish_time = item.get("publish_time") or item.get("date") or item.get("公告日期") or ""
            parsed = self._parse_date(str(publish_time))
            if parsed and parsed < cutoff:
                continue
            key = (title, parsed.date().isoformat() if parsed else "")
            if key in seen:
                continue
            seen.add(key)
            rows.append(item)
        return rows

    def _parse_date(self, value: str) -> datetime | None:
        if not value:
            return None
        text = value[:10]
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None
