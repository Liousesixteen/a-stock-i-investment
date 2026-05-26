# OpenClaw A 股投资分析决策 Skill 套件优化版开发文档

## 0. 文档定位

本文档是对前一版开发文档的重构版。

前一版文档是边讨论边追加，后半部分出现了：

- Skill 数量过多。
- 插件拆分策略后置。
- 产业链模块后置。
- 性能优化后置。
- `a-stock-data` 集成方案不够前置。

本版文档重新按工程逻辑组织，作为后续 Codex / Claude Code / OpenClaw 开发的主文档。

---

# 1. 项目总定位

## 1.1 项目名称

推荐名称：

```text
openclaw-a-stock-investment
```

或：

```text
a-stock-investment
```

## 1.2 项目一句话定位

> `a-stock-investment` 是一个基于现有 `a-stock-data` （/Users/ccdemac/.openclaw/workspace-finance/skills/a-stock-data）的 A 股投资研究、产业链分析、交易计划、风险控制与复盘 Skill 套件。它对外暴露少量任务型 Skill，对内保留完整分析引擎；个股分析默认包含产业链定位，并通过 quick / standard / deep 三档模式控制耗时与深度，目标是帮助用户把每天炒股流程标准化、结构化、可复盘，而不是预测确定性涨跌。

## 1.3 项目边界

本项目做：

```text
大盘环境分析
板块轮动分析
产业链分析
个股综合分析
技术面分析
基本面分析
估值分析
公告新闻分析
资金流分析
风险控制
仓位管理
交易计划生成
盘前简报
盘中监控
盘后复盘
组合风险诊断
交易日志与复盘
报告生成
```

本项目不做：

```text
不重新开发完整数据源
不自动下单
不承诺收益
不输出确定性涨跌预测
不鼓励满仓、融资、借钱炒股
不替用户做最终投资决定
```

## 1.4 与 a-stock-data 的关系

现有 `a-stock-data` 作为数据底座保留。

```text
a-stock-data
负责：行情、K线、财务、公告、新闻、研报、资金流、板块、概念等数据获取

a-stock-investment
负责：分析、评分、风控、仓位、决策、复盘、报告生成
```

最终关系：

```text
OpenClaw / Claude Code / Codex
        ↓
a-stock-investment
        ↓
AStockDataGateway
        ↓
a-stock-data
        ↓
原始数据源
```

## 1.5 安全与权限边界

本项目必须默认处于“研究辅助”和“决策辅助”模式，不允许自动执行真实交易。

安全边界：

```text
1. 不自动下单。
2. 不连接券商交易接口作为第一版目标。
3. 不保存用户券商账号、密码、交易验证码、Token 等敏感信息。
4. 不读取与项目无关的本地文件。
5. 不把用户交易日志、持仓信息上传到未知外部服务。
6. 不鼓励融资、配资、借钱炒股。
7. 所有真实交易动作必须由用户自行确认并手动执行。
8. 若未来接入交易接口，必须先做只读模式和模拟交易模式。
9. 若未来支持真实交易，必须加入二次确认、交易限额、日志审计和紧急停止机制。
```

输出边界：

```text
可以输出：分析结论、风险提示、仓位建议、交易计划、止损参考、反向失效条件。
不可以输出：保证收益、确定性涨跌、满仓建议、无风险承诺、诱导高频交易。
```

---

# 2. 插件架构设计

## 2.1 不建议把 a-stock-data 和 a-stock-investment 合并

不建议一开始把 `a-stock-data` 和 `a-stock-investment` 合成一个大插件。

原因：

```text
1. 数据层和分析层变化频率不同。
2. 数据源接口经常失效，分析逻辑经常迭代，两者耦合会增加维护难度。
3. 分开后更容易定位问题。
4. 后续可以扩展港股、美股、ETF、基金、可转债等数据层。
5. a-stock-data 已经相对完整，重复开发数据源浪费时间。
```

## 2.2 推荐三层架构

长期推荐结构：

```text
a-stock-data
        ↓
a-stock-investment
        ↓
openclaw-finagent
```

三层职责：

| 层级 | 名称 | 职责 |
|---|---|---|
| 数据层 | `a-stock-data` | 获取行情、财务、公告、新闻、研报、资金流等数据 |
| 分析层 | `a-stock-investment` | 研究、分析、评分、风控、仓位、复盘 |
| 总入口层 | `openclaw-finagent` | 统一路由、组合调用、用户体验封装 |

## 2.3 当前阶段推荐方案

当前不要做 `openclaw-finagent`，先做：

```text
保留 a-stock-data
新建 a-stock-investment
通过 AStockDataGateway 兼容 a-stock-data
```

后续稳定后，再做总入口：

```text
openclaw-finagent
```

---

# 3. Skill 粒度优化设计

## 3.1 不采用“很多小 Skill”方案

不推荐对外暴露这些细粒度 Skill：

```text
a-stock-market-regime
a-stock-sector-rotation
a-stock-technical-analysis
a-stock-fundamental-analysis
a-stock-valuation-analysis
a-stock-announcement-analysis
a-stock-news-sentiment
a-stock-capital-flow
a-stock-risk-control
a-stock-position-management
a-stock-decision-engine
```

这些能力都需要，但不适合全部作为 OpenClaw 对外 Skill。

原因：

```text
1. 用户不会按这些底层模块提问。
2. OpenClaw 路由会混乱。
3. 每个 Skill 都要维护 SKILL.md，重复内容多。
4. 功能越拆越细，用户体验反而变差。
5. 底层模块应该由高层工作流统一调度。
```

## 3.2 采用“5 个对外任务型 Skill + 内部模块”方案

对外只暴露 5 个高层 Skill：

```text
1. a-stock-daily-workflow
2. a-stock-stock-analysis
3. a-stock-industry-research
4. a-stock-portfolio-risk
5. a-stock-trade-review
```

内部保留完整分析模块：

```text
market_regime.py
sector_rotation.py
industry_chain.py
technical.py
fundamental.py
valuation.py
announcement.py
news_sentiment.py
capital_flow.py
risk.py
decision_engine.py
position_sizer.py
trade_plan.py
```

## 3.3 五个对外 Skill 的职责

### 3.3.1 a-stock-daily-workflow

负责每日交易流程。

覆盖：

```text
盘前简报
盘中监控
盘后复盘
周度计划
自选股扫描
```

用户问题：

```text
生成今天的盘前计划。
今天 A 股怎么看？
帮我做盘后复盘。
扫描一下我的自选股。
生成本周交易计划。
```

### 3.3.2 a-stock-stock-analysis

负责单只股票综合分析。

覆盖：

```text
个股综合分析
持仓诊断
买卖计划
技术面
基本面
估值
公告新闻
资金流
产业链位置
风险控制
仓位建议
```

用户问题：

```text
帮我分析一下 002415 能不能买。
这只股票要不要卖？
我的 300750 还能拿吗？
给我一个交易计划。
```

### 3.3.3 a-stock-industry-research

负责行业、板块、产业链研究。

覆盖：

```text
板块轮动
产业链分析
主题研究
上下游拆解
核心受益公司
真受益 vs 蹭概念
行业观察股票池
```

用户问题：

```text
分析 AI 算力产业链。
半导体产业链有哪些核心股票？
机器人板块谁最受益？
这个概念是真逻辑还是炒作？
```

### 3.3.4 a-stock-portfolio-risk

负责组合风险诊断。

覆盖：

```text
持仓组合诊断
行业集中度
产业链集中度
单票仓位风险
总仓位建议
组合回撤风险
调仓建议
```

用户问题：

```text
帮我看看我的持仓风险。
我的组合是不是太集中？
现在总仓位应该多少？
这些股票是不是一个方向？
```

### 3.3.5 a-stock-trade-review

负责交易日志和复盘。

覆盖：

```text
交易日志
单笔交易复盘
周度交易复盘
胜率统计
盈亏比统计
错误标签
交易纪律检查
```

用户问题：

```text
记录一笔交易。
帮我复盘今天的交易。
我最近交易有什么问题？
统计一下我的胜率和盈亏比。
```

---

# 4. 推荐项目目录结构

