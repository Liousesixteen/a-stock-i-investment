from __future__ import annotations

from typing import Optional

import typer

from stock_assistant.cache import JsonCache
from stock_assistant.data_gateway import AStockDataGateway
from stock_assistant.storage.journal_store import JournalStore
from stock_assistant.workflows.industry_research import IndustryResearchWorkflow
from stock_assistant.workflows.market_sentiment import MarketSentimentWorkflow
from stock_assistant.workflows.morning_brief import MorningBriefWorkflow
from stock_assistant.workflows.portfolio_review import PortfolioReviewWorkflow
from stock_assistant.workflows.stock_deep_dive import StockDeepDiveWorkflow
from stock_assistant.workflows.trade_review import TradeReviewWorkflow

app = typer.Typer(help="A股投资分析决策助手")
cache_app = typer.Typer(help="缓存命令")
data_app = typer.Typer(help="数据源诊断命令")
portfolio_app = typer.Typer(help="组合风险命令")
trade_app = typer.Typer(help="交易日志与复盘命令")
knowledge_app = typer.Typer(help="动态知识库命令")
app.add_typer(cache_app, name="cache")
app.add_typer(data_app, name="data")
app.add_typer(portfolio_app, name="portfolio")
app.add_typer(trade_app, name="trade")
app.add_typer(knowledge_app, name="knowledge")


def get_data_health_checker():
    from stock_assistant.data_health import DataHealthChecker

    return DataHealthChecker()


def build_data_health_checker(provider_name: str):
    from stock_assistant.data_health import DataHealthChecker
    from stock_assistant.data_sources.adapters import AkShareAdapter, AStockDataAdapter

    provider = AkShareAdapter() if provider_name == "akshare" else AStockDataAdapter()
    checker_cls = globals().get("DataHealthChecker", DataHealthChecker)
    return checker_cls(provider=provider)


@app.command()
def analyze(
    symbol: str,
    mode: str = typer.Option("standard", "--mode", "-m", help="quick / standard / deep"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="保存 Markdown 报告"),
    live: bool = typer.Option(False, "--live", help="启用 a-stock-data 真实 HTTP 数据，失败时自动降级"),
) -> None:
    result = StockDeepDiveWorkflow(gateway=AStockDataGateway(use_live=live)).analyze(symbol, mode=mode)
    if output:
        from pathlib import Path

        Path(output).write_text(result.markdown, encoding="utf-8")
    typer.echo(result.markdown)


@app.command()
def morning(live: bool = typer.Option(False, "--live", help="启用真实数据源生成盘前简报")) -> None:
    typer.echo(MorningBriefWorkflow(gateway=AStockDataGateway(use_live=live)).render())


@app.command("close-review")
def close_review(live: bool = typer.Option(False, "--live", help="启用真实数据源生成盘后复盘")) -> None:
    typer.echo(MorningBriefWorkflow(gateway=AStockDataGateway(use_live=live)).close_review())


@app.command()
def sentiment(live: bool = typer.Option(False, "--live", help="启用真实数据源生成市场情绪与消息面雷达")) -> None:
    typer.echo(MarketSentimentWorkflow(gateway=AStockDataGateway(use_live=live)).render())


@app.command()
def industry(query: str, deep: bool = typer.Option(False, "--deep", help="保留参数，后续用于深度产业链研究")) -> None:
    typer.echo(IndustryResearchWorkflow().render(query))


@cache_app.command("refresh-market")
def refresh_market() -> None:
    message = MorningBriefWorkflow(gateway=AStockDataGateway(use_live=False)).refresh_market_cache()
    typer.echo(message)


@data_app.command("health")
def data_health(
    symbol: str = typer.Argument("002415", help="用于探测数据源的股票代码"),
    provider: str = typer.Option("astock", "--provider", help="astock 或 akshare"),
    profile: str = typer.Option("quick", "--profile", help="quick 或 full；quick 避开批量重接口"),
    checks: Optional[str] = typer.Option(None, "--checks", help="逗号分隔的端点名，优先级高于 profile"),
) -> None:
    from stock_assistant.data_health import PROFILE_CHECKS

    checker = build_data_health_checker(provider)
    selected_checks = [item.strip() for item in checks.split(",") if item.strip()] if checks else PROFILE_CHECKS.get(profile, PROFILE_CHECKS["quick"])
    typer.echo(checker.to_markdown(checker.check(symbol, checks=selected_checks)))


