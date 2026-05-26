---
name: a-stock-investment
description: A 股投资研究与决策辅助 Skill。Use this whenever the user asks about A 股市场、指数/大盘、明日走势、盘前盘后复盘、个股分析、持仓诊断、买卖计划、仓位控制、板块题材、产业链、公告新闻研报、龙虎榜、北向资金、资金流、数据源健康、知识库/知识图谱，or describes an A-share investment situation implicitly in a long paragraph. Trigger on semantic intent, stock codes, Chinese stock names, market context, portfolio/risk questions, and phrases like “怎么看/要不要/还能不能/风险/机会/复盘/明天”.
---

# A 股投资分析决策助手

This skill turns natural-language A 股 research requests into calls to the local `stock-assistant` CLI. On first use, bootstrap the CLI automatically if it is not available.

## First-use Bootstrap

Before running an analysis command, locate the CLI in this order:

1. If `/Users/ccdemac/DevProjs/a-stock-investment/.venv/bin/stock-assistant` exists, use it.
2. If `$HOME/.a-stock-investment/.venv/bin/stock-assistant` exists, use it.
3. If `stock-assistant` exists on `PATH`, use it.
4. Otherwise run this skill's bundled setup script from the skill directory:

```bash
bash scripts/bootstrap.sh
```

The bootstrap script clones/uses the project, creates `.venv`, installs dependencies with `pip install -e .`, and verifies `stock-assistant --help`.

After bootstrap, prefer the printed `CLI=...` path for all commands.

## Intent Routing

Do not require exact trigger words. Infer the task from the user's intent, symbols, Chinese stock names, market context, holdings, risk language, or time references.

- Broad market, “今天盘面”, “明天怎么看”, index走势, 盘后复盘: run `close-review --live`.
- 盘前计划, 今日策略, 交易纪律: run `morning --live`.
- Single stock code or stock name, 持仓诊断, 要不要买/卖/减仓: run `analyze SYMBOL --mode standard --live`.
- 深度研究, 产业链, 研报/公告/知识图谱: run `analyze SYMBOL --mode deep --live`, and consider `knowledge ingest`.
- Sector/theme questions such as AI算力、机器人、半导体、医药: run `industry QUERY`.
- Portfolio/risk exposure: run `portfolio review`.
- Trade journaling or复盘: use `trade add`, `trade list`, or `trade review`.
- Data reliability, freshness, fallback, or source failures: run `data report SYMBOL --profile quick` first, then `data health` when needed.
- Knowledge base updates: run `knowledge ingest SYMBOL --source news|announcements|research --live`.

If the user asks a broad question without a symbol, start with market context. If a stock name is present but no code is obvious, first resolve or ask a concise clarification only when local context cannot identify it safely.

## Output Contract

Always make the answer useful for investment research, not automatic trading:

- State the conclusion, confidence, and key evidence.
- Separate facts, inferred views, and missing data.
- Include risk controls: position sizing, invalidation condition, stop-loss/reference level when appropriate.
- Mention data-source limitations, stale fields, or fallback usage.
- Do not promise returns or present the output as personal financial advice.

## Common Commands

```bash
$CLI close-review --live
$CLI morning --live
$CLI analyze 002415 --mode standard --live
$CLI analyze 002415 --mode deep --live
$CLI industry AI算力
$CLI data report 002415 --profile quick
$CLI knowledge ingest 603019 --source news --live
```
