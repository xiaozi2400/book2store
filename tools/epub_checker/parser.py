"""EPUBCheck JSON 输出解析。"""
from __future__ import annotations

import json
from pathlib import Path

from .models import CheckResult, Issue, Severity


def parse_epubcheck_output(json_text: str, epub_path: Path) -> CheckResult:
    """把 EPUBCheck 的 --json 输出扁平化为 CheckResult。

    处理：
    - JSON 损坏 → 返回空结果 + 保留原文到 raw_output
    - locations 嵌套结构 → 扁平为 "path@line"
    - 缺失字段（rule_id, suggestion, locations）→ 用 None/空字符串
    - 缺失或非法 severity → 默认为 USAGE
    """
    base_counts = {s.value: 0 for s in Severity}

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        return CheckResult(
            epub_path=epub_path,
            epub_version="?",
            checker_version="?",
            issues=[],
            counts=base_counts,
            duration_ms=0,
            raw_output=json_text,
        )

    issues: list[Issue] = []
    for m in data.get("messages", []) or []:
        severity_str = m.get("severity", "USAGE")
        try:
            severity = Severity(severity_str)
        except ValueError:
            severity = Severity.USAGE

        # locations 是 {"<context>": [{"path": "...", "line": N}]}
        locs = m.get("locations") or {}
        location = ""
        if locs:
            first_list = next(iter(locs.values()), []) or []
            if first_list:
                first_loc = first_list[0] or {}
                location = first_loc.get("path", "") or ""
                if "line" in first_loc:
                    location += f"@{first_loc['line']}"

        issues.append(Issue(
            severity=severity,
            message=m.get("message", "") or "",
            location=location,
            rule_id=m.get("ID"),
            suggestion=m.get("hint"),
        ))

    counts = dict(base_counts)
    for issue in issues:
        counts[issue.severity.value] += 1

    return CheckResult(
        epub_path=epub_path,
        epub_version=str( (data.get("publication") or {}).get("ePubVersion") or "?" ),
        checker_version=str( (data.get("checker") or {}).get("checkerVersion") or "?" ),
        issues=issues,
        counts=counts,
        duration_ms=(data.get("checker") or {}).get("elapsedTime", 0) or 0,
        raw_output=None,
    )
