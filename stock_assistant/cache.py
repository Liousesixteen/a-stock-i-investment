from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from stock_assistant.utils import now_iso


class JsonCache:
    def __init__(self, root: str | Path = "cache") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "stock_snapshots").mkdir(exist_ok=True)

    def path_for(self, key: str) -> Path:
        safe = key.replace(":", "_").replace("/", "_")
        if safe.endswith(".json"):
            return self.root / safe
        return self.root / f"{safe}.json"

    def write(self, key: str, data: Any, ttl_seconds: int, source: str) -> Path:
        payload = {
            "generated_at": now_iso(),
            "ttl_seconds": ttl_seconds,
            "source": source,
            "is_stale": False,
            "data": data,
        }
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path

    def read(self, key: str) -> Optional[Dict[str, Any]]:
        path = self.path_for(key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def read_fresh(self, key: str) -> Optional[Dict[str, Any]]:
        payload = self.read(key)
        if not payload:
            return None
        generated_at = payload.get("generated_at")
        ttl_seconds = int(payload.get("ttl_seconds") or 0)
        if not generated_at or ttl_seconds <= 0:
            return None
        try:
            generated = datetime.fromisoformat(generated_at)
        except ValueError:
            return None
        if datetime.now() - generated > timedelta(seconds=ttl_seconds):
            payload["is_stale"] = True
            return None
        payload["is_stale"] = False
        return payload
