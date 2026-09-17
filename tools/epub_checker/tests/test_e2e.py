"""端到端集成测试——需要本机已装 epubcheck 与 Java。
通过环境变量 SKIP_EPUBCHECK_E2E=1 可跳过。"""
import json
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


def test_real_check_bad_content(tmp_path):
    """冒烟：对坏文件运行（不崩溃，输出结构化结果）"""
    fake = tmp_path / "fake.epub"
    fake.write_bytes(b"not a real epub\x00\x01\x02")
    result = runner.invoke(app, ["check", str(fake), "--json"])
    assert result.exit_code == 0  # epubcheck 5.3.0 对不可解析文件报空结果
    data = json.loads(result.stdout)
    assert "epub_path" in data
    assert "checker_version" in data
    assert "issues" in data


def test_real_version_cmd():
    """version 命令在装好 epubcheck 时打印版本"""
    result = runner.invoke(app, ["version"])
    assert "epub-checker" in result.stdout.lower() or "epubcheck" in result.stdout.lower()
