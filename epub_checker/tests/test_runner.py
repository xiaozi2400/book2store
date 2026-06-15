"""subprocess 运行单元测试。所有 subprocess.run 都通过 monkeypatch mock。"""
import subprocess
from pathlib import Path

import pytest

from epub_checker.config import Config
from epub_checker.runner import run_epubcheck


def _completed(returncode: int, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_run_epubcheck_command_assembly(tmp_path, monkeypatch):
    """验证命令拼装：epubcheck 前缀 + epub 路径 + mode + profile + --json + -v 0"""
    fake = tmp_path / "ec"
    fake.write_text("#!/bin/sh\n")
    cfg = Config(epubcheck_path=str(fake))

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["timeout"] = kwargs.get("timeout")
        captured["text"] = kwargs.get("text")
        captured["capture_output"] = kwargs.get("capture_output")
        return _completed(0, stdout='{"messages": []}')

    monkeypatch.setattr("epub_checker.runner.subprocess.run", fake_run)

    book = tmp_path / "book.epub"
    book.write_bytes(b"PK\x03\x04dummy")
    rc, out = run_epubcheck(book, cfg, profile="dict", mode="mo")

    assert rc == 0
    assert out == '{"messages": []}'
    assert captured["cmd"][0] == str(fake)
    assert str(book) in captured["cmd"]
    assert "--mode" in captured["cmd"]
    assert "mo" in captured["cmd"]
    assert "--profile" in captured["cmd"]
    assert "dict" in captured["cmd"]
    assert "--json" in captured["cmd"]
    assert "-v" in captured["cmd"]
    assert "0" in captured["cmd"]
    assert captured["timeout"] == cfg.timeout_seconds
    assert captured["text"] is True
    assert captured["capture_output"] is True


def test_run_epubcheck_returns_returncode_and_stdout(tmp_path, monkeypatch):
    fake = tmp_path / "ec"
    fake.write_text("")
    cfg = Config(epubcheck_path=str(fake))

    def fake_run(cmd, **kwargs):
        return _completed(1, stdout='{"messages": [{"severity":"ERROR"}]}')

    monkeypatch.setattr("epub_checker.runner.subprocess.run", fake_run)

    rc, out = run_epubcheck(tmp_path / "book.epub", cfg)
    assert rc == 1
    assert "ERROR" in out


def test_run_epubcheck_timeout_propagates(tmp_path, monkeypatch):
    fake = tmp_path / "ec"
    fake.write_text("")
    cfg = Config(epubcheck_path=str(fake))

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=10)

    monkeypatch.setattr("epub_checker.runner.subprocess.run", fake_run)

    with pytest.raises(subprocess.TimeoutExpired):
        run_epubcheck(tmp_path / "book.epub", cfg)


def test_run_epubcheck_uses_config_defaults(tmp_path, monkeypatch):
    """未传 profile/mode 时使用 config 默认值"""
    fake = tmp_path / "ec"
    fake.write_text("")
    cfg = Config(epubcheck_path=str(fake), default_profile="edupub", default_mode="mo")

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _completed(0, stdout="{}")

    monkeypatch.setattr("epub_checker.runner.subprocess.run", fake_run)

    run_epubcheck(tmp_path / "book.epub", cfg)

    assert "edupub" in captured["cmd"]
    assert "mo" in captured["cmd"]
