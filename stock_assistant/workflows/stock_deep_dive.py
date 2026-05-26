from __future__ import annotations

from typing import Any, Dict, List

from stock_assistant.analyzers.announcement import AnnouncementAnalyzer
from stock_assistant.analyzers.capital_flow import CapitalFlowAnalyzer
from stock_assistant.analyzers.fundamental import FundamentalAnalyzer
from stock_assistant.analyzers.industry_chain import IndustryChainAnalyzer
from stock_assistant.analyzers.market_regime import MarketRegimeAnalyzer
from stock_assistant.analyzers.risk import RiskAnalyzer
from stock_assistant.analyzers.sector_rotation import SectorRotationAnalyzer
from stock_assistant.analyzers.technical import TechnicalAnalyzer
from stock_assistant.analyzers.valuation import ValuationAnalyzer
from stock_assistant.config_loader import load_risk_rules
from stock_assistant.data_gateway import AStockDataGateway
from stock_assistant.decision.decision_engine import DecisionEngine
from stock_assistant.models import AnalysisResult
from stock_assistant.workflows.deep_dive import DeepDiveEnhancer


class StockDeepDiveWorkflow:
    def __init__(self, gateway: AStockDataGateway | None = None) -> None:
        self.gateway = gateway or AStockDataGateway()
        self.rules = load_risk_rules()
        self.technical = TechnicalAnalyzer()
        self.chain = IndustryChainAnalyzer()
        self.risk = RiskAnalyzer()
        self.decision = DecisionEngine()
        self.fundamental = FundamentalAnalyzer(self.rules.get("fundamental_rules", {}))
        self.valuation = ValuationAnalyzer(self.rules.get("valuation_rules", {}))
        self.announcement = AnnouncementAnalyzer(self.rules.get("announcement_rules", {}))
        self.capital_flow = CapitalFlowAnalyzer()
        self.deep_dive = DeepDiveEnhancer()

    def analyze(self, symbol: str, mode: str = "standard") -> AnalysisResult:
        if mode not in {"quick", "standard", "deep"}:
            raise ValueError("mode must be quick, standard, or deep")
        quote = self.gateway.get_realtime_quote(symbol)
        basic = self.gateway.get_stock_basic(symbol)
        bars = self.gateway.get_daily_bars(symbol)
        technical = self.technical.analyze(bars)
        market = MarketRegimeAnalyzer(self.gateway).analyze()
        sector = SectorRotationAnalyzer(self.gateway).analyze_for_stock(basic.get("industry", ""))
        chain = self.chain.analyze_company_position(basic, mode=mode)
        valuation = self.gateway.get_stock_valuation(symbol) if mode != "quick" else {}
        financial = self.gateway.get_financial_snapshot(symbol) if mode != "quick" else {}
        announcements = self.gateway.get_announcements(symbol) if mode != "quick" else []
        news = self.gateway.get_news(symbol) if mode != "quick" else []
        capital_flow = self.gateway.get_capital_flow(symbol) if mode != "quick" else None
        fundamental_analysis = self.fundamental.analyze(financial) if mode != "quick" else {}
        valuation_analysis = self.valuation.analyze(valuation) if mode != "quick" else {}
        announcement_analysis = self.announcement.analyze(announcements) if mode != "quick" else {}
        capital_flow_analysis = self.capital_flow.analyze(capital_flow) if mode != "quick" else {}
        risk = self.risk.analyze(
            quote,
            technical,
            chain,
            fundamental_analysis,
            valuation_analysis,
            capital_flow_analysis,
            announcement_analysis,
        )
        decision = self.decision.decide(
            technical,
            market,
            sector,
            chain,
            risk,
            fundamental_analysis,
            valuation_analysis,
            capital_flow_analysis,
            announcement_analysis,
        )
        deep_analysis = self.deep_dive.analyze(quote["symbol"], chain) if mode == "deep" else {}
        missing_data = self._collect_missing([quote, basic, valuation, financial, *announcements, *news])
        evidence = {
            "quote": quote,
            "basic": basic,
            "technical": technical,
            "market": market,
            "sector": sector,
            "chain": chain,
            "valuation": valuation,
            "financial": financial,
            "announcements": announcements,
            "news": news,
            "capital_flow": capital_flow.to_dict("records") if capital_flow is not None else [],
            "fundamental_analysis": fundamental_analysis,
            "valuation_analysis": valuation_analysis,
            "announcement_analysis": announcement_analysis,
            "capital_flow_analysis": capital_flow_analysis,
            "deep_analysis": deep_analysis,
            "risk": risk,
            "decision": decision,
        }
        if capital_flow is not None:
            missing_data.extend(capital_flow.attrs.get("missing_data", []))
        markdown = self._render_markdown(evidence, mode, missing_data)
        return AnalysisResult(
            symbol=quote["symbol"],
            name=quote["name"],
            mode=mode,
            markdown=markdown,
            evidence=evidence,
            missing_data=missing_data,
        )

    def _collect_missing(self, payloads: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        missing: List[Dict[str, str]] = []
        for payload in payloads:
            missing.extend(payload.get("missing_data", []) or [])
        return missing

    def _render_markdown(self, evidence: Dict[str, Any], mode: str, missing_data: List[Dict[str, str]]) -> str:
        quote = evidence["quote"]
        technical = evidence["technical"]
        market = evidence["market"]
        sector = evidence["sector"]
        chain = evidence["chain"]
        risk = evidence["risk"]
        decision = evidence["decision"]
        title = "个股快速分析" if mode == "quick" else "个股综合分析"
        support = "、".join(str(x) for x in technical["support_levels"]) or "待补齐"
        resistance = "、".join(str(x) for x in technical["resistance_levels"]) or "待补齐"
        risk_lines = "\n".join(f"- {item}" for item in risk["warnings"])
        invalid_lines = "\n".join(f"{idx}. {item}" for idx, item in enumerate(decision["invalid_conditions"], start=1))
        if missing_data:
            missing_lines = "\n".join(f"- {item['field']}：{item['reason']}" for item in missing_data)
        elif quote.get("source", "").startswith("a-stock-data"):
            missing_lines = f"- 已启用真实数据源：{quote['source']}；仍需注意不同数据源可能存在延迟或字段缺口"
        else:
            missing_lines = "- 当前 MVP 使用部分样例/缓存数据，需接入实时 a-stock-data 后提升置信度"
        standard_extra = ""
        if mode != "quick":
            valuation = evidence["valuation"]
            financial = evidence["financial"]
            fundamental_analysis = evidence["fundamental_analysis"]
            valuation_analysis = evidence["valuation_analysis"]
            announcement_analysis = evidence["announcement_analysis"]
            capital_flow_analysis = evidence["capital_flow_analysis"]
            announcements = evidence["announcements"]
            news = evidence["news"]
            capital = evidence["capital_flow"]
            standard_extra = f"""
## 基本面与估值

- 财务摘要：营收同比 {financial.get('revenue_yoy', '未知')}%，净利润同比 {financial.get('net_profit_yoy', '未知')}%，ROE {financial.get('roe', '未知')}%
- 基本面评分：{fundamental_analysis.get('fundamental_score', '未知')}/100，{fundamental_analysis.get('quality', '未知')}
- 估值评分：{valuation_analysis.get('valuation_score', '未知')}/100，{valuation_analysis.get('valuation_level', valuation.get('valuation_level', '未知'))}
- 估值状态：PE TTM {valuation.get('pe_ttm', '未知')}，PB {valuation.get('pb', '未知')}

## 公告新闻与资金流

- 公告：{announcements[0]['title'] if announcements else '近期公告缺失，事件风险未知'}
- 公告风险：{announcement_analysis.get('event_risk', 'unknown')}，公告评分 {announcement_analysis.get('announcement_score', '未知')}/100
- 新闻：{news[0]['title'] if news else '新闻数据缺失，舆情判断中性'}
- 资金流：{capital[0]['main_net_inflow'] if capital else '缺失'}，{capital_flow_analysis.get('trend', '资金流数据缺失')}
- 资金流评分：{capital_flow_analysis.get('capital_flow_score', '未知')}/100
"""
        deep_extra = self._render_deep_extra(evidence["deep_analysis"]) if mode == "deep" else ""
        return f"""# {title}：{quote['name']}（{quote['symbol']}）

> 研究辅助，不构成投资建议；不自动下单，不承诺收益。

## 核心结论

当前建议：{decision['conclusion']}  
综合评分：{decision['overall_score']}/100  
风险等级：{risk['risk_level']}  
仓位建议：{decision['position']['text']}

## 大盘与板块

- 大盘状态：{market['regime']}。{market['summary']}
- 板块状态：{sector['sector_status']}
- 强势板块：{'、'.join(sector['strong_sectors'])}

## 产业链定位

- 产业链定位：{chain['chain']} / {chain['segment']}
- 受益类型：{chain['benefit_type']}
- 判断：{chain['summary']}

## 技术状态

- 技术状态：{technical['trend']}，技术评分 {technical['technical_score']}/100
- 支撑位：{support}
- 压力位：{resistance}
- 止损参考：{technical['stop_loss_reference']}
- 信号：{'；'.join(technical['signals']) or '暂无明确信号'}
{standard_extra}
{deep_extra}
## 风险提示

{risk_lines}

## 交易计划

- 激进：只有放量突破压力位且板块未退潮时，才考虑小仓位试错
- 稳健：等待回踩支撑不破，再观察是否符合计划
- 仓位：{decision['position']['text']}
- 止损参考：{technical['stop_loss_reference']}

## 反向失效条件

{invalid_lines}

## 数据限制

{missing_lines}
"""

    def _render_deep_extra(self, deep: Dict[str, Any]) -> str:
        if not deep:
            return ""
        segments = "\n".join(
            f"- {item['layer']} / {item['segment']}：{item['description'] or '等待补充'}"
            for item in deep.get("chain_segments", [])
        ) or "- 产业链环节待补充"
        peers = "\n".join(
            f"- {'[当前标的] ' if item.get('is_target') else ''}{item.get('name')}（{item.get('symbol')}）：{item.get('segment')}，{item.get('benefit_type')}，置信度 {item.get('confidence')}"
            for item in deep.get("peer_companies", [])
        ) or "- 同链公司待补充"
        evidence = "\n".join(
            f"- {item.get('source', 'local')}：{item.get('text', '')}"
            for item in deep.get("target_evidence", [])
        ) or "- 暂无可追溯证据"
        metrics = "\n".join(f"- {item}" for item in deep.get("tracking_metrics", []))
        scenarios = "\n".join(f"- {item}" for item in deep.get("risk_scenarios", []))
        return f"""
## 深度产业链比较

### 上中下游拆解

{segments}

### 同链公司横向比较

{peers}

### 证据链

{evidence}

### 后续跟踪指标

{metrics}

### 风险情景

{scenarios}
"""