@data_app.command("report")
def data_report(
    symbol: str = typer.Argument("002415", help="用于生成状态报告的股票代码"),
    provider: str = typer.Option("astock", "--provider", help="astock 或 akshare"),
    profile: str = typer.Option("quick", "--profile", help="quick 或 full"),
) -> None:
    from stock_assistant.data_health import PROFILE_CHECKS

    checker = build_data_health_checker(provider)
    checks = PROFILE_CHECKS.get(profile, PROFILE_CHECKS["quick"])
    result = checker.check(symbol, checks=checks)
    cache = JsonCache()
    lines = [
        f"# 数据源状态报告：{symbol}",
        "",
        "## 健康摘要",
        "",
        f"- ok：{result['summary'].get('ok', 0)}",
        f"- fail：{result['summary'].get('fail', 0)}",
        f"- unsupported：{result['summary'].get('unsupported', 0)}",
        f"- unavailable：{result['summary'].get('unavailable', 0)}",
        "",
        "## 失败接口",
        "",
    ]
    failures = [(name, item) for name, item in result["checks"].items() if item["status"] != "ok"]
    if not failures:
        lines.append("- 暂无失败接口")
    for name, item in failures:
        lines.append(f"- {name}：{item['status']}，{item.get('message', '')}")
    lines.extend(["", "## 缓存状态", ""])
    cache_rows = sorted(cache.root.glob("*.json"))
    if not cache_rows:
        lines.append("- 暂无缓存")
    for path in cache_rows:
        payload = cache.read(path.name)
        if not payload:
            continue
        lines.append(
            f"- {path.stem}：source={payload.get('source', '')} generated_at={payload.get('generated_at', '')} ttl={payload.get('ttl_seconds', '')}"
        )
    typer.echo("\n".join(lines))


@portfolio_app.command("review")
def portfolio_review() -> None:
    typer.echo(PortfolioReviewWorkflow().render())


@trade_app.command("add")
def trade_add(
    symbol: str = typer.Option(..., "--symbol"),
    action: str = typer.Option(..., "--action"),
    price: float = typer.Option(..., "--price"),
    quantity: int = typer.Option(..., "--quantity"),
    reason: str = typer.Option("", "--reason"),
) -> None:
    trade_id = JournalStore().add_trade(symbol=symbol, action=action, price=price, quantity=quantity, reason=reason)
    typer.echo(f"trade recorded: #{trade_id}")


@trade_app.command("list")
def trade_list() -> None:
    typer.echo(TradeReviewWorkflow().render_list())


@trade_app.command("review")
def trade_review() -> None:
    typer.echo(TradeReviewWorkflow().render_review())


def get_evidence_store():
    from stock_assistant.knowledge.evidence_store import EvidenceStore

    return EvidenceStore()


@knowledge_app.command("ingest")
def knowledge_ingest(
    symbol: str,
    source: str = typer.Option("news", "--source", help="news / announcements / research"),
    live: bool = typer.Option(False, "--live", help="启用真实数据源采集证据"),
) -> None:
    from stock_assistant.knowledge.enrichment import KnowledgeEnricher

    result = KnowledgeEnricher(store=get_evidence_store(), gateway=AStockDataGateway(use_live=live)).ingest_symbol(symbol, source)
    typer.echo(f"ingested evidence={result['evidence_count']} candidates={result['candidate_count']}")


@knowledge_app.command("candidates")
def knowledge_candidates(status: str = typer.Option("pending", "--status", help="pending/observed/verified/rejected")) -> None:
    rows = get_evidence_store().list_candidates(status=None if status == "all" else status)
    lines = ["# 候选知识", ""]
    if not rows:
        lines.append("暂无候选知识")
    for row in rows:
        lines.append(
            f"- {row.get('id')} {row.get('symbol')} {row.get('chain')} / {row.get('segment')} "
            f"status={row.get('status')} confidence={row.get('confidence')}"
        )
    typer.echo("\n".join(lines))


@knowledge_app.command("promote")
def knowledge_promote(candidate_id: str) -> None:
    row = get_evidence_store().update_candidate_status(candidate_id, "verified")
    typer.echo(f"promoted {row['id']} to verified")


@knowledge_app.command("reject")
def knowledge_reject(candidate_id: str) -> None:
    row = get_evidence_store().update_candidate_status(candidate_id, "rejected")
    typer.echo(f"rejected {row['id']}")


if __name__ == "__main__":
    app()
