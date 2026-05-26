from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from stock_assistant.utils import clamp


class TechnicalAnalyzer:
    def analyze(self, bars: pd.DataFrame) -> Dict[str, Any]:
        if bars.empty or "close" not in bars:
            return {
                "technical_score": 50,
                "trend": "K线缺失",
                "signals": [],
                "warnings": ["K线缺失，无法判断技术趋势"],
                "support_levels": [],
                "resistance_levels": [],
                "stop_loss_reference": "等待补齐K线后再设置",
                "confidence": 0.2,
            }

        close = bars["close"].astype(float)
        latest = close.iloc[-1]
        ma5 = close.rolling(5).mean().iloc[-1]
        ma10 = close.rolling(10).mean().iloc[-1]
        ma20 = close.rolling(min(20, len(close))).mean().iloc[-1]
        recent_high = float(bars["high"].astype(float).tail(10).max())
        recent_low = float(bars["low"].astype(float).tail(10).min())

        score = 50
        signals = []
        warnings = []
        if latest > ma5:
            score += 8
            signals.append("收盘价站上5日均线")
        if latest > ma10:
            score += 8
            signals.append("收盘价站上10日均线")
        if latest > ma20:
            score += 10
            signals.append("收盘价站上阶段均线")
        if recent_high and latest / recent_high > 0.97:
            warnings.append("股价接近近期压力区，不宜追高")
            score -= 5

        trend = "技术面偏强" if score >= 68 else "技术面中性" if score >= 45 else "技术面偏弱"
        return {
            "technical_score": int(clamp(score)),
            "trend": trend,
            "signals": signals,
            "warnings": warnings,
            "support_levels": [round(recent_low, 2), round(ma10, 2)],
            "resistance_levels": [round(recent_high, 2), round(recent_high * 1.06, 2)],
            "stop_loss_reference": f"跌破 {round(min(recent_low, ma10), 2)} 且放量",
            "confidence": 0.75,
        }
