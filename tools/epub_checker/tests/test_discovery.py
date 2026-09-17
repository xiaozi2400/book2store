"""命令发现单元测试。"""
import os
import sys

import pytest

from epub_checker.config import Config
from epub_checker.discovery import EpubCheckNotFound, _resolve_epubcheck_cmd


def test_resolve_uses_jar_config(tmp_path):
    jar = tmp_path / "ec.jar"
    jar.write_bytes(b"")
    cfg = Config(epubcheck_path=str(jar))
    cmd = _resolve_epubcheck_cmd(cfg)
    assert cmd[0] == "java"
    # java_opts 在 java 与 -jar 之间
    assert "-jar" in cmd
    assert cmd[cmd.index("-jar") + 1] == str(jar)


def test_resolve_uses_executable_config(tmp_path):
    exe = tmp_path / "my-epubcheck"
    exe.write_text("#!/bin/sh\n")
    cfg = Config(epubcheck_path=str(exe))
    cmd = _resolve_epubcheck_cmd(cfg)
    # .jar 后缀才会包成 java -jar，其它直接用
    assert cmd == [str(exe)]


def test_resolve_falls_back_to_path(tmp_path, monkeypatch):
    # Windows 上 .bat 走 PATHEXT；POSIX 直接用名字。
    if sys.platform == "win32":
        fake = tmp_path / "epubcheck.bat"
    else:
        fake = tmp_path / "epubcheck"
    fake.write_text("#!/bin/sh\n" if sys.platform != "win32" else "@echo off\n")
    monkeypatch.setenv("PATH", str(tmp_path))
    cfg = Config()
    cmd = _resolve_epubcheck_cmd(cfg)
    # 返回完整路径（spec 要求）
    name = os.path.basename(cmd[-1]).lower()
    assert name in ("epubcheck", "epubcheck.bat")


def test_resolve_finds_bat_on_windows(tmp_path, monkeypatch):
    bat = tmp_path / "epubcheck.bat"
    bat.write_text("@echo off\n")
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr("sys.platform", "win32")
    cfg = Config()
    cmd = _resolve_epubcheck_cmd(cfg)
    # Windows: shutil.which + PATHEXT 应能找到，返回完整路径
    name = os.path.basename(cmd[-1]).lower()
    assert name in ("epubcheck.bat", "epubcheck")


def test_resolve_raises_when_not_found(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))  # 空目录
    cfg = Config()
    with pytest.raises(EpubCheckNotFound) as exc_info:
        _resolve_epubcheck_cmd(cfg)
    assert "epubcheck" in str(exc_info.value).lower()