```text
openclaw-a-stock-investment/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
│
├── config/
│   ├── user_profile.yaml
│   ├── watchlist.yaml
│   ├── risk_rules.yaml
│   ├── strategy_profiles.yaml
│   ├── industry_chains.yaml
│   ├── company_tags.yaml
│   ├── supply_chain_relations.yaml
│   └── output_templates.yaml
│
├── skills/
│   ├── a-stock-daily-workflow/
│   │   └── SKILL.md
│   ├── a-stock-stock-analysis/
│   │   └── SKILL.md
│   ├── a-stock-industry-research/
│   │   └── SKILL.md
│   ├── a-stock-portfolio-risk/
│   │   └── SKILL.md
│   └── a-stock-trade-review/
│       └── SKILL.md
│
├── stock_assistant/
│   ├── __init__.py
│   ├── cli.py
│   ├── config_loader.py
│   ├── data_gateway.py
│   ├── cache.py
│   ├── models.py
│   ├── utils.py
│   │
│   ├── analyzers/
│   │   ├── __init__.py
│   │   ├── market_regime.py
│   │   ├── sector_rotation.py
│   │   ├── industry_chain.py
│   │   ├── technical.py
│   │   ├── fundamental.py
│   │   ├── valuation.py
│   │   ├── announcement.py
│   │   ├── news_sentiment.py
│   │   ├── capital_flow.py
│   │   └── risk.py
│   │
│   ├── decision/
│   │   ├── __init__.py
│   │   ├── scoring.py
│   │   ├── decision_engine.py
│   │   ├── position_sizer.py
│   │   └── trade_plan.py
│   │
│   ├── workflows/
│   │   ├── __init__.py
│   │   ├── morning_brief.py
│   │   ├── intraday_watch.py
│   │   ├── close_review.py
│   │   ├── stock_deep_dive.py
│   │   ├── industry_chain_deep_dive.py
│   │   ├── portfolio_review.py
│   │   └── weekly_review.py
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── sqlite_store.py
│   │   ├── watchlist_store.py
│   │   ├── journal_store.py
│   │   └── portfolio_store.py
│   │
│   ├── reports/
│   │   ├── __init__.py
│   │   ├── markdown_renderer.py
│   │   └── report_generator.py
│   │
│   └── templates/
│       ├── stock_analysis_quick.md
│       ├── stock_analysis_standard.md
│       ├── stock_analysis_deep.md
│       ├── morning_brief.md
│       ├── close_review.md
│       ├── industry_chain_report.md
│       ├── portfolio_review.md
│       └── trade_review.md
│
├── cache/
│   ├── market_context.json
│   ├── sector_context.json
│   ├── industry_context.json
│   └── stock_snapshots/
│
├── tests/
│   ├── test_data_gateway.py
│   ├── test_technical.py
│   ├── test_market_regime.py
│   ├── test_sector_rotation.py
│   ├── test_industry_chain.py
│   ├── test_fundamental.py
│   ├── test_valuation.py
│   ├── test_announcement.py
│   ├── test_risk.py
│   ├── test_decision_engine.py
│   ├── test_position_sizer.py
│   └── fixtures/
│
└── prompts_for_codex/
    ├── 01_project_bootstrap.md
    ├── 02_astock_data_gateway.md
    ├── 03_context_cache.md
    ├── 04_technical_analyzer.md
    ├── 05_market_sector_analyzers.md
    ├── 06_industry_chain.md
    ├── 07_fundamental_valuation.md
    ├── 08_event_capital_risk.md
    ├── 09_decision_engine.md
    ├── 10_workflows.md
    ├── 11_trade_review.md
    └── 12_skills.md
```

---

# 5. 数据层设计：AStockDataGateway

## 5.1 目标

`AStockDataGateway` 是 `a-stock-investment` 与现有 `a-stock-data` 的唯一连接层。

所有分析器不得直接调用 `a-stock-data` 的端点，也不得直接调用外部数据源。

```text
analyzers / workflows
        ↓
AStockDataGateway
        ↓
a-stock-data
```

## 5.2 设计原则

```text
1. 保留 a-stock-data，不修改其核心逻辑。
2. 通过适配器调用 a-stock-data。
3. 对外输出统一字段。
4. 加入缓存、异常处理和字段校验。
5. 分析器只认识内部标准字段。
```

## 5.3 主要接口

```python
class AStockDataGateway:
    def get_stock_basic(self, symbol: str) -> dict: ...

    def get_realtime_quote(self, symbol: str) -> dict: ...

    def get_daily_bars(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        adjust: str = "qfq",
    ) -> pd.DataFrame: ...

    def get_index_bars(self, index_code: str, start: str | None = None, end: str | None = None) -> pd.DataFrame: ...

    def get_sector_performance(self) -> pd.DataFrame: ...

    def get_concept_performance(self) -> pd.DataFrame: ...

    def get_stock_valuation(self, symbol: str) -> dict: ...

    def get_financial_snapshot(self, symbol: str) -> dict: ...

    def get_financial_statements(self, symbol: str) -> dict: ...

    def get_announcements(self, symbol: str, days: int = 30) -> list[dict]: ...

    def get_news(self, symbol: str, days: int = 7) -> list[dict]: ...

    def get_research_reports(self, symbol: str | None = None, industry: str | None = None) -> list[dict]: ...

    def get_capital_flow(self, symbol: str) -> pd.DataFrame: ...

    def get_northbound_flow(self) -> dict: ...

    def get_dragon_tiger(self, symbol: str, days: int = 30) -> list[dict]: ...

    def get_lockup_calendar(self, symbol: str, days: int = 180) -> list[dict]: ...
```

## 5.4 标准字段

### 5.4.1 日线字段

```text
date
open
high
low
close
volume
amount
turnover_rate
pct_chg
```

### 5.4.2 实时行情字段

```text
symbol
name
price
pct_chg
open
high
low
pre_close
volume
amount
turnover_rate
pe_ttm
pb
market_cap
float_market_cap
limit_up
limit_down
```

### 5.4.3 财务字段

```text
report_date
revenue
revenue_yoy
net_profit
net_profit_yoy
gross_margin
net_margin
roe
debt_ratio
operating_cashflow
free_cashflow
eps
bps
```

### 5.4.4 公告字段

```text
symbol
title
publish_time
url
announcement_type
raw_text
source
```

### 5.4.5 新闻字段

```text
symbol
title
publish_time
source
url
summary
raw_text
```

### 5.4.6 资金流字段

```text
symbol
date
main_net_inflow
super_large_net_inflow
large_net_inflow
medium_net_inflow
small_net_inflow
net_inflow_pct
```

## 5.5 AStockDataGateway 数据适配验收清单

`AStockDataGateway` 的第一目标不是“拿到所有数据”，而是保证核心数据可用、字段统一、失败可降级。

| 接口 | 必须返回 | 用途 | 缺失时降级方式 |
|---|---|---|---|
| `get_stock_basic` | 股票名称、行业、概念、市场 | 股票识别、产业链匹配 | 使用 symbol 继续分析，行业/产业链置信度降低 |
| `get_realtime_quote` | 当前价、涨跌幅、成交额、换手率 | 实时状态、盘中判断 | 使用最近收盘价代替，标记实时数据缺失 |
| `get_daily_bars` | date、open、high、low、close、volume、amount | 技术分析、支撑压力 | 无法执行技术分析，报告降级 |
| `get_index_bars` | 指数 K 线、成交额 | 大盘环境 | 使用最近缓存的 market_context，标记已过期 |
| `get_sector_performance` | 行业涨跌幅、成交额 | 板块轮动 | 使用缓存 sector_context，若无缓存则板块评分设为中性 |
| `get_concept_performance` | 概念涨跌幅、热度 | 题材判断 | 使用行业粗分类代替 |
| `get_stock_valuation` | PE、PB、市值、估值相关字段 | 估值分析 | valuation_score 设为 50，置信度降低 |
| `get_financial_snapshot` | 营收、利润、ROE、负债率、现金流 | 基本面评分 | fundamental_score 设为 50，报告说明财务数据缺失 |
| `get_financial_statements` | 利润表、资产负债表、现金流量表 | deep 模式财务深挖 | deep 模式降级为 standard 财务摘要 |
| `get_announcements` | 公告标题、时间、链接、正文或摘要 | 公告风险 | 事件风险标记为 unknown，不默认安全 |
| `get_news` | 新闻标题、时间、来源、摘要 | 新闻舆情 | news_score 设为 50，报告说明新闻数据缺失 |
| `get_research_reports` | 研报标题、机构、日期、摘要/PDF | deep 模式产业链验证 | 跳过研报验证，仅用公告和财务证据 |
| `get_capital_flow` | 主力资金、大单、小单、日期 | 资金流评分 | capital_flow_score 设为 50 |
| `get_northbound_flow` | 北向资金净流入/流出 | 市场资金环境 | 不参与评分，仅提示缺失 |
| `get_dragon_tiger` | 龙虎榜席位、买卖金额 | 短线资金识别 | 跳过龙虎榜分析 |
| `get_lockup_calendar` | 解禁时间、规模、比例 | 风险控制 | 解禁风险标记为 unknown |

