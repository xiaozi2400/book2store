"""数据模型。"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(str, Enum):
    """问题严重等级。EPUBCheck 的 FATAL > ERROR > WARNING > USAGE。"""
    FATAL = "FATAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    USAGE = "USAGE"


@dataclass
class Issue:
    """单条检查问题。"""
    severity: Severity
    message: str
    location: str
    rule_id: str | None = None
    suggestion: str | None = None


@dataclass
class CheckResult:
    """一次完整检查的结果。"""
    epub_path: Path
    epub_version: str
    checker_version: str
    issues: list[Issue]
    counts: dict[str, int]
    duration_ms: int
    raw_output: str | None = None

    @property
    def passed(self) -> bool:
        """FATAL=0 且 ERROR=0 算通过。WARNING/USAGE 不影响通过判定（除非 --strict）。"""
        return self.counts.get("FATAL", 0) == 0 and self.counts.get("ERROR", 0) == 0

    @property
    def by_severity(self) -> dict[Severity, list[Issue]]:
        """按严重等级分组。"""
        out: dict[Severity, list[Issue]] = {s: [] for s in Severity}
        for issue in self.issues:
            out[issue.severity].append(issue)
        return out

    def to_dict(self) -> dict[str, Any]:
        """序列化为可 JSON 化的字典。"""
        d = asdict(self)
        d["epub_path"] = self.epub_path.as_posix()
        d["issues"] = [
            {**asdict(i), "severity": i.severity.value} for i in self.issues
        ]
        return d
