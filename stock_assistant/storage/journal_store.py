from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List


class JournalStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or os.environ.get("STOCK_ASSISTANT_DB", "~/.stock_assistant/stock_assistant.db")).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_date TEXT DEFAULT CURRENT_DATE,
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
                )
                """
            )

    def add_trade(self, symbol: str, action: str, price: float, quantity: int, reason: str = "", name: str = "") -> int:
        amount = price * quantity
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO trades(symbol, name, action, price, quantity, amount, reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (symbol, name, action, price, quantity, amount, reason),
            )
            return int(cursor.lastrowid)

    def list_trades(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM trades ORDER BY id DESC LIMIT 50").fetchall()
        return [dict(row) for row in rows]
