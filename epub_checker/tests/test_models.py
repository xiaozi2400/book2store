"""数据模型单元测试。"""
from pathlib import Path

from epub_checker.models import Severity, Issue, CheckResult


def test_severity_enum_values():
    assert Severity.FATAL.value == "FATAL"
    assert Severity.ERROR.value == "ERROR"
    assert Severity.WARNING.value == "WARNING"
    assert Severity.USAGE.value == "USAGE"


def test_issue_dataclass_fields():
    issue = Issue(
        severity=Severity.ERROR,
        message="Resource not declared",
        location="OEBPS/package.opf@42",
        rule_id="OPF-018",
        suggestion="Add manifest item",
    )
    assert issue.severity == Severity.ERROR
    assert issue.message == "Resource not declared"
    assert issue.location == "OEBPS/package.opf@42"
    assert issue.rule_id == "OPF-018"
    assert issue.suggestion == "Add manifest item"


def test_issue_optional_fields_default_none():
    issue = Issue(severity=Severity.USAGE, message="msg", location="loc")
    assert issue.rule_id is None
    assert issue.suggestion is None


def test_checkresult_passed_when_clean():
    result = CheckResult(
        epub_path=Path("book.epub"),
        epub_version="3.3",
        checker_version="5.0.0",
        issues=[],
        counts={"FATAL": 0, "ERROR": 0, "WARNING": 0, "USAGE": 0},
        duration_ms=100,
        raw_output=None,
    )
    assert result.passed is True


def test_checkresult_passed_fails_on_error():
    result = CheckResult(
        epub_path=Path("book.epub"),
        epub_version="3.3",
        checker_version="5.0.0",
        issues=[Issue(severity=Severity.ERROR, message="x", location="y")],
        counts={"FATAL": 0, "ERROR": 1, "WARNING": 0, "USAGE": 0},
        duration_ms=100,
        raw_output=None,
    )
    assert result.passed is False


def test_checkresult_passed_fails_on_fatal():
    result = CheckResult(
        epub_path=Path("book.epub"),
        epub_version="3.3",
        checker_version="5.0.0",
        issues=[Issue(severity=Severity.FATAL, message="x", location="y")],
        counts={"FATAL": 1, "ERROR": 0, "WARNING": 0, "USAGE": 0},
        duration_ms=100,
        raw_output=None,
    )
    assert result.passed is False


def test_checkresult_by_severity_groups_correctly():
    issues = [
        Issue(severity=Severity.ERROR, message="e1", location="l"),
        Issue(severity=Severity.WARNING, message="w1", location="l"),
        Issue(severity=Severity.ERROR, message="e2", location="l"),
    ]
    result = CheckResult(
        epub_path=Path("b.epub"),
        epub_version="3.3",
        checker_version="5.0.0",
        issues=issues,
        counts={"FATAL": 0, "ERROR": 2, "WARNING": 1, "USAGE": 0},
        duration_ms=0,
        raw_output=None,
    )
    grouped = result.by_severity
    assert len(grouped[Severity.ERROR]) == 2
    assert len(grouped[Severity.WARNING]) == 1
    assert len(grouped[Severity.FATAL]) == 0
    assert len(grouped[Severity.USAGE]) == 0


def test_checkresult_to_dict_serializes():
    result = CheckResult(
        epub_path=Path("/tmp/book.epub"),
        epub_version="3.3",
        checker_version="5.0.0",
        issues=[Issue(severity=Severity.ERROR, message="m", location="l",
                      rule_id="R-1", suggestion="fix")],
        counts={"FATAL": 0, "ERROR": 1, "WARNING": 0, "USAGE": 0},
        duration_ms=42,
        raw_output=None,
    )
    d = result.to_dict()
    assert d["epub_path"] == "/tmp/book.epub"
    assert d["epub_version"] == "3.3"
    assert d["issues"][0]["severity"] == "ERROR"
    assert d["issues"][0]["rule_id"] == "R-1"
