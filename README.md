# A 股投资分析决策助手

这是一个面向 A 股研究的命令行辅助工具。它把 `a-stock-data` 直连数据源、AkShare 备用数据源、风险规则、产业链知识库、动态知识图谱和报告工作流整合在一起，用于盘前/盘后复盘、个股分析、组合风险、交易复盘和知识库积累。

> 重要边界：本项目只做投资研究辅助，不自动下单，不承诺收益，不构成投资建议。所有输出都应结合个人风险承受能力和二次核验使用。

## 当前状态

已完成第一版可用成品：

- `a-stock-data` 全端点适配面，健康检查中 `unsupported = 0`
- AkShare 作为真实备用数据源
- live 个股分析、盘后复盘、数据源状态报告可运行
- TTL 缓存和失败冷却，避免重复等待慢接口
- 公告/新闻去重与近期过滤
- 动态知识库支持新闻、公告、研报入库
- 测试覆盖核心链路，当前为 `70 passed`

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
- 指数、北向资金、板块扩散等情绪驱动因子
- 最新消息雷达：利好、利空、中性/待验证、小道消息/传闻
- 国内政策、宏观数据、资金面、外围市场和微观结构跟踪清单
- 使用纪律：传闻不作为单独交易依据，情绪偏热降低追涨

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

主数据源顺序：

```text
a-stock-data 直连源
-> AkShare 同语义备用源
-> 本地知识库/配置补充
-> 样例降级数据
```

原则：

- 真实数据优先
- AkShare 用作备用兜底，不替代 `a-stock-data`
- 样例数据只保证流程不断，不伪装成实时数据
- 报告会在“数据限制”中说明缺失、降级或本地补充

已适配的数据层：

- 行情：腾讯、百度 K 线、mootdx、AkShare
- 研报：东财研报、PDF、同花顺 EPS、iwencai 入口
- 信号：同花顺热点、北向、资金流、龙虎榜、解禁、行业板块
- 资金面：两融、大宗交易、股东户数、分红、资金流
- 新闻：东财个股新闻、财联社、全球资讯
- 基础数据：东财、mootdx F10、Sina 三表、AkShare 财务指标
- 公告：巨潮、AkShare 公告

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
70 passed, 1 warning
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
- 板块强弱是否来自真实数据还是降级数据
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
