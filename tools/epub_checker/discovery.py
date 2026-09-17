"""epubcheck 可执行文件定位。"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from .config import Config


class EpubCheckNotFound(Exception):
    """找不到 epubcheck 可执行文件时抛出。"""


def _resolve_epubcheck_cmd(config: Config) -> list[str]:
    """定位 epubcheck 命令。返回完整的命令行前缀。

    优先级：
    1. config.epubcheck_path 指向 .jar → 返回 ["java", *java_opts, "-jar", "<jar>"]
       其它情况 → 返回 ["<path>"]
    2. PATH 中的 epubcheck（POSIX）
    3. PATH 中的 epubcheck.bat（Windows）
    4. 都找不到 → 抛 EpubCheckNotFound
    """
    # 1) 显式配置
    if config.epubcheck_path:
        p = Path(config.epubcheck_path)
        if p.suffix.lower() == ".jar":
            return ["java", *config.java_opts, "-jar", str(p)]
        return [str(p)]

    # 2/3) PATH 查找
    candidates = ["epubcheck"]
    if sys.platform == "win32":
        candidates.append("epubcheck.bat")

    for name in candidates:
        found = shutil.which(name)
        if found:
            if found.lower().endswith(".jar"):
                return ["java", *config.java_opts, "-jar", found]
            return [found]

    raise EpubCheckNotFound(
        "找不到 epubcheck 可执行文件。\n"
        "  - macOS:   brew install epubcheck\n"
        "  - Ubuntu:  sudo apt install epubcheck\n"
        "  - Windows: scoop install epubcheck 或手动下载 https://github.com/w3c/epubcheck/releases\n"
        "  - 或在 config.yaml 设置 epub_checker.epubcheck_path"
    )
