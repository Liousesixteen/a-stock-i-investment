from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AnalysisResult:
    symbol: str
    name: str
    mode: str
    markdown: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    missing_data: List[Dict[str, str]] = field(default_factory=list)