验收要求：

```text
1. 每个接口都有字段标准化函数。
2. 每个接口都有异常捕获和 missing_data 标记。
3. 每个接口都支持缓存读取。
4. 字段缺失时不得让整个报告崩溃。
5. 数据缺失必须影响 confidence，而不是静默忽略。
```

---

# 6. 性能设计：quick / standard / deep 三档分析模式

## 6.1 为什么需要三档模式

完整个股分析如果每次都实时跑：

```text
行情 + K线 + 财务 + 估值 + 公告 + 新闻 + 资金流 + 大盘 + 板块 + 产业链 + 决策
```

会比较慢。

因此必须分为：

```text
quick：快速分析
standard：标准分析
deep：深度分析
```

## 6.2 quick 快速模式

适用：

```text
简单看一下
盘中快速判断
持仓是否有明显风险
```

调用：

```text
实时行情
K线
技术分析
缓存的大盘状态
缓存的板块状态
本地产业链标签
基础风险检查
```

不调用：

```text
完整财务三表
深度公告解析
研报 PDF
同产业链横向比较
```

输出：

```text
核心结论
技术状态
产业链一句话定位
支撑压力
风险提示
仓位建议
```

## 6.3 standard 标准模式

适用：默认个股分析。

调用：

```text
实时行情
K线
技术指标
大盘环境
板块强度
产业链定位
基本财务指标
估值
最近公告
最近新闻
资金流
风险检查
决策引擎
```

输出：

```text
完整个股综合报告
产业链小节
交易计划
反向失效条件
```

## 6.4 deep 深度模式

适用：

```text
深度分析这只股票
它是不是真受益
和同产业链公司比怎么样
写一份深度研报
```

调用：

```text
完整财务三表
多期财务指标
研报列表
公告深度解析
新闻事件梳理
产业链上下游拆解
同链公司横向比较
估值横向比较
资金流趋势
组合风险影响
```

输出：

```text
深度个股报告
产业链比较
估值比较
业绩兑现验证
风险情景
```

## 6.5 缓存策略

### 6.5.1 每日缓存

```text
大盘环境
板块排名
概念板块
行业强弱
产业链配置
公司基础资料
F10 主营业务
历史财务数据
估值历史
```

### 6.5.2 分钟级缓存

```text
实时行情
资金流
北向资金
盘中板块异动
```

### 6.5.3 事件触发缓存

```text
公告
新闻
研报
解禁
龙虎榜
```

## 6.6 上下文缓存文件

```text
cache/market_context.json
cache/sector_context.json
cache/industry_context.json
cache/stock_snapshots/{symbol}.json
```

## 6.7 分析性能原则

```text
1. 大盘和板块在盘前统一计算，个股分析读取缓存。
2. 产业链结构来自本地配置，个股分析只做匹配。
3. 深度研报、同链对比只在 deep 模式执行。
4. 多源数据并行获取。
5. 缺失数据时降级分析，不中断整个报告。
```

## 6.8 数据缺失与降级分析机制

系统必须允许部分数据缺失，并在报告中明确说明缺失内容和影响。

通用规则：

```text
1. 缺失数据不等于 0 分，默认使用中性分 50。
2. 缺失关键数据会降低 confidence。
3. 风险类数据缺失不能默认安全，只能标记 unknown。
4. quick 模式允许更多缺失，deep 模式必须尽量补全。
5. 降级后仍然要输出可用结论，但必须说明限制。
```

| 缺失数据 | 降级方式 | 对评分影响 | 报告提示 |
|---|---|---|---|
| 实时行情缺失 | 使用最近收盘价 | 实时判断置信度降低 | “实时行情缺失，使用最近收盘数据” |
| K线缺失 | 跳过技术分析 | technical_score = 50 | “K线缺失，无法判断技术趋势” |
| 财务数据缺失 | 跳过基本面评分 | fundamental_score = 50 | “财务数据缺失，基本面判断置信度降低” |
| 估值数据缺失 | 跳过估值分位 | valuation_score = 50 | “估值数据缺失，无法判断贵贱” |
| 公告数据缺失 | 不触发公告风险 | event_risk = unknown | “未获取到近期公告，事件风险未知” |
| 新闻数据缺失 | 新闻舆情中性 | news_score = 50 | “新闻数据缺失，舆情判断中性” |
| 资金流缺失 | 资金评分中性 | capital_flow_score = 50 | “资金流数据缺失，不参与加减分” |
| 产业链匹配缺失 | 使用行业粗分类 | industry_chain_score = 50 | “产业链匹配不足，受益类型未知” |
| 大盘数据缺失 | 使用缓存 | market_score 维持缓存值 | “大盘环境使用缓存数据” |
| 板块数据缺失 | 使用缓存或中性 | sector_score = 50 | “板块数据缺失，板块强度中性处理” |

## 6.9 缓存 TTL 设计

| 缓存对象 | 文件/键名 | 推荐 TTL | 更新方式 |
|---|---|---:|---|
| 大盘环境 | `market_context.json` | 盘前一次；盘中 30 分钟 | `stock-assistant cache refresh-market` |
| 板块轮动 | `sector_context.json` | 15-30 分钟 | 盘中可刷新 |
| 产业链热度 | `industry_context.json` | 每日；深度研究每周 | 盘前或周末刷新 |
| 个股实时行情 | `stock_realtime:{symbol}` | 30-60 秒 | 查询时自动刷新 |
| 个股 K 线 | `daily_bars:{symbol}` | 每日收盘后 | 收盘后刷新 |
| 财务数据 | `financials:{symbol}` | 1 天-1 周 | 财报期可缩短 TTL |
| 估值数据 | `valuation:{symbol}` | 1 天 | 每日刷新 |
| 公告 | `announcements:{symbol}` | 1-3 小时 | 事件触发或盘后刷新 |
| 新闻 | `news:{symbol}` | 15-60 分钟 | 查询时刷新 |
| 研报 | `research_reports:{symbol}` | 1 天 | deep 模式触发刷新 |
| 龙虎榜 | `dragon_tiger:{symbol}` | 1 天 | 收盘后刷新 |
| 解禁日历 | `lockup:{symbol}` | 1 天 | 每日刷新 |

缓存实现要求：

```text
1. 缓存必须记录 generated_at、ttl_seconds、source、is_stale。
2. 过期缓存可以作为降级数据使用，但必须标记 stale。
3. 用户可以通过 CLI 强制刷新缓存。
4. deep 模式优先尝试刷新关键数据。
```

---

# 7. 产业链分析模块设计

## 7.1 是否需要产业链分析

需要。

A 股很多机会并不是单只股票孤立产生的，而是来自：

```text
政策方向
产业趋势
板块轮动
产业链扩散
订单预期
国产替代
供需变化
价格周期
```

所以个股分析默认要带产业链定位，但要按 quick / standard / deep 控制展开程度。

## 7.2 a-stock-data 是否足够支撑产业链分析

结论：

```text
a-stock-data 足够支撑产业链分析第一版的数据证据层。
但不够单独支撑完整产业链知识图谱。
```

也就是说：

```text
a-stock-data 负责动态证据
本地产业链知识库负责产业链结构
industry_chain.py 负责分析判断
```

## 7.3 a-stock-data 可提供的产业链相关数据

```text
行业板块排名
概念板块归属
强势股题材归因
个股新闻
财联社快讯
全球资讯
研报列表
研报 PDF
一致预期 EPS
F10 公司资料
东财个股信息
财务三表
季报 37 字段
公告
资金流
龙虎榜
北向资金
限售解禁
```

这些数据可以帮助判断：

```text
股票属于什么行业/概念
市场正在炒什么题材
公司上涨是否有题材原因
是否有订单/公告/业绩验证
资金是否关注
研报是否覆盖某个产业逻辑
是否存在解禁、减持、监管风险
```

## 7.4 a-stock-data 不足的地方

它不直接提供：

```text
完整上中下游结构
公司与公司之间的供应链关系
产品收入占比与具体产业链映射
某公司是否为某环节核心供应商
产业链利润分配
产业链价格传导路径
海外竞争格局
长期技术路线图
```

这些需要本项目补充：

```text
industry_chains.yaml
company_tags.yaml
supply_chain_relations.yaml
研报/RAG 知识库
F10 主营业务匹配
公告与新闻事件抽取
```

## 7.5 产业链数据三层架构

```text
第一层：静态产业链知识库
  - industry_chains.yaml
  - company_tags.yaml
  - supply_chain_relations.yaml

第二层：动态市场数据
  - 来自 a-stock-data
  - 板块、概念、行情、资金、公告、新闻、研报、财务

第三层：分析判断层
  - industry_chain.py
  - 判断环节、受益类型、验证程度、风险等级
```

