from __future__ import annotations

from stock_assistant.storage.journal_store import JournalStore


class TradeReviewWorkflow:
    def __init__(self, store: JournalStore | None = None) -> None:
        self.store = store or JournalStore()

    def render_list(self) -> str:
        trades = self.store.list_trades()
        if not trades:
            return "# 交易记录\n\n暂无交易记录"
        lines = ["# 交易记录", ""]
        for trade in trades:
            lines.append(
                f"- #{trade['id']} {trade['trade_date']} {trade['symbol']} {trade['action']} {trade['price']} x {trade['quantity']}：{trade.get('reason') or ''}"
            )
        return "\n".join(lines)

    def render_review(self) -> str:
        trades = self.store.list_trades()
        total = len(trades)
        unplanned = sum(1 for trade in trades if not trade.get("reason"))
        return f"""# 交易复盘

## 统计

- 交易笔数：{total}
- 无明确理由交易：{unplanned}

## 高频错误

{self._mistake_text(unplanned)}

## 交易纪律

每笔交易必须有买入理由、失效条件、止损参考和仓位上限；亏损后不情绪化加仓。
"""

    def _mistake_text(self, unplanned: int) -> str:
        if unplanned:
            return "- 存在无计划交易，需要先写交易计划再执行"
        return "- 暂未发现无计划交易；继续检查是否按止损和仓位纪律执行"
