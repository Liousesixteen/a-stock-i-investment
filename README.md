# A 股投资分析决策助手

这是一个面向 A 股研究的命令行辅助工具。它把 `a-stock-data` 直连数据源能力、AkShare 备用数据源、腾讯历史 K 线备用源、风险规则、产业链知识库、动态知识图谱和报告工作流整合在一起，用于盘前/盘后复盘、个股分析、组合风险、交易复盘和知识库积累。

> 重要边界：本项目只做投资研究辅助，不自动下单，不承诺收益，不构成投资建议。所有输出都应结合个人风险承受能力和二次核验使用。

## 当前状态

已完成第一版可用成品：

- `a-stock-data` 数据源能力已内置到本项目代码，不需要额外安装 `a-stock-data` Skill
- `a-stock-data` 全端点适配面，健康检查中 `unsupported = 0`
- AkShare 作为真实备用数据源
- 腾讯历史 K 线作为百度/东财 K 线失败时的真实备用源
- live 个股分析、盘后复盘、数据源状态报告可运行
- TTL 缓存和失败冷却，避免重复等待慢接口
- 公告/新闻去重与近期过滤
- 动态知识库支持新闻、公告、研报入库
- 测试覆盖核心链路，当前为 `80 passed`

## 安装

建议使用 Python 3.9+。