## 7.6 industry_chains.yaml 示例

```yaml
industries:
  ai_compute:
    name: "AI算力"
    aliases:
      - "人工智能算力"
      - "算力"
      - "AI服务器"
      - "数据中心"

    drivers:
      - "大模型训练需求"
      - "推理算力需求增长"
      - "云厂商资本开支"
      - "国产算力替代"
      - "数据中心建设"

    upstream:
      - segment: "GPU/AI芯片"
        description: "算力产业链核心，决定训练和推理性能。"
        key_metrics:
          - "芯片出货量"
          - "订单排期"
          - "国产替代进度"
        companies:
          - symbol: "688256"
            name: "寒武纪"
            role: "国产AI芯片"
            benefit_type: "直接受益"

      - segment: "HBM/存储"
        description: "高端AI芯片配套关键环节。"
        key_metrics:
          - "HBM供需"
          - "存储价格"
        companies: []

    midstream:
      - segment: "AI服务器"
        description: "将芯片、存储、网络、电源集成为算力设备。"
        key_metrics:
          - "服务器订单"
          - "云厂商采购"
          - "毛利率变化"
        companies:
          - symbol: "603019"
            name: "中科曙光"
            role: "服务器/算力基础设施"
            benefit_type: "直接受益"

      - segment: "液冷"
        description: "高功耗数据中心散热方案。"
        key_metrics:
          - "液冷渗透率"
          - "数据中心PUE要求"
        companies: []

      - segment: "光模块/高速互联"
        description: "训练集群中高速通信关键部件。"
        key_metrics:
          - "800G/1.6T需求"
          - "海外云厂商订单"
        companies: []

    downstream:
      - segment: "云厂商/数据中心"
        description: "算力采购和应用落地载体。"
        key_metrics:
          - "资本开支"
          - "机柜建设"
          - "算力租赁价格"
        companies: []

      - segment: "AI应用"
        description: "大模型和企业应用需求端。"
        key_metrics:
          - "付费用户"
          - "商业化收入"
        companies: []

    risks:
      - "估值过高"
      - "订单兑现不及预期"
      - "海外芯片限制"
      - "云厂商资本开支下降"
      - "题材退潮"
```

## 7.7 产业链分析器 industry_chain.py

核心职责：

```text
1. 读取本地产业链配置。
2. 根据股票行业、概念、F10、公告、新闻、研报匹配产业链。
3. 判断公司处于上游、中游还是下游。
4. 判断直接受益、间接受益、概念相关、伪概念风险。
5. 计算产业链热度和公司受益评分。
6. 输出产业链报告或个股产业链定位。
```

核心接口：

```python
class IndustryChainAnalyzer:
    def analyze_industry_chain(self, industry_key: str) -> dict: ...

    def analyze_company_position(
        self,
        symbol: str,
        industry_key: str | None = None,
        mode: str = "standard",
    ) -> dict: ...

    def generate_chain_watchlist(self, industry_key: str) -> list[dict]: ...
```

## 7.8 产业链评分体系

### 环节评分

```text
segment_score =
  景气度 * 0.25
+ 政策/事件催化 * 0.15
+ 业绩兑现度 * 0.20
+ 资金关注度 * 0.15
+ 估值合理性 * 0.10
+ 技术趋势 * 0.10
+ 风险折扣 * 0.05
```

### 公司受益评分

```text
company_benefit_score =
  产业链相关度 * 0.25
+ 收入/利润弹性 * 0.20
+ 行业地位 * 0.15
+ 订单/公告验证 * 0.15
+ 资金关注度 * 0.10
+ 技术趋势 * 0.10
+ 风险折扣 * 0.05
```

## 7.9 个股分析中的产业链规则

个股分析默认带产业链内容。

### quick 模式

只输出：

```text
所属行业
所属概念/主题
是否处于当前强势方向
产业链环节
受益类型
一句风险提示
```

### standard 模式

输出：

```text
所属产业链
所处环节
受益逻辑
业绩验证
同链核心标的简要对比
风险提示
```

### deep 模式

输出：

```text
完整产业链拆解
上下游关系
同环节公司对比
直接受益证据
订单/公告/研报验证
蹭概念风险
产业链跟踪指标
```

---

# 8. Python 与 LLM 分工原则

## 8.1 为什么需要明确分工

本项目不能设计成纯 Python，也不能设计成纯 LLM。

纯 Python 的问题：

```text
规则容易死板
产业链逻辑难以动态理解
公告和新闻影响难以准确解释
最终报告表达不够自然
复杂交易场景缺少灵活判断
```

纯 LLM 的问题：

```text
指标计算容易出错
财务口径可能不一致
技术分析不可复现
仓位和风控不稳定
容易产生没有数据支撑的判断
```

因此采用混合架构：

```text
Python 负责“准”
LLM 负责“活”
配置负责“可调”
风控负责“刹车”
```

## 8.2 总体分工

```text
AStockDataGateway
  ↓
Python Analyzers
  ↓
Structured Evidence
  ↓
Rule Engine / Risk Engine
  ↓
LLM Reasoning Layer
  ↓
Markdown Report
```

也就是：

```text
数据层：a-stock-data + AStockDataGateway
计算层：technical.py / fundamental.py / valuation.py / capital_flow.py
知识层：industry_chains.yaml / company_tags.yaml / research_notes.md
规则层：risk_rules.yaml / strategy_profiles.yaml
推理层：LLM 根据结构化证据做综合判断
输出层：报告模板 + Markdown
```

## 8.3 Python 应该负责什么

Python 负责确定性、可计算、可测试、可复现的部分。

包括：

```text
行情数据标准化
技术指标计算
财务指标计算
估值分位计算
资金流统计
公告关键词初筛
新闻事件初筛
支撑压力计算
风险规则检查
仓位上限计算
组合集中度计算
交易复盘统计
缓存管理
CLI 命令
报告模板渲染
```

Python 输出的应该是结构化证据，而不是最终投资结论。

例如，技术分析器不应该直接输出：

```text
可以买
必须卖
明天会涨
```

而应该输出：

```json
{
  "technical_score": 76,
  "trend": "技术面偏强",
  "signals": [
    "收盘价站上20日线",
    "MACD处于多头状态",
    "成交量较20日均量放大"
  ],
  "warnings": [
    "距离前高压力位较近"
  ],
  "support_levels": [34.8, 32.5],
  "resistance_levels": [38.6, 41.2]
}
```

## 8.4 LLM 应该负责什么

LLM 负责非结构化理解、综合解释、报告表达和复杂场景归纳。

包括：

```text
公告影响解释
新闻催化解释
产业链逻辑表达
真受益 vs 蹭概念判断解释
多因素综合归纳
风险情景推演
交易计划文字化
研报生成
交易复盘点评
```

LLM 的输入必须是 Python 生成的结构化证据和可追溯文本，不应凭空生成结论。

例如，LLM 输入：

```json
{
  "technical_score": 78,
  "industry_chain_position": "AI服务器/算力基础设施",
  "benefit_type": "直接受益",
  "valuation_level": "偏高",
  "risk_level": "中高",
  "capital_flow_score": 71,
  "evidence": [
    "公司主营业务与服务器相关",
    "近期公告提到算力基础设施项目",
    "AI算力板块近5日涨幅居前"
  ]
}
```

LLM 输出：

```text
该股技术面偏强，且处于 AI 算力产业链中游算力基础设施环节，属于直接受益方向。但当前估值偏高，风险等级为中高，不适合重仓追高，更适合等待回踩确认后小仓位试错。
```

## 8.5 配置文件应该负责什么

配置文件负责可调规则，避免把所有阈值写死到代码里。

例如：

```yaml
technical_rules:
  trend:
    strong_score: 80
    bullish_score: 65
    neutral_score: 45

  risk:
    far_above_ma20_pct: 12
    rsi_overbought: 80
    volume_spike_ratio: 1.5

position_rules:
  low_risk_max_pct: 20
  medium_risk_max_pct: 15
  high_risk_max_pct: 5
```

以后如果要调整策略，只修改 YAML，不需要改 Python 代码。

## 8.6 风控层应该负责什么

风控层是系统的硬约束。

即使 LLM 认为逻辑很好，只要触发硬性风险，决策也必须降级。

硬性风险示例：

```text
立案调查
退市风险
重大违法
财务造假风险
严重流动性不足
单票仓位超过上限
行业/产业链集中度过高
```

风控规则：

