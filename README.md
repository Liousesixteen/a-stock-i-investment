# a-stock-investment

A 股投资分析决策 Skill 套件 MVP。项目复用 `a-stock-data` 作为数据底座，本仓库只负责分析、风控、仓位、决策和报告输出。

## MVP 命令

```bash
stock-assistant analyze 002415 --mode quick
stock-assistant analyze 002415 --mode standard
stock-assistant cache refresh-market
```

当前版本默认使用可降级的数据网关和内置样例数据，保证分析流程、报告结构和风控边界可测试。后续可以在 `AStockDataGateway` 中替换或扩展 live provider。

## 安全边界

本项目只做研究辅助和决策辅助，不自动下单，不承诺收益，不鼓励满仓、融资或借钱交易。
