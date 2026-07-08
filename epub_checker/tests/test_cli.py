"""CLI 单元测试。所有 epubcheck 调用通过 monkeypatch mock。"""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from epub_checker.config import Config
from epub_checker.discovery import EpubCheckNotFound
from epub_checker.main import app


runner = CliRunner()


def _stub_run(monkeypatch, json_text: str, returncode: int = 0):
    """让 main.run_epubcheck 返回指定 JSON。"""
    def fake_run(epub_path, config, *, profile=None, mode=None):
        return returncode, json_text
    monkeypatch.setattr("epub_checker.main.run_epubcheck", fake_run)


def _stub_resolve_ok(monkeypatch):
    monkeypatch.setattr("epub_checker.main._resolve_epubcheck_cmd", lambda c: ["ec"])


def test_cli_check_pass_exits_0(tmp_path, monkeypatch):
    _stub_resolve_ok(monkeypatch)
    _stub_run(monkeypatch, json.dumps(
        {"messages": [], "checker": {"checkerVersion": "5.0.0"}, "publication": {"ePubVersion": "3.3"}}
    ))
    book = tmp_path / "book.epub"
    book.write_bytes(b"PK\x03\x04")
    result = runner.invoke(app, ["check", str(book)])
    assert result.exit_code == 0


def test_cli_check_fatal_exits_3(tmp_path, monkeypatch):
    _stub_resolve_ok(monkeypatch)
    sample = Path(__file__).parent / "fixtures" / "epubcheck_sample.json"
    _stub_run(monkeypatch, sample.read_text(encoding="utf-8"), returncode=1)
    book = tmp_path / "book.epub"
    book.write_bytes(b"PK\x03\x04")
    result = runner.invoke(app, ["check", str(book)])
    # sample 含 1 FATAL + 2 ERROR + 1 WARNING，取最大 = 3
    assert result.exit_code == 3


def test_cli_check_warning_only_strict_exits_1(tmp_path, monkeypatch):
    _stub_resolve_ok(monkeypatch)
    _stub_run(monkeypatch, json.dumps({
        "messages": [{"severity": "WARNING", "message": "w", "locations": {}}],
        "checker": {"checkerVersion": "5.0.0"},
        "publication": {"ePubVersion": "3.3"}
    }))
    book = tmp_path / "book.epub"
    book.write_bytes(b"PK\x03\x04")
    result = runner.invoke(app, ["check", str(book), "--strict"])
    assert result.exit_code == 1


def test_cli_check_warning_only_non_strict_exits_0(tmp_path, monkeypatch):
    _stub_resolve_ok(monkeypatch)
    _stub_run(monkeypatch, json.dumps({
        "messages": [{"severity": "WARNING", "message": "w", "locations": {}}],
        "checker": {"checkerVersion": "5.0.0"},
        "publication": {"ePubVersion": "3.3"}
    }))
    book = tmp_path / "book.epub"
    book.write_bytes(b"PK\x03\x04")
    result = runner.invoke(app, ["check", str(book)])
    assert result.exit_code == 0


def test_cli_check_json_output(tmp_path, monkeypatch):
    _stub_resolve_ok(monkeypatch)
    _stub_run(monkeypatch, json.dumps({
        "messages": [{"severity": "WARNING", "message": "w", "locations": {}}],
        "checker": {"checkerVersion": "5.0.0"},
        "publication": {"ePubVersion": "3.3"}
    }))
    book = tmp_path / "book.epub"
    book.write_bytes(b"PK\x03\x04")
    result = runner.invoke(app, ["check", str(book), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["epub_version"] == "3.3"


def test_cli_check_md_output_writes_file(tmp_path, monkeypatch):
    _stub_resolve_ok(monkeypatch)
    _stub_run(monkeypatch, json.dumps(
        {"messages": [], "checker": {"checkerVersion": "5.0.0"}, "publication": {"ePubVersion": "3.3"}}
    ))
    book = tmp_path / "book.epub"
    book.write_bytes(b"PK\x03\x04")
    out = tmp_path / "report.md"
    result = runner.invoke(app, ["check", str(book), "--md", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert "EPUB Quality Report" in out.read_text(encoding="utf-8")


def test_cli_check_nonexistent_file(tmp_path, monkeypatch):
    _stub_resolve_ok(monkeypatch)
    result = runner.invoke(app, ["check", str(tmp_path / "nope.epub")])
    assert result.exit_code == 4


def test_cli_check_epubcheck_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr("epub_checker.main._resolve_epubcheck_cmd",
                        lambda c: (_ for _ in ()).throw(EpubCheckNotFound("missing")))
    book = tmp_path / "book.epub"
    book.write_bytes(b"PK\x03\x04")
    result = runner.invoke(app, ["check", str(book)])
    assert result.exit_code == 4


def test_cli_check_directory_batch(tmp_path, monkeypatch):
    """目录扫描 *.epub，任一失败即整批失败"""
    _stub_resolve_ok(monkeypatch)
    (tmp_path / "a.epub").write_bytes(b"PK\x03\x04")
    (tmp_path / "b.epub").write_bytes(b"PK\x03\x04")

    responses = [
        (0, json.dumps({"messages": [], "checker": {"checkerVersion": "5.0.0"}, "publication": {"ePubVersion": "3.3"}})),
        (1, json.dumps({
            "messages": [{"severity": "ERROR", "message": "x", "locations": {}}],
            "checker": {"checkerVersion": "5.0.0"},
            "publication": {"ePubVersion": "3.3"}
        })),
    ]

    def fake_run(epub_path, config, *, profile=None, mode=None):
        return responses.pop(0)

    monkeypatch.setattr("epub_checker.main.run_epubcheck", fake_run)

    result = runner.invoke(app, ["check", str(tmp_path)])
    # 第二个文件 ERROR → 退出码 2
    assert result.exit_code == 2


def test_cli_version_prints_something(tmp_path, monkeypatch):
    def fake_resolve(c):
        return ["fake-epubcheck"]
    monkeypatch.setattr("epub_checker.main._resolve_epubcheck_cmd", fake_resolve)

    import subprocess
    def fake_subprocess_run(cmd, **kwargs):
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="EPUBCheck v5.0.0", stderr="")

    monkeypatch.setattr("epub_checker.main.subprocess.run", fake_subprocess_run)

    # 让 Config.from_yaml 指向空路径，避免读真实 config.yaml
    monkeypatch.setattr("epub_checker.main.Config.from_yaml",
                        classmethod(lambda cls, p: Config()))

    result = runner.invoke(app, ["version"])
    assert "epub-checker" in result.stdout.lower() or "epubcheck" in result.stdout.lower()