```text
存在 hard_blocks → 直接 avoid
风险等级为高 → 不能输出 buy_with_plan
风险等级为极高 → 最高只能 watch 或 avoid
```

## 8.7 各模块分工表

| 模块 | Python | LLM | 配置 |
|---|---|---|---|
| 行情数据 | 字段标准化、缓存 | 不参与 | 数据源配置 |
| 技术分析 | 指标计算、评分 | 解释技术状态 | 技术阈值 |
| 基本面 | 财务指标计算、异常检测 | 总结财务质量 | 财务阈值 |
| 估值 | 分位数、横向对比 | 解释贵不贵 | 估值阈值 |
| 公告 | 关键词初筛、事件分类 | 判断影响程度 | 事件规则 |
| 新闻 | 初步分类、去重 | 催化解释 | 新闻源配置 |
| 资金流 | 净流入统计、评分 | 解释资金行为 | 评分阈值 |
| 产业链 | 匹配标签、计算热度 | 判断受益逻辑 | 产业链知识库 |
| 风控 | 硬规则、仓位上限 | 解释风险 | 风控规则 |
| 决策 | 权重融合、决策枚举 | 生成自然语言结论 | 策略配置 |
| 报告 | 模板渲染 | 段落生成 | 模板配置 |

## 8.8 产业链模块的混合设计

产业链分析不能只靠 Python 写死，也不能只靠 LLM 猜。

推荐结构：

```text
本地知识库给初始标签
        ↓
a-stock-data 提供动态证据
        ↓
Python 做匹配和评分
        ↓
LLM 判断逻辑是否成立并解释
        ↓
风控层识别蹭概念风险
```

例如：

```text
本地标签：
中科曙光 = AI服务器 / 算力基础设施

动态验证：
最近新闻有没有 AI 服务器订单？
公告有没有相关合同？
研报有没有强调算力业务？
财务有没有体现增长？
板块是不是还强？
资金是不是还在流入？

综合判断：
直接受益逻辑仍成立 / 逻辑减弱 / 只是题材带动
```

因此产业链模块中的配置不是最终结论，而是初始假设；`a-stock-data` 的动态数据是证据；LLM 负责解释证据；风控负责约束风险。

## 8.9 Analyzer 输出规范

所有 analyzer 必须输出结构化证据。

建议字段：

```json
{
  "module": "technical",
  "score": 76,
  "summary": "技术面偏强",
  "signals": [],
  "warnings": [],
  "evidence": [],
  "missing_data": [],
  "confidence": 0.72
}
```

禁止 analyzer 直接输出：

```text
一定买
一定卖
必涨
稳赚
满仓
```

## 8.10 LLM Reasoning Layer 输入规范

LLM 不直接从原始数据生成结论，而是接收：

```text
结构化分析结果
关键公告/新闻摘要
产业链匹配证据
风险检查结果
用户风险偏好
用户持仓信息
```

输入示例：

```json
{
  "stock": {},
  "market": {},
  "sector": {},
  "industry_chain": {},
  "technical": {},
  "fundamental": {},
  "valuation": {},
  "events": {},
  "capital_flow": {},
  "risk": {},
  "position": {},
  "user_profile": {}
}
```

## 8.11 最终结论生成原则

最终结论由决策引擎和 LLM 共同完成：

```text
Python decision_engine 生成：decision、score、risk_level、position_limit
LLM 生成：原因解释、风险场景、交易计划文字、报告段落
```

最终输出必须包含：

```text
核心结论
主要依据
主要风险
适合什么周期
不适合什么情况
交易计划
止损参考
仓位建议
反向失效条件
```

## 8.12 开发原则

```text
1. Python 不负责拍脑袋，只负责算准和整理证据。
2. LLM 不负责裸算指标，只负责综合解释和报告生成。
3. 阈值不写死，优先放进配置文件。
4. 风控规则优先于最终评分。
5. 每个结论都要有 evidence 字段。
6. 数据缺失时要降级分析并说明 missing_data。
7. 任何模块都不能输出确定性收益承诺。
```

## 8.13 Structured Evidence 标准结构

所有 analyzer 应统一输出 `AnalyzerEvidence`，方便后续决策引擎和 LLM Reasoning Layer 接入。

推荐 Pydantic 结构：

```python
from pydantic import BaseModel, Field
from typing import Any


class RawRef(BaseModel):
    source: str
    title: str | None = None
    url: str | None = None
    publish_time: str | None = None
    ref_type: str | None = None


class AnalyzerEvidence(BaseModel):
    module: str
    score: float | None = None
    score_level: str | None = None
    summary: str
    signals: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    raw_refs: list[RawRef] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)
```

统一规则：

```text
1. score 范围默认 0-100；缺失时允许为 None。
2. confidence 范围 0-1。
3. signals 表示正向信号。
4. warnings 表示注意事项。
5. risks 表示明确风险。
6. evidence 必须写可解释依据。
7. missing_data 必须写明缺了什么。
8. raw_refs 用于保留公告、新闻、研报、数据源引用。
```

## 8.14 LLM Prompt 输入输出规范

LLM 不直接接触原始杂乱数据，而是接收结构化证据包。

Prompt 文件建议：

```text
stock_assistant/reports/prompts/
  stock_reasoning_prompt.md
  industry_reasoning_prompt.md
  risk_explanation_prompt.md
  trade_review_prompt.md
```

LLM 输入结构：

```json
{
  "task": "stock_analysis",
  "mode": "standard",
  "symbol": "002415",
  "user_profile": {
    "risk_preference": "balanced",
    "time_horizon": "swing"
  },
  "structured_evidence": {
    "market": {},
    "sector": {},
    "industry_chain": {},
    "technical": {},
    "fundamental": {},
    "valuation": {},
    "events": {},
    "capital_flow": {},
    "risk": {},
    "position": {}
  },
  "constraints": [
    "不得承诺收益",
    "不得输出确定性涨跌",
    "不得鼓励满仓或融资",
    "必须说明风险和反向失效条件"
  ]
}
```

LLM 输出结构：

```json
{
  "one_sentence_conclusion": "",
  "reasoning_summary": "",
  "main_reasons": [],
  "main_risks": [],
  "trade_plan_text": "",
  "invalidation_conditions": [],
  "confidence_comment": "",
  "disclaimer": ""
}
```

LLM 输出约束：

```text
1. 不得新增没有 evidence 支撑的事实。
2. 不得把中性数据解释成强烈利好。
3. 不得忽略 hard_blocks。
4. 不得输出“必涨、稳赚、满仓”等词。
5. 必须说明不确定性。
```

## 8.15 评分缺失值与中性值规则

综合评分时，缺失数据使用中性值，不使用 0 分。

默认中性值：

```text
market_score = 50
sector_score = 50
industry_chain_score = 50
technical_score = 50
fundamental_score = 50
valuation_score = 50
news_score = 50
capital_flow_score = 50
risk_score = 50
```

缺失值规则：

```text
1. 缺失数据使用 50 分，不直接惩罚。
2. 缺失关键数据降低 confidence。
3. 风险数据缺失标记 unknown，不等于 low risk。
4. hard_blocks 数据缺失时不能判定安全。
5. deep 模式中若关键数据缺失，需要在报告开头提示分析限制。
```

confidence 调整示例：

```text
缺少一个非关键模块：confidence -0.03
缺少一个关键模块：confidence -0.08
缺少 K线或财务等核心数据：confidence -0.15
使用过期缓存：confidence -0.05
公告/风险数据未知：confidence -0.08
```

---

# 9. 内部分析模块设计

## 9.1 market_regime.py 大盘环境分析

目标：判断当前大盘状态和建议总仓位。

输入：

```text
主要指数 K 线
成交额
涨跌家数
板块表现
```

输出：

```json
{
  "market_regime": "震荡偏强",
  "market_score": 68,
  "risk_appetite": "中等偏高",
  "suggested_total_position": "50%-70%",
  "reasons": [],
  "warnings": []
}
```

状态枚举：

```text
强势上涨
震荡偏强
震荡偏弱
弱势下跌
```

## 9.2 sector_rotation.py 板块轮动分析

目标：识别市场主线、退潮方向、补涨方向。

评分：

```text
今日涨幅 25%
5日涨幅 20%
20日涨幅 15%
成交额排名 20%
龙头强度 15%
连续性 5%
```

输出：

```json
{
  "hot_sectors": [],
  "emerging_sectors": [],
  "cooling_sectors": [],
  "overheated_sectors": []
}
```

## 9.3 technical.py 技术分析

实现指标：

```text
MA5/10/20/60/120
MACD
RSI14
BOLL
ATR14
成交量均线
20/60/120日高低点
```

输出：