```bash
cd /Users/ccdemac/DevProjs/a-stock-investment
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

### 安装为 Skill

如果希望智能体在用户自然提问时自动调用这个项目，可以安装统一 Skill 入口：

```bash
./scripts/install_skill.sh
```

安装后会复制到：

```text
~/.agents/skills/a-stock-investment/
```

首次触发时，如果本机还没有可用的 `stock-assistant`，Skill 会运行自带的 bootstrap 脚本，自动完成：

- 获取项目代码
- 创建 `.venv`
- 安装 Python 依赖
- 验证 CLI 是否可运行

这个 Skill 的触发不是靠死板关键词，而是靠 `SKILL.md` frontmatter 里的语义描述。用户可以直接问：

```text
今天 A 股盘面怎么样，明天大盘怎么看？
我手里有 002415，要不要减仓？
算力方向还能追吗？
帮我看看最近公告和研报有没有风险点。
数据源是不是正常，今天拿到的是实时数据吗？
```

智能体会根据问题意图自动选择盘后复盘、个股分析、行业研究、知识库入库或数据源健康检查。用户不需要手动切换模式；只有在需要强制指定深度时，才建议说“quick / standard / deep”或“快速看 / 标准分析 / 深度研究”。

可选配置：

```bash
cp .env.example .env
```

如果要使用 iwencai 语义研报搜索，需要配置：

```bash
export IWENCAI_API_KEY="your_key_here"
export IWENCAI_BASE_URL="https://openapi.iwencai.com"
```

## 常用命令

CLI 是 command-line interface，也就是命令行接口。它是 Skill 背后的稳定执行层：智能体可以调用它获取实时数据、生成报告、检查数据源；开发者也可以直接在终端运行同样的命令来复现结果、排查问题和做自动化测试。

### 盘后复盘

```bash
.venv/bin/stock-assistant close-review --live
```

输出内容包括：

- 主要指数表现
- 北向资金
- 合计成交额
- 强弱板块
- 明日基准/偏强/偏弱三情景
- 明日交易纪律

### 市场情绪与消息面

```bash
.venv/bin/stock-assistant sentiment --live
```

输出内容包括：

- 市场情绪评分和情绪状态
- 多因子评分拆解：指数表现、量能流动性、北向资金、板块扩散、题材热度、消息面
- 指数、北向资金、成交额、板块扩散、题材热度、消息可信度等情绪驱动因子
- 最新消息雷达：利好、利空、中性/待验证、小道消息/传闻
- 事件抽取：事件类别、影响范围、方向、来源等级、置信度
- 国内政策、宏观数据、资金面、外围市场和微观结构跟踪清单
- 使用纪律：传闻不作为单独交易依据，情绪偏热降低追涨

消息面只使用真实数据源：优先 `a-stock-data` 的财联社和东财全球快讯，失败后使用 AkShare 的财联社、富途、同花顺、新浪、东财全球资讯接口。全部失败时明确提示“真实市场新闻缺失”，不使用虚构新闻降级。

### 个股分析

```bash
.venv/bin/stock-assistant analyze 002415 --mode quick --live
.venv/bin/stock-assistant analyze 002415 --mode standard --live
.venv/bin/stock-assistant analyze 002415 --mode deep --live
```

模式说明：

- `quick`：技术面、市场、产业链和基础结论
- `standard`：增加基本面、估值、公告新闻、资金流、仓位建议
- `deep`：增加产业链拆解、同链公司、证据链、跟踪指标和风险情景

保存报告：

```bash
.venv/bin/stock-assistant analyze 002415 --mode standard --live -o reports/002415.md
```

### 数据源状态

```bash
.venv/bin/stock-assistant data health 002415 --provider astock
.venv/bin/stock-assistant data health 002415 --provider akshare
.venv/bin/stock-assistant data health 002415 --provider astock --profile full
.venv/bin/stock-assistant data report 002415 --profile quick
```

说明：

- `health`：检查指定数据源接口是否可用
- `report`：输出健康摘要、失败接口、缓存状态
- `quick`：日常轻量检查
- `full`：全端点检查，可能较慢

### 盘前简报

```bash
.venv/bin/stock-assistant morning --live
```

### 行业研究

```bash
.venv/bin/stock-assistant industry AI算力
.venv/bin/stock-assistant industry 机器人
```

### 组合风险

```bash
.venv/bin/stock-assistant portfolio review
```

### 交易日志和复盘

```bash
.venv/bin/stock-assistant trade add --symbol 002415 --action buy --price 31.8 --quantity 100 --reason "计划内试错"
.venv/bin/stock-assistant trade list
.venv/bin/stock-assistant trade review
```

### 动态知识库

```bash
.venv/bin/stock-assistant knowledge ingest 603019 --source news --live
.venv/bin/stock-assistant knowledge ingest 603019 --source announcements --live
.venv/bin/stock-assistant knowledge ingest 603019 --source research --live
.venv/bin/stock-assistant knowledge candidates
.venv/bin/stock-assistant knowledge promote <candidate_id>
.venv/bin/stock-assistant knowledge reject <candidate_id>
```

知识库默认写入：

```text
data/knowledge/
```

该目录默认不提交到 Git，因为它属于运行时数据。

## 数据源策略

本项目可以独立使用，不依赖用户本机安装 `/Users/.../.agents/skills/a-stock-data` 这个 Skill。`a-stock-data` 的调用逻辑已经沉淀在项目代码里，主要入口包括：

- `stock_assistant/providers/astock_data.py`：直连 HTTP/TCP 数据源实现
- `stock_assistant/data_sources/adapters.py`：`a-stock-data` 与 AkShare 适配器
- `stock_assistant/data_gateway.py`：统一数据网关、缓存、真实备用源和缺失标记

运行时依赖的是 Python 包和外部真实接口，而不是另一个 Skill 文件。

主数据源顺序：

```text
a-stock-data 内置直连源
-> AkShare 同语义真实备用源
-> 已验证的直连 HTTP 真实备用源
-> 明确标记缺失
```

原则：

- 真实数据优先
- AkShare 用作备用兜底，不替代 `a-stock-data`
- 数据源全部失败时只输出缺失说明，不用虚构数据补齐
- 报告会在“数据限制”中说明缺失、降级或真实备用源使用情况

### 数据源清单

| 数据层 | 主数据源 | 备用源 | 说明 |
|---|---|---|---|
| 实时行情 | 腾讯财经直连 API | AkShare `stock_zh_a_spot_em` | 价格、涨跌幅、PE/PB、市值、换手率、涨跌停 |
| 个股日 K | 百度股市通 K 线 | 腾讯历史 K 线、AkShare 腾讯/东财 K 线 | 百度为空或东财代理失败时继续尝试真实 K 线 |
| 指数行情/指数 K | a-stock-data 指数行情、东财/腾讯指数 K | AkShare 指数接口 | 用于大盘快照、量能、情绪评分 |
| 基础资料 | 东财个股资料、百度板块归属、mootdx F10 | AkShare 股票基础资料 | 名称、行业、概念、上市信息、市值等 |
| 财务快照/指标 | Sina 财报三表、mootdx finance | AkShare 东财财务指标、同花顺财务摘要、Sina 财报接口 | Sina 为空时补营收同比、净利同比、毛利率、ROE 等 |
| 研报 | 东财研报、PDF、同花顺 EPS、iwencai | 暂按可用接口返回，缺失则明示 | iwencai 需要可选 API Key |
| 新闻/快讯 | 东财个股新闻、财联社、东财全球资讯 | AkShare 财联社、富途、同花顺、新浪、东财全球资讯 | 全部失败时返回“真实市场新闻缺失” |
| 公告 | 巨潮资讯 cninfo | AkShare 公告接口 | 公告标题、类型、发布时间和链接 |
| 北向资金 | 同花顺/东财北向数据 | AkShare 北向历史和汇总接口 | 统一净流入/净流出口径 |
| 板块/题材 | 东财行业板块、百度概念归属、同花顺热点 | AkShare 行业/概念板块接口 | 若当前网络或反爬导致失败，会在报告中标记缺失 |
| 资金流 | 东财 push2/push2his 个股资金流 | AkShare 个股资金流接口 | 当前环境下东财资金流可能受代理影响，失败不造数 |
| 龙虎榜/解禁/两融/大宗/股东/分红 | 东财 datacenter、交易所/公开接口 | AkShare 对应接口 | 用于风险事件和筹码资金面补充 |

### 覆盖范围

- 行情：腾讯实时行情、百度 K 线、腾讯历史 K 线、mootdx、AkShare
- 研报：东财研报、PDF、同花顺 EPS、iwencai 入口
- 信号：同花顺热点、北向、资金流、龙虎榜、解禁、行业板块
- 资金面：两融、大宗交易、股东户数、分红、资金流
- 新闻：东财个股新闻、财联社、全球资讯
- 基础数据：东财、mootdx F10、Sina 三表、AkShare 东财/同花顺财务指标
- 公告：巨潮、AkShare 公告

### 失败处理

- 不使用 sample、mock、demo 或本地伪造数据作为行情/新闻/公告/财务/资金流兜底
- 单个 live 源失败后，会继续尝试真实备用源；失败冷却不会阻止真实备用源尝试
- 所有真实源都失败时，报告会输出缺失字段和原因，例如“真实资金流缺失”或“真实板块数据缺失”
- 缓存只保存真实返回结果或失败原因，不缓存假数据

## 缓存机制

为了兼顾新鲜度和速度，项目使用 TTL 缓存：

| 数据 | TTL |
|---|---:|
| 实时行情 | 60 秒 |
| 市场快照 | 60 秒 |
| 日 K | 5 分钟 |
| 板块 | 5 分钟 |
| 新闻 | 10 分钟 |
| 公告 | 1 天 |
| 基础信息 | 1 天 |
| 财务快照 | 1 天 |

失败接口会进入 5 分钟失败冷却，避免每次分析都卡在同一个超时接口。失败冷却只缓存失败原因，不缓存假数据。

缓存目录：

```text
cache/
```

缓存默认不提交到 Git。

## 测试

```bash
.venv/bin/python -m pytest -q
```

当前验证结果：

```text
80 passed, 1 warning
```

`urllib3 NotOpenSSLWarning` 是 macOS 系统 Python 使用 LibreSSL 引起的警告，不影响当前功能运行。生产环境建议使用基于 OpenSSL 的 Python。

## 如何判断还可以优化什么

优先用这三条命令发现问题：

```bash
.venv/bin/stock-assistant data report 002415 --profile quick
.venv/bin/stock-assistant data health 002415 --provider astock --profile full
.venv/bin/stock-assistant close-review --live
```

观察重点：

- `fail` 接口是否集中在同一来源
- 是否出现大量 `数据限制`
- live 分析是否超过 30 秒
- 公告/新闻是否重复或过旧
- 板块强弱是否来自真实数据源，若缺失是否已明确提示
- 研报/公告是否成功进入知识库候选

## 后续优化建议

### 高优先级

- 增加数据源状态仪表盘，展示接口成功率、失败原因、缓存命中率
- 对公告、新闻、研报做更强的摘要抽取和事件分类
- 对风险提示按时间、严重度、来源可信度排序
- 为热点题材增加稳定备用源，减少同花顺热点超时影响

### 中优先级

- 增加批量 watchlist 分析
- 增加组合级行业暴露、风格暴露和相关性估计
- 将知识图谱候选自动分层：观察、验证、核心事实、过期事实
- 给 `data health --profile full` 增加并发和超时上限

### 低优先级

- 增加 Web UI 或本地仪表盘
- 增加报告模板配置
- 增加导出 Excel/HTML/PDF
- 增加自动化每日定时复盘

## 项目结构

```text
stock_assistant/
  analyzers/        分析器：技术、基本面、估值、风险、公告、资金流
  data_sources/     a-stock-data 和 AkShare 适配器
  providers/        a-stock-data 直连实现
  workflows/        个股分析、盘前盘后、行业、组合、交易复盘
  knowledge/        动态知识库和知识图谱
  decision/         决策和仓位建议
  storage/          本地交易日志
config/             行业链、公司标签、风险规则、观察池
skills/             Skill 文档
tests/              测试
```

## 安全声明

本项目不会自动下单，不建议满仓、融资或借钱交易。任何分析结果都只是研究辅助，实际投资决策需自行承担风险。
