from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from stock_assistant.utils import now_iso


class EvidenceStore:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or os.environ.get("STOCK_ASSISTANT_KNOWLEDGE_DIR", "data/knowledge"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.evidence_path = self.root / "evidence.jsonl"
        self.candidate_path = self.root / "candidates.jsonl"

    def add_evidence(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(evidence)
        payload.setdefault("created_at", now_iso())
        payload.setdefault("status", "observed")
        payload["id"] = payload.get("id") or self._id_for(payload, ["symbol", "source", "title", "text"])
        existing = {item["id"]: item for item in self.list_evidence()}
        if payload["id"] in existing:
            return existing[payload["id"]]
        self._append(self.evidence_path, payload)
        return payload

    def add_candidate(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(candidate)
        payload.setdefault("created_at", now_iso())
        payload.setdefault("status", "pending")
        payload["id"] = payload.get("id") or self._id_for(payload, ["symbol", "chain", "segment", "relation"])
        existing = {item["id"]: item for item in self.list_candidates()}
        if payload["id"] in existing:
            return existing[payload["id"]]
        self._append(self.candidate_path, payload)
        return payload

    def list_evidence(self) -> List[Dict[str, Any]]:
        return self._read_jsonl(self.evidence_path)

    def list_candidates(self, status: str | None = None) -> List[Dict[str, Any]]:
        rows = self._read_jsonl(self.candidate_path)
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return rows

    def update_candidate_status(self, candidate_id: str, status: str) -> Dict[str, Any]:
        rows = self.list_candidates()
        updated = {}
        for row in rows:
            if row.get("id") == candidate_id:
                row["status"] = status
                row["updated_at"] = now_iso()
                updated = row
        self._write_jsonl(self.candidate_path, rows)
        if not updated:
            raise ValueError(f"candidate not found: {candidate_id}")
        return updated

    def _append(self, path: Path, payload: Dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _read_jsonl(self, path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _write_jsonl(self, path: Path, rows: List[Dict[str, Any]]) -> None:
        path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8")

    def _id_for(self, payload: Dict[str, Any], keys: List[str]) -> str:
        raw = "|".join(str(payload.get(key, "")) for key in keys)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