```json
{
  "technical_score": 76,
  "trend": "技术面偏强",
  "signals": [],
  "warnings": [],
  "support_levels": [],
  "resistance_levels": [],
  "stop_loss": 34.8,
  "entry_strategy": "等待回踩20日线不破"
}
```

## 9.4 fundamental.py 基本面分析

维度：

```text
成长性
盈利能力
现金流质量
资产负债健康
稳定性
```

输出：

```json
{
  "fundamental_score": 82,
  "quality_level": "优秀",
  "highlights": [],
  "risks": [],
  "red_flags": []
}
```

## 9.5 valuation.py 估值分析

指标：

```text
PE TTM
PB
PS
PEG
股息率
历史估值分位
行业估值对比
```

估值分位：

```text
0%-20%：偏低
20%-40%：合理偏低
40%-60%：合理
60%-80%：合理偏高
80%-100%：偏高
```

## 9.6 announcement.py 公告分析

识别事件：

```text
业绩预增
业绩预亏
减持
增持
回购
解禁
重大合同
中标
重组
监管处罚
监管问询
立案调查
诉讼
退市风险
商誉减值
```

输出：

```json
{
  "events": [],
  "positive_events": [],
  "negative_events": [],
  "hard_risk_events": []
}
```

## 9.7 news_sentiment.py 新闻舆情

目标：判断短期催化和风险。

输出：

```json
{
  "sentiment_score": 68,
  "summary": "近期新闻偏正面",
  "positive_events": [],
  "negative_events": [],
  "uncertain_events": []
}
```

## 9.8 capital_flow.py 资金流分析

维度：

```text
主力资金
超大单
大单
北向资金
两融
龙虎榜
大宗交易
股东户数
```

输出：

```json
{
  "capital_flow_score": 71,
  "summary": "短期资金关注度较高",
  "signals": [],
  "warnings": []
}
```

## 9.9 risk.py 风险控制

风险类型：

```text
技术风险
基本面风险
公告风险
估值风险
资金风险
市场风险
仓位风险
产业链退潮风险
```

输出：

```json
{
  "risk_level": "中高",
  "risk_points": 5,
  "warnings": [],
  "hard_blocks": [],
  "max_position_pct": 10,
  "must_confirm": true
}
```

---

# 10. 决策引擎设计

## 12.1 decision_engine.py 目标

融合所有分析结果，生成最终决策辅助建议。

## 12.2 决策枚举

```text
avoid：规避
watch：继续观察
wait_pullback：等待回调
small_position_try：小仓位试错
buy_with_plan：按计划分批参与
hold：继续持有
reduce：减仓
sell_stop_loss：止损卖出
```

## 12.3 综合评分权重

标准模式推荐：

```text
大盘环境 10%
板块强度 10%
产业链受益 15%
技术面 20%
基本面 15%
估值 10%
公告/新闻 5%
资金流 5%
风险控制 10%
```

## 12.4 产业链对决策的影响

规则：

```text
强产业链 + 核心环节 + 直接受益 + 有业绩验证：提高评级
强产业链 + 间接受益 + 资金关注：小幅提高评级
强产业链 + 仅概念相关 + 无业绩验证：不提高评级，提示风险
弱产业链 + 技术破位：降低评级
产业链退潮 + 高位放量：显著降低评级
```

## 12.5 风控优先级

风控优先于评分。

```text
如果存在 hard_blocks，直接 avoid。
如果风险等级为高，不能输出 buy_with_plan。
如果风险等级为极高，最高只能 watch 或 avoid。
```

## 10.6 输出结构

```json
{
  "symbol": "002415",
  "decision": "small_position_try",
  "decision_cn": "小仓位试错",
  "total_score": 72.5,
  "confidence": 0.68,
  "reasons": [],
  "risks": [],
  "trade_plan": {
    "entry": "回踩20日线不破",
    "stop_loss": 34.8,
    "take_profit": "接近压力位分批减仓",
    "position": "首次不超过5%，总仓位不超过10%"
  },
  "invalidation_conditions": []
}
```

---

# 11. 五个对外 Skill 的 SKILL.md 设计

## 10.1 a-stock-stock-analysis/SKILL.md

```markdown
---
name: a-stock-stock-analysis
description: Analyze a single A-share stock using market context, sector strength, industry chain position, technicals, fundamentals, valuation, events, capital flow, risk control, and trade planning.
---

# A 股个股综合分析 Skill

## When to use

Use this skill when the user asks:

- 分析某只股票能不能买。
- 某只股票要不要卖。
- 某只持仓还能不能拿。
- 给某只股票制定交易计划。
- 判断某只股票是不是真受益。

## Modes

- quick: 快速分析
- standard: 标准分析，默认
- deep: 深度分析

## Workflow

1. Identify stock name, industry, and concepts.
2. Load cached market and sector context.
3. Fetch stock data through AStockDataGateway.
4. Analyze industry chain position.
5. Analyze technicals.
6. Analyze fundamentals.
7. Analyze valuation.
8. Analyze announcements and news.
9. Analyze capital flow.
10. Run risk control.
11. Generate position sizing.
12. Generate final decision and report.

## Output Requirements

Always include:

- 核心结论
- 大盘与板块背景
- 产业链位置
- 技术面
- 基本面
- 估值
- 公告新闻
- 资金面
- 风险检查
- 交易计划
- 反向失效条件

## Safety Rules

Never promise returns.
Never say a stock will definitely rise.
Never encourage full-position buying or margin trading.
Always include risk warnings.
```

## 10.2 a-stock-daily-workflow/SKILL.md

```markdown
---
name: a-stock-daily-workflow
description: Generate daily A-share trading workflow including morning briefing, intraday watch, close review, weekly plan, and watchlist scan.
---

# A 股每日交易流程 Skill

## When to use

Use when the user asks:

- 生成今天的盘前计划。
- 今天 A 股怎么看？
- 做盘后复盘。
- 扫描自选股。
- 生成本周交易计划。

## Workflow

1. Load user watchlist and positions.
2. Analyze market regime.
3. Analyze sector rotation.
4. Analyze industry chain heat.
5. Review positions.
6. Scan watchlist.
7. Detect risk events.
8. Generate report.
```

## 10.3 a-stock-industry-research/SKILL.md

```markdown
---
name: a-stock-industry-research
description: Analyze A-share sectors, themes, and industry chains, including upstream, midstream, downstream, real beneficiaries, concept risks, and watchlists.
---

# A 股行业与产业链研究 Skill

## When to use

Use when the user asks:

- 分析某个产业链。
- 某个板块谁最受益。
- 某个概念是不是真逻辑。
- 找某个产业链核心股票。

## Workflow

1. Identify industry/theme.
2. Load local industry chain knowledge.
3. Fetch sector/concept/news/report/fund flow data through AStockDataGateway.
4. Analyze upstream/midstream/downstream.
5. Score segments and companies.
6. Separate real beneficiaries from concept-only names.
7. Generate watchlist and risks.
```

## 10.4 a-stock-portfolio-risk/SKILL.md

```markdown
---
name: a-stock-portfolio-risk
description: Diagnose A-share portfolio risk, including position concentration, industry exposure, industry chain exposure, single-stock risk, and total position suggestions.
---

# A 股持仓组合风险诊断 Skill

## When to use

Use when the user asks:

- 看看我的持仓风险。
- 我的组合是不是太集中？
- 当前应该几成仓？
- 哪些持仓需要减仓？

## Workflow

1. Load positions.
2. Map each stock to industry and industry chain.
3. Analyze single-stock risks.
4. Analyze industry and chain concentration.
5. Generate total position suggestion.
6. Generate adjustment suggestions.
```

## 10.5 a-stock-trade-review/SKILL.md

```markdown
---
name: a-stock-trade-review
description: Record and review A-share trades, calculate win rate, profit/loss ratio, mistake tags, and discipline execution.
---

# A 股交易复盘 Skill

## When to use

Use when the user asks:

- 记录一笔交易。
- 复盘今天的交易。
- 分析我最近交易问题。
- 统计胜率和盈亏比。

## Workflow

1. Read or write trade journal.
2. Calculate trade statistics.
3. Identify mistake tags.
4. Evaluate discipline execution.
5. Generate improvement suggestions.
```

---

# 12. 工作流设计

## 11.1 stock_deep_dive.py 个股综合分析

### quick

```text
输入股票代码
  ↓
获取实时行情 + K线
  ↓
读取缓存的大盘/板块/产业链上下文
  ↓
技术分析
  ↓
基础风险检查
  ↓
简短结论
```

### standard

