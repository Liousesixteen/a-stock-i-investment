---
name: a-stock-stock-analysis
description: 单只 A 股综合分析、持仓诊断、买卖计划、风险控制与仓位建议。默认包含产业链定位，支持 quick / standard / deep。
---

# A 股个股分析

使用当前项目的 Python CLI：

```bash
stock-assistant analyze SYMBOL --mode quick
stock-assistant analyze SYMBOL --mode standard
```

## 边界

- 只做研究辅助和决策辅助。
- 不自动下单。
- 不承诺收益。
- 不鼓励满仓、融资或借钱交易。

## 输出要求

报告必须包含核心结论、大盘状态、板块/产业链定位、技术趋势、支撑压力、风险等级、仓位建议、止损参考和反向失效条件。
