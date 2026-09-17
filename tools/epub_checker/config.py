"""配置：dataclass + 从 config.yaml 读取。"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_JAVA_OPTS = ["-Xmx1g"]
DEFAULT_PROFILE = "default"
DEFAULT_MODE = "exp"

logger = logging.getLogger("epub_checker.config")


@dataclass
class Config:
    """工具配置。所有字段都有默认值，可被 config.yaml 的 epub_checker 段覆盖。"""
    epubcheck_path: str | None = None  # None = 走 PATH
    java_opts: list[str] = field(default_factory=lambda: list(DEFAULT_JAVA_OPTS))
    default_profile: str = DEFAULT_PROFILE
    default_mode: str = DEFAULT_MODE
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "Config":
        """从 config.yaml 读取 epub_checker 段。读不到或文件不存在时返回默认配置。"""
        if not yaml_path.exists():
            return cls()
        try:
            import yaml  # 延迟导入，避免硬依赖
        except ImportError:
            return cls()
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            logger.warning("无法解析 %s: %s，使用默认配置", yaml_path, e)
            return cls()
        section = data.get("epub_checker", {}) or {}
        return cls(
            epubcheck_path=section.get("epubcheck_path"),
            java_opts=section.get("java_opts", list(DEFAULT_JAVA_OPTS)),
            default_profile=section.get("default_profile", DEFAULT_PROFILE),
            default_mode=section.get("default_mode", DEFAULT_MODE),
            timeout_seconds=section.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
        )