```text
输入股票代码
  ↓
并行获取：行情/K线/估值/财务摘要/公告/新闻/资金流
  ↓
读取缓存：大盘/板块/产业链
  ↓
技术 + 基本面 + 估值 + 事件 + 资金分析
  ↓
风险检查
  ↓
仓位建议
  ↓
综合决策
  ↓
生成标准报告
```

### deep

```text
输入股票代码
  ↓
执行 standard 模式
  ↓
追加获取：完整财务三表/研报/同链公司/历史估值/深度公告
  ↓
产业链横向比较
  ↓
财务质量深挖
  ↓
生成深度报告
```

## 11.2 morning_brief.py 盘前简报

```text
读取 watchlist 和 positions
  ↓
更新 market_context
  ↓
更新 sector_context
  ↓
更新 industry_context
  ↓
检查持仓风险
  ↓
扫描自选股机会
  ↓
生成今日计划
```

## 11.3 close_review.py 盘后复盘

```text
获取指数表现
  ↓
获取板块表现
  ↓
复盘产业链主线
  ↓
复盘持仓
  ↓
复盘今日交易
  ↓
生成明日计划
```

## 11.4 industry_chain_deep_dive.py 产业链深度分析

```text
识别产业链名称
  ↓
加载 industry_chains.yaml
  ↓
获取板块、概念、新闻、公告、研报、资金流
  ↓
分析上中下游
  ↓
筛选核心受益公司
  ↓
识别蹭概念风险
  ↓
输出产业链报告
```

## 11.5 portfolio_review.py 组合风险诊断

```text
读取持仓
  ↓
识别每只股票行业与产业链
  ↓
计算单票仓位
  ↓
计算行业集中度
  ↓
计算产业链集中度
  ↓
检查个股风险
  ↓
输出组合建议
```


## 12.6 报告输出示例

### quick 模式示例

```markdown
# 个股快速分析：{{ name }}（{{ symbol }}）

## 核心结论

暂时观察，不建议追高。当前技术面偏强，但股价接近前高压力位，风险收益比一般。

## 关键信息

- 大盘状态：震荡偏强
- 板块状态：所属板块近期强于大盘
- 产业链定位：属于 AI 算力中游算力基础设施环节，偏直接受益
- 技术状态：站上 20 日线和 60 日线，成交量温和放大
- 支撑位：34.8
- 压力位：38.6

## 风险提示

板块短期涨幅较大，如果后续放量滞涨或跌破 20 日线，需要降低预期。

## 交易计划

- 激进：放量突破压力位后小仓位试错
- 稳健：等待回踩 20 日线不破再考虑
- 止损：跌破 34.8 且放量
- 仓位：首次不超过 5%，总仓位不超过 10%

## 反向失效条件

1. 跌破关键支撑位并放量。
2. 所属板块退潮。
3. 出现重大利空公告。
```

### standard 模式示例

```markdown
# 个股综合分析：{{ name }}（{{ symbol }}）

## 1. 核心结论

当前建议：等待回调 / 小仓位试错  
综合评分：72/100  
风险等级：中高  
一句话结论：公司产业链逻辑较清晰，技术面偏强，但估值和短线位置不适合重仓追高。

## 2. 大盘与板块

当前市场处于震荡偏强状态，所属板块近期表现强于大盘，但板块内部已经开始分化。

## 3. 产业链位置

公司位于 AI 算力产业链中游，属于算力基础设施环节。若后续公告、订单或财务数据继续验证算力业务增长，产业链逻辑可以维持；如果仅靠题材上涨，需要警惕概念炒作风险。

## 4. 技术面

技术面偏强，股价站上中短期均线，但上方接近前高压力区。

## 5. 基本面与估值

基本面质量中等偏好，估值处于合理偏高区间，需要业绩增长继续支撑。

## 6. 公告新闻与资金流

近期未发现硬性利空事件，资金关注度中等偏高。

## 7. 风险检查

主要风险包括：估值偏高、板块退潮、短线追高、订单兑现不及预期。

## 8. 交易计划

等待回踩确认优于直接追高。首次仓位不超过 5%，确认后总仓位不超过 10%。

## 9. 反向失效条件

跌破关键支撑、板块转弱、出现减持/监管/业绩不及预期等事件时，原判断失效。
```

---

# 13. CLI 设计

## 15.1 命令总览

```bash
stock-assistant analyze SYMBOL --mode quick
stock-assistant analyze SYMBOL --mode standard
stock-assistant analyze SYMBOL --mode deep

stock-assistant morning
stock-assistant intraday-watch
stock-assistant close-review
stock-assistant weekly-review

stock-assistant industry "AI算力"
stock-assistant industry "半导体" --deep

stock-assistant portfolio review

stock-assistant trade add
stock-assistant trade list
stock-assistant trade review

stock-assistant cache refresh-market
stock-assistant cache refresh-sector
stock-assistant cache refresh-industry
```

## 15.2 CLI 输出原则

```text
1. 默认输出 Markdown。
2. 终端使用 Rich 渲染。
3. 支持 --json 输出结构化结果。
4. 支持 --output report.md 保存报告。
5. 错误时提示缺失数据和降级结果。
```

---

# 14. 配置文件设计

## 13.1 user_profile.yaml

```yaml
user:
  default_market: A
  risk_preference: balanced
  default_time_horizon: swing
  default_analysis_mode: standard
  max_single_stock_pct: 15
  max_sector_pct: 35
  max_chain_pct: 35
  prefer_stop_loss: true
  report_language: zh-CN
```

## 13.2 watchlist.yaml

```yaml
watchlists:
  core:
    - symbol: "300750"
      name: "宁德时代"
      industry: "新能源"
      chain: "新能源车"
      note: "中长期观察"
      priority: high

  short_term:
    - symbol: "603019"
      name: "中科曙光"
      industry: "AI算力"
      chain: "AI算力"
      note: "观察突破"
      priority: high

positions:
  - symbol: "300750"
    name: "宁德时代"
    cost: 180.5
    position_pct: 12
    stop_loss: 168
    plan: "中线持有，跌破止损"
```

## 15.3 risk_rules.yaml

```yaml
max_single_stock_pct:
  low_risk: 25
  medium_risk: 15
  medium_high_risk: 10
  high_risk: 5
  extreme_risk: 0

max_sector_pct:
  default: 35

max_chain_pct:
  default: 35

technical_rules:
  warn_if_below_ma20: true
  warn_if_below_ma60: true
  warn_if_far_above_ma20_pct: 12
  warn_if_rsi_above: 80
  warn_if_rsi_below: 30
  stop_loss_atr_multiplier: 2.0

fundamental_rules:
  warn_if_revenue_yoy_below: -10
  warn_if_net_profit_yoy_below: -20
  warn_if_debt_ratio_above: 70
  warn_if_ocf_negative: true

announcement_rules:
  hard_block_events:
    - 立案调查
    - 退市风险
    - 重大违法
  warn_events:
    - 减持
    - 解禁
    - 诉讼
    - 监管问询
    - 业绩预亏

industry_chain_rules:
  warn_if_concept_only: true
  warn_if_no_business_validation: true
  warn_if_chain_overheated: true
```

---

# 15. 交易日志与复盘设计

## 14.1 SQLite 数据库

默认路径：

```text
~/.stock_assistant/stock_assistant.db
```

## 14.2 trades 表

```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT,
    action TEXT NOT NULL,
    price REAL NOT NULL,
    quantity INTEGER,
    amount REAL,
    reason TEXT,
    plan TEXT,
    emotion TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

## 14.3 trade_reviews 表

```sql
CREATE TABLE trade_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER,
    review_date TEXT,
    result_pct REAL,
    followed_plan INTEGER,
    mistake_tags TEXT,
    lesson TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

## 15.4 错误标签

```text
追高
未止损
过早卖出
频繁交易
逆势交易
无计划买入
仓位过重
题材退潮后接盘
公告风险未检查
大盘弱势仍重仓
亏损后情绪化加仓
盈利后盲目加仓
```

---

# 16. 开发阶段规划

## 16.0 第一版 MVP 最小闭环

第一版不要追求完整平台，先完成最小可用闭环。

MVP 只做 3 个命令：

```bash
stock-assistant analyze SYMBOL --mode quick
stock-assistant analyze SYMBOL --mode standard
stock-assistant morning
```

MVP 必须包含：

```text
1. AStockDataGateway 基础适配。
2. K线和实时行情字段标准化。
3. 技术分析。
4. 大盘与板块缓存。
5. 简化产业链定位。
6. 基础风险检查。
7. 基础仓位建议。
8. 个股 quick / standard 报告。
9. 盘前简报。
10. 风险提示和反向失效条件。
```

