"""Config 单元测试。"""
from pathlib import Path

from epub_checker.config import Config, DEFAULT_JAVA_OPTS


def test_default_config():
    cfg = Config()
    assert cfg.epubcheck_path is None
    assert cfg.java_opts == DEFAULT_JAVA_OPTS
    assert cfg.default_profile == "default"
    assert cfg.default_mode == "exp"
    assert cfg.timeout_seconds == 300


def test_config_from_missing_yaml_returns_defaults(tmp_path):
    cfg = Config.from_yaml(tmp_path / "nonexistent.yaml")
    assert cfg.epubcheck_path is None
    assert cfg.default_profile == "default"


def test_config_from_yaml_reads_section(tmp_path):
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(
        "epub_checker:\n"
        "  epubcheck_path: /opt/epubcheck.jar\n"
        "  java_opts: ['-Xmx2g']\n"
        "  default_profile: dict\n"
        "  timeout_seconds: 600\n",
        encoding="utf-8",
    )
    cfg = Config.from_yaml(yaml_path)
    assert cfg.epubcheck_path == "/opt/epubcheck.jar"
    assert cfg.java_opts == ["-Xmx2g"]
    assert cfg.default_profile == "dict"
    assert cfg.timeout_seconds == 600


def test_config_from_yaml_handles_missing_section(tmp_path):
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text("other_section:\n  foo: bar\n", encoding="utf-8")
    cfg = Config.from_yaml(yaml_path)
    # 没有 epub_checker 段时返回默认
    assert cfg.default_profile == "default"


def test_config_from_yaml_handles_invalid_yaml(tmp_path):
    yaml_path = tmp_path / "bad.yaml"
    yaml_path.write_text(":\n:\n  - [unbalanced", encoding="utf-8")
    cfg = Config.from_yaml(yaml_path)
    # 解析失败时返回默认
    assert cfg.epubcheck_path is None
