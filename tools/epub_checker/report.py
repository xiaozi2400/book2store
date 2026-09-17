"""报告渲染：Rich 控制台 + JSON + Markdown。"""
from __future__ import annotations

import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .models import CheckResult, Severity


_SEV_STYLE: dict[Severity, str] = {
    Severity.FATAL: "bold red",
    Severity.ERROR: "red",
    Severity.WARNING: "yellow",
    Severity.USAGE: "dim",
}


def _passed_strict(result: CheckResult, strict: bool) -> bool:
    """FATAL/ERROR 必失败；strict 时 WARNING 也算失败。"""
    if not result.passed:
        return False
    if strict and result.counts.get("WARNING", 0) > 0:
        return False
    return True


def render_console(
    result: CheckResult,
    strict: bool,
    *,
    console: Console | None = None,
) -> None:
    """Rich 终端表格输出。"""
    if console is None:
        console = Console()

    ok = _passed_strict(result, strict)

    header = (
        f"Book:     {result.epub_path}\n"
        f"Version:  EPUB {result.epub_version}\n"
        f"Checker:  EPUBCheck {result.checker_version}\n"
        f"Duration: {result.duration_ms / 1000:.2f} s"
    )
    console.print(Panel(header, title="EPUB Quality Check", border_style="cyan"))

    counts_table = Table(title="Issues by Severity", show_header=True)
    counts_table.add_column("Severity", style="bold")
    counts_table.add_column("Count", justify="right")
    for sev in Severity:
        n = result.counts.get(sev.value, 0)
        style = _SEV_STYLE.get(sev, "")
        counts_table.add_row(f"[{style}]{sev.value}[/{style}]", str(n))
    console.print(counts_table)

    if ok:
        console.print("[bold green]PASS[/bold green]")
    else:
        summary = (
            f"{result.counts.get('FATAL', 0)} fatal, "
            f"{result.counts.get('ERROR', 0)} error, "
            f"{result.counts.get('WARNING', 0)} warning"
        )
        console.print(f"[bold red]FAIL[/bold red] — {summary}")

    if result.issues:
        console.print()
        console.print("[bold]Top issues:[/bold]")
        for issue in result.issues[:20]:
            style = _SEV_STYLE.get(issue.severity, "")
            rule = f"[{issue.rule_id}] " if issue.rule_id else ""
            console.print(
                f"  [{style}]{issue.severity.value}[/{style}] "
                f"{rule}{issue.message}"
            )
            if issue.location:
                console.print(f"           @ {issue.location}")
            if issue.suggestion:
                console.print(f"           ↳ {issue.suggestion}")


def render_json(result: CheckResult) -> str:
    """JSON 字符串输出。"""
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)


def render_markdown(result: CheckResult, strict: bool) -> str:
    """Markdown 报告输出。"""
    ok = _passed_strict(result, strict)
    lines: list[str] = []
    lines.append(f"# EPUB Quality Report — {result.epub_path.name}")
    lines.append("")
    lines.append("## Metadata")
    lines.append("")
    lines.append(f"- **File**: `{result.epub_path}`")
    lines.append(f"- **EPUB Version**: EPUB {result.epub_version}")
    lines.append(f"- **Checker**: EPUBCheck {result.checker_version}")
    lines.append(f"- **Duration**: {result.duration_ms / 1000:.2f} s")
    lines.append("")
    lines.append("## Severity Counts")
    lines.append("")
    lines.append("| Severity | Count |")
    lines.append("|----------|------:|")
    for sev in Severity:
        lines.append(f"| {sev.value} | {result.counts.get(sev.value, 0)} |")
    lines.append("")
    status = "PASS" if ok else "FAIL"
    lines.append(f"## Verdict: **{status}**")
    lines.append("")
    if result.issues:
        lines.append("## Issues")
        lines.append("")
        for sev in Severity:
            bucket = [i for i in result.issues if i.severity == sev]
            if not bucket:
                continue
            lines.append(f"### {sev.value} ({len(bucket)})")
            lines.append("")
            for issue in bucket:
                lines.append(f"#### {issue.rule_id or '(no rule id)'}: {issue.message}")
                lines.append("")
                if issue.location:
                    lines.append(f"- **Location**: `{issue.location}`")
                if issue.suggestion:
                    lines.append(f"- **Fix**: {issue.suggestion}")
                lines.append("")
    return "\n".join(lines) + "\n"
