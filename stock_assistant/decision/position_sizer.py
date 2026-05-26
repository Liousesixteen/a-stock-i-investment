from __future__ import annotations

from typing import Dict


class PositionSizer:
    LIMITS = {"低": 20, "中": 12, "中高": 8, "高": 3, "极高": 0}

    def suggest(self, risk_level: str, decision: str) -> Dict[str, str]:
        max_pct = self.LIMITS.get(risk_level, 8)
        if decision in {"avoid", "watch"}:
            first = 0
            text = f"观察不建仓，总仓位上限参考 {max_pct}%"
        else:
            first = min(5, max_pct)
            text = f"首次仓位不超过 {first}%，总仓位不超过 {max_pct}%"
        return {
            "first_position": f"{first}%",
            "max_position": f"{max_pct}%",
            "text": text,
        }
