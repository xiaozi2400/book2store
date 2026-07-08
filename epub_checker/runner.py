"""subprocess 封装。"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .config import Config
from .discovery import _resolve_epubcheck_cmd


def run_epubcheck(
    epub_path: Path,
    config: Config,
    *,
    profile: str | None = None,
    mode: str | None = None,
) -> tuple[int, str]:
    """调用 epubcheck 处理一个 EPUB 文件，返回 (returncode, stdout)。

    stdout 是 JSON 字符串；epubcheck 在有 ERROR 时仍可能输出 JSON，但 returncode 非零。
    """
    cmd_prefix = _resolve_epubcheck_cmd(config)
    cmd = [
        *cmd_prefix,
        str(epub_path),
        "--mode", mode or config.default_mode,
        "--profile", profile or config.default_profile,
        "--json", "-",
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=config.timeout_seconds,
    )
    return proc.returncode, proc.stdout