MVP 暂不做：

```text
deep 深度研报
完整交易日志
组合诊断
复杂 RAG
可视化面板
自动预警
真实交易接口
```

## 阶段 0：a-stock-data 适配层

目标：先打通数据层。

任务：

```text
1. 阅读已安装 a-stock-data 的 SKILL.md 和可用端点。
2. 实现 AStockDataGateway。
3. 标准化行情、财务、公告、新闻、资金流字段。
4. 实现缓存层。
5. 实现字段校验和异常处理。
6. 编写测试 fixture。
```

验收：

```bash
stock-assistant cache refresh-market
stock-assistant analyze 002415 --mode quick
```

## 阶段 1：MVP 个股快速分析

目标：能快速分析单只股票。

任务：

```text
technical.py
market_regime.py
sector_rotation.py
industry_chain.py 简化版
risk.py 简化版
position_sizer.py 简化版
decision_engine.py 简化版
stock_deep_dive.py quick/standard
skills/a-stock-stock-analysis/SKILL.md
```

验收：

```bash
stock-assistant analyze 002415 --mode quick
stock-assistant analyze 002415 --mode standard
```

## 阶段 2：每日工作流

目标：可以辅助每天盘前盘后。

任务：

```text
watchlist.yaml
morning_brief.py
close_review.py
context_cache.py
skills/a-stock-daily-workflow/SKILL.md
```

验收：

```bash
stock-assistant morning
stock-assistant close-review
```

## 阶段 3：产业链研究增强

目标：支持产业链报告和个股产业链定位。

任务：

```text
industry_chains.yaml
company_tags.yaml
industry_chain.py 标准版
industry_chain_deep_dive.py
skills/a-stock-industry-research/SKILL.md
```

优先支持：

```text
AI算力
半导体
机器人
新能源车
固态电池
创新药
低空经济
消费电子
数据中心
军工信息化
```

验收：

```bash
stock-assistant industry "AI算力"
stock-assistant analyze 603019 --mode deep
```

## 阶段 4：基本面、估值、事件、资金增强

目标：提升标准分析质量。

任务：

```text
fundamental.py
valuation.py
announcement.py
news_sentiment.py
capital_flow.py
risk.py 完整版
decision_engine.py 完整版
```

验收：

```bash
stock-assistant analyze 002415 --mode standard
```

报告中应包含：

```text
基本面评分
估值判断
公告风险
新闻催化
资金流判断
完整风控
```

## 阶段 5：组合风险与交易复盘

目标：管理持仓和提升交易能力。

任务：

```text
portfolio_review.py
journal_store.py
trade_review.py
weekly_review.py
skills/a-stock-portfolio-risk/SKILL.md
skills/a-stock-trade-review/SKILL.md
```

验收：

```bash
stock-assistant portfolio review
stock-assistant trade add ...
stock-assistant trade review
```

## 阶段 6：高级扩展

任务：

```text
回测系统
多因子评分
RAG 研报库
产业链知识图谱
可视化面板
openclaw-finagent 总入口插件
```

---

# 17. Codex 开发任务 Prompt

## 18.1 总 Prompt

```text
我要开发一个项目：openclaw-a-stock-investment。

背景：
我已经安装了 a-stock-data Skill，它负责 A 股数据源。现在我要开发一个基于 a-stock-data 的 A 股投资分析决策 Skill 套件。

重要架构要求：
1. 不要重写 a-stock-data。
2. 新项目通过 AStockDataGateway 兼容 a-stock-data。
3. 对外只暴露 5 个任务型 Skill：
   - a-stock-daily-workflow
   - a-stock-stock-analysis
   - a-stock-industry-research
   - a-stock-portfolio-risk
   - a-stock-trade-review
4. 底层分析能力作为内部 Python 模块，不全部暴露成 Skill。
5. 个股分析支持 quick / standard / deep 三档模式。
6. 个股分析默认包含产业链定位，但根据模式控制展开程度。
7. 不自动下单，不承诺收益，不鼓励满仓或融资。

请先完成阶段 0 和阶段 1：

阶段 0：
- 实现 AStockDataGateway
- 实现缓存层
- 标准化字段
- 实现数据校验

阶段 1：
- technical.py
- market_regime.py
- sector_rotation.py
- industry_chain.py 简化版
- risk.py 简化版
- position_sizer.py 简化版
- decision_engine.py 简化版
- stock_deep_dive.py
- cli.py
- skills/a-stock-stock-analysis/SKILL.md

技术栈：
Python, pandas, numpy, pydantic, typer, pyyaml, jinja2, rich, pytest。

CLI 至少支持：
stock-assistant analyze SYMBOL --mode quick
stock-assistant analyze SYMBOL --mode standard
stock-assistant cache refresh-market

所有输出必须包含风险提示、止损参考、仓位建议、反向失效条件。
```

## 18.2 AStockDataGateway Prompt

```text
请实现 stock_assistant/data_gateway.py。

要求：
1. 定义 AStockDataGateway。
2. 它负责适配已安装的 a-stock-data Skill。
3. 对外提供统一接口：
   - get_stock_basic
   - get_realtime_quote
   - get_daily_bars
   - get_index_bars
   - get_sector_performance
   - get_concept_performance
   - get_stock_valuation
   - get_financial_snapshot
   - get_financial_statements
   - get_announcements
   - get_news
   - get_research_reports
   - get_capital_flow
   - get_northbound_flow
   - get_dragon_tiger
   - get_lockup_calendar
4. 所有返回字段必须标准化。
5. 添加缓存、异常处理、字段校验。
6. 不要让 analyzers 直接调用 a-stock-data。
```

## 18.3 Stock Analysis Prompt

```text
请实现 a-stock-stock-analysis 对应的内部工作流 stock_deep_dive.py。

要求：
1. 支持 quick / standard / deep 三档模式。
2. quick 只调用实时行情、K线、技术分析、缓存大盘板块、简化产业链定位、基础风险检查。
3. standard 调用行情、K线、估值、财务摘要、公告、新闻、资金流、产业链定位、风险控制、决策引擎。
4. deep 在 standard 基础上增加完整财务三表、研报、同产业链公司横向比较、公告深度解析。
5. 报告必须包含：核心结论、大盘与板块、产业链位置、技术面、基本面、估值、公告新闻、资金流、风险、交易计划、反向失效条件。
6. 不承诺收益，不自动下单。
```

---

# 18. 验收标准

## 17.1 阶段 1 验收

```bash
stock-assistant analyze 002415 --mode quick
stock-assistant analyze 002415 --mode standard
```

输出必须包含：

```text
核心结论
大盘状态
板块/产业链定位
技术趋势
支撑压力
风险等级
仓位建议
止损参考
反向失效条件
```

## 17.2 阶段 2 验收

```bash
stock-assistant morning
stock-assistant close-review
```

输出必须包含：

```text
今日市场状态
建议总仓位
强势板块
产业链主线
持仓风险
自选股观察条件
今日纪律
明日计划
```

## 17.3 阶段 3 验收

```bash
stock-assistant industry "AI算力"
```

输出必须包含：

```text
上游
中游
下游
核心受益公司
真受益 vs 蹭概念
后续跟踪指标
风险提示
```

## 18.4 阶段 5 验收

```bash
stock-assistant portfolio review
stock-assistant trade review
```

输出必须包含：

```text
组合集中度
产业链集中度
单票风险
总仓位建议
胜率
盈亏比
高频错误
交易纪律建议
```

---

# 19. 最终系统形态

最终系统应形成：

```text
a-stock-data
    ↓
AStockDataGateway
    ↓
a-stock-investment
    ├── 5 个对外 Skill
    ├── 内部分析模块
    ├── 三档个股分析模式
    ├── 产业链知识库
    ├── 风险控制系统
    ├── 交易复盘系统
    └── 报告生成系统
```

后续可扩展：

```text
openclaw-finagent
```

作为统一入口插件。

---

# 20. 最终开发原则总结

```text
1. 不重写数据源，复用 a-stock-data。
2. 不暴露过多 Skill，只暴露 5 个任务型 Skill。
3. 内部模块保持细粒度，方便测试和复用。
4. 个股分析默认带产业链，但按 quick / standard / deep 控制深度。
5. 大盘、板块、产业链背景使用缓存，避免每只股票重复计算。
6. 产业链分析采用“本地知识库 + a-stock-data 动态证据”。
7. 风控优先于评分。
8. 所有报告必须包含风险提示和反向失效条件。
9. 系统目标是辅助决策和复盘，不是预测涨跌。
10. 先做可用 MVP，再扩展深度研报、RAG、回测和可视化。
```

