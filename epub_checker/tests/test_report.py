"""报告渲染单元测试。"""
import io
import json
from pathlib import Path

from rich.console import Console

from epub_checker.models import CheckResult, Issue, Severity
from epub_checker.report import render_console, render_json, render_markdown


def _sample_result(tmp_path: Path, passed: bool = True) -> CheckResult:
    issues = [
        Issue(severity=Severity.ERROR, message="OPF problem", location="OEBPS/package.opf@42",
              rule_id="OPF-018", suggestion="Add manifest item"),
        Issue(severity=Severity.WARNING, message="Missing metadata", location="OEBPS/package.opf",
              rule_id="OPF-097", suggestion="Add accessibility metadata"),
    ]
    return CheckResult(
        epub_path=tmp_path / "book.epub",
        epub_version="3.3",
        checker_version="5.0.0",
        issues=[] if passed else issues,
        counts={"FATAL": 0, "ERROR": 0 if passed else 1, "WARNING": 0 if passed else 1, "USAGE": 0},
        duration_ms=1420,
        raw_output=None,
    )


def test_render_json_is_parseable(tmp_path):
    result = _sample_result(tmp_path, passed=False)
    out = render_json(result)
    data = json.loads(out)
    assert data["epub_version"] == "3.3"
    assert data["checker_version"] == "5.0.0"
    assert data["counts"]["ERROR"] == 1
    assert len(data["issues"]) == 2
    issue0 = data["issues"][0]
    assert issue0["severity"] == "ERROR"
    assert issue0["rule_id"] == "OPF-018"
    assert "book.epub" in data["epub_path"]


def test_render_markdown_contains_key_sections(tmp_path):
    result = _sample_result(tmp_path, passed=False)
    md = render_markdown(result, strict=False)
    assert "# EPUB Quality Report" in md
    assert "EPUB 3.3" in md
    assert "EPUBCheck 5.0.0" in md
    assert "| FATAL |" in md
    assert "| ERROR |" in md
    assert "| WARNING |" in md
    assert "OPF-018" in md
    assert "Add manifest item" in md
    assert "FAIL" in md


def test_render_markdown_pass_banner(tmp_path):
    result = _sample_result(tmp_path, passed=True)
    md = render_markdown(result, strict=False)
    assert "PASS" in md
    assert "FAIL" not in md


def test_render_markdown_strict_warning(tmp_path):
    """--strict 模式下仅 WARNING 也算不通过"""
    result = CheckResult(
        epub_path=tmp_path / "book.epub",
        epub_version="3.3",
        checker_version="5.0.0",
        issues=[Issue(severity=Severity.WARNING, message="w", location="l")],
        counts={"FATAL": 0, "ERROR": 0, "WARNING": 1, "USAGE": 0},
        duration_ms=100,
        raw_output=None,
    )
    md = render_markdown(result, strict=True)
    assert "FAIL" in md


def test_render_console_contains_status(tmp_path):
    result = _sample_result(tmp_path, passed=False)
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=120)
    render_console(result, strict=False, console=console)
    output = buf.getvalue()
    assert "EPUB" in output
    assert "ERROR" in output
    assert "WARNING" in output
    assert "FAIL" in output


def test_render_console_pass_shows_pass(tmp_path):
    result = _sample_result(tmp_path, passed=True)
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=120)
    render_console(result, strict=False, console=console)
    output = buf.getvalue()
    assert "PASS" in output
