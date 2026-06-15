"""JSON 解析单元测试。"""
import json
from pathlib import Path

from epub_checker.models import Severity
from epub_checker.parser import parse_epubcheck_output


def test_parse_real_sample(tmp_path):
    sample = Path(__file__).parent / "fixtures" / "epubcheck_sample.json"
    result = parse_epubcheck_output(sample.read_text(encoding="utf-8"), tmp_path / "b.epub")

    assert result.epub_version == "3.3"
    assert result.checker_version == "5.0.0"
    assert len(result.issues) == 4

    # counts
    assert result.counts == {"FATAL": 1, "ERROR": 2, "WARNING": 1, "USAGE": 0}
    assert result.passed is False

    # 严重等级分布
    by_sev = result.by_severity
    assert len(by_sev[Severity.ERROR]) == 2
    assert len(by_sev[Severity.WARNING]) == 1
    assert len(by_sev[Severity.FATAL]) == 1

    # 字段映射
    opf018 = by_sev[Severity.ERROR][0]
    assert opf018.rule_id == "OPF-018"
    assert "manifest" in opf018.message
    assert "OEBPS/package.opf" in opf018.location
    assert "@42" in opf018.location
    assert opf018.suggestion is not None

    # FATAL 没有 location
    fatal = by_sev[Severity.FATAL][0]
    assert fatal.location == ""

    # WARNING 没有 line 号
    warn = by_sev[Severity.WARNING][0]
    assert "@" not in warn.location
    assert warn.suggestion is not None


def test_parse_empty_messages(tmp_path):
    text = json.dumps({"epubVersion": "3.3", "checkerVersion": "5.0.0", "messages": []})
    result = parse_epubcheck_output(text, tmp_path / "b.epub")
    assert result.issues == []
    assert result.counts == {"FATAL": 0, "ERROR": 0, "WARNING": 0, "USAGE": 0}
    assert result.passed is True


def test_parse_invalid_json_keeps_raw_output(tmp_path):
    garbage = "not json at all"
    result = parse_epubcheck_output(garbage, tmp_path / "b.epub")
    assert result.issues == []
    assert result.raw_output == garbage
    assert result.passed is True


def test_parse_missing_fields_use_defaults(tmp_path):
    text = json.dumps({
        "epubVersion": "3.0",
        "checkerVersion": "4.0.0",
        "messages": [
            {"severity": "USAGE", "message": "weird message"}
        ]
    })
    result = parse_epubcheck_output(text, tmp_path / "b.epub")
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.severity == Severity.USAGE
    assert issue.message == "weird message"
    assert issue.location == ""
    assert issue.rule_id is None
    assert issue.suggestion is None


def test_parse_unknown_severity_falls_back_to_usage(tmp_path):
    text = json.dumps({
        "epubVersion": "3.3", "checkerVersion": "5.0.0",
        "messages": [{"severity": "BOGUS", "message": "x"}]
    })
    result = parse_epubcheck_output(text, tmp_path / "b.epub")
    assert result.issues[0].severity == Severity.USAGE
    assert result.counts["USAGE"] == 1
