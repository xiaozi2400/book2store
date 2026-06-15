"""端到端集成测试——需要本机已装 epubcheck 与 Java。
通过环境变量 SKIP_EPUBCHECK_E2E=1 可跳过。"""
import os
import shutil

import pytest
from typer.testing import CliRunner

from epub_checker.main import app


runner = CliRunner()


pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_EPUBCHECK_E2E") == "1" or shutil.which("epubcheck") is None,
    reason="需要本机已装 epubcheck",
)


def test_real_cli_help():
    """CLI 帮助文本可访问"""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "check" in result.stdout


def test_real_check_empty_file(tmp_path):
    """最小冒烟：空文件当 epub（epubcheck 应报 FATAL）"""
    fake = tmp_path / "fake.epub"
    fake.write_bytes(b"")
    result = runner.invoke(app, ["check", str(fake)])
    # 空文件不合法
    assert result.exit_code != 0
    assert result.exit_code in (2, 3)  # ERROR or FATAL


def test_real_version_cmd():
    """version 命令在装好 epubcheck 时打印版本"""
    result = runner.invoke(app, ["version"])
    assert "epub-checker" in result.stdout.lower() or "epubcheck" in result.stdout.lower()
