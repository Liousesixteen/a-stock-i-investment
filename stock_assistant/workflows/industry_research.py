from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from stock_assistant.config_loader import load_yaml


class IndustryResearchWorkflow:
    def __init__(self, config_path: str | Path = "config/industry_chains.yaml") -> None:
        self.config_path = Path(config_path)

    def render(self, query: str) -> str:
        data = load_yaml(self.config_path, {"industries": {}})
        industry = self._find_industry(data.get("industries", {}), query)
        name = industry.get("name", query)
        return f"""# 产业链研究：{name}

## 上游

{self._render_segments(industry.get('upstream', []))}

## 中游

{self._render_segments(industry.get('midstream', []))}

## 下游

{self._render_segments(industry.get('downstream', []))}

## 核心受益公司

{self._render_companies(industry)}

## 真受益 vs 蹭概念

优先看主营收入、订单公告、客户验证和资金持续性。只有概念标签但缺少业务和财务验证的标的，按蹭概念风险处理。

## 后续跟踪指标

- 板块涨跌幅和成交额是否持续强于市场
- 核心公司公告、订单、业绩是否兑现
- 同产业链是否扩散到更多环节

## 风险提示

{self._render_risks(industry.get('risks', []))}
"""

    def _find_industry(self, industries: Dict[str, Any], query: str) -> Dict[str, Any]:
        for item in industries.values():
            if item.get("name") == query or query in item.get("aliases", []):
                return item
        return {"name": query, "upstream": [], "midstream": [], "downstream": [], "risks": ["本地产业链知识库尚未覆盖该主题"]}

    def _render_segments(self, segments: List[Dict[str, Any]]) -> str:
        if not segments:
            return "- 暂无配置"
        return "\n".join(f"- {item.get('segment', '未知环节')}：{item.get('description', '等待补充')}" for item in segments)

    def _render_companies(self, industry: Dict[str, Any]) -> str:
        companies = []
        for section in ["upstream", "midstream", "downstream"]:
            for segment in industry.get(section, []):
                for company in segment.get("companies", []):
                    companies.append(
                        f"- {company.get('name', '')}（{company.get('symbol', '')}）：{company.get('role', '')}，{company.get('benefit_type', '')}"
                    )
        return "\n".join(companies) if companies else "- 暂无核心公司配置"

    def _render_risks(self, risks: List[str]) -> str:
        return "\n".join(f"- {risk}" for risk in risks) if risks else "- 估值过高、订单不及预期、题材退潮"
