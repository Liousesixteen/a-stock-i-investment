from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from stock_assistant.config_loader import load_yaml


class PortfolioReviewWorkflow:
    def __init__(self, watchlist_path: str | Path = "config/watchlist.yaml") -> None:
        self.watchlist_path = Path(watchlist_path)

    def render(self) -> str:
        data = load_yaml(self.watchlist_path, {"positions": [], "watchlists": {}})
        positions: List[Dict[str, Any]] = data.get("positions", []) or []
        total_pct = sum(float(item.get("position_pct", 0) or 0) for item in positions)
        sectors = self._group_pct(positions, "industry")
        chains = self._group_pct(positions, "chain")
        return f"""# 组合风险诊断

## 总仓位建议

当前配置持仓仓位约 {total_pct:.1f}%。若大盘和板块不共振，总仓位建议控制在 50%-60% 以下；单票必须遵守风险等级上限。

## 行业集中度

{self._render_group(sectors)}

## 产业链集中度

{self._render_group(chains)}

## 单票风险

{self._render_positions(positions)}

## 调仓建议

避免多个持仓集中在同一题材退潮方向；若无明确计划和止损，不新增仓位。
"""

    def _group_pct(self, positions: List[Dict[str, Any]], key: str) -> Dict[str, float]:
        grouped: Dict[str, float] = {}
        for item in positions:
            name = item.get(key) or "未分类"
            grouped[name] = grouped.get(name, 0.0) + float(item.get("position_pct", 0) or 0)
        return grouped

    def _render_group(self, grouped: Dict[str, float]) -> str:
        if not grouped:
            return "- 暂无持仓，集中度风险低"
        return "\n".join(f"- {name}：{pct:.1f}%" for name, pct in sorted(grouped.items(), key=lambda x: x[1], reverse=True))

    def _render_positions(self, positions: List[Dict[str, Any]]) -> str:
        if not positions:
            return "- 暂无持仓"
        return "\n".join(
            f"- {item.get('name', item.get('symbol'))}（{item.get('symbol')}）：{item.get('position_pct', 0)}%，止损 {item.get('stop_loss', '未设置')}"
            for item in positions
        )
