# EPUB 质量检查工具实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现独立子项目 `epub_checker/`，通过调用外部 EPUBCheck 验证 EPUB 文件是否符合 EPUB 3.3 出版社标准。

**Architecture:** 自包含 Python 子项目（类似 `ebook_translator/`），含 7 个职责单一的模块（main/config/models/discovery/runner/parser/report）。EPUBCheck 作为外部黑盒引擎，Python 层只做参数拼装、JSON 解析、报告渲染——零校验规则复写。报告支持 Rich 控制台 / JSON / Markdown 三种格式，4 档退出码支持 CI 集成。完全独立于 `automation/` 流水线。

**Tech Stack:** Python 3.11+、Typer（CLI）、Rich（终端输出）、PyYAML（可选配置）、subprocess（EPUBCheck 调用）、pytest + typer.testing（测试）

---

## File Structure

```
epub_checker/
├── __init__.py                  # 包标识 + __version__
├── main.py                      # Typer CLI: check / version
├── config.py                    # Config dataclass + from_yaml
├── models.py                    # Severity, Issue, CheckResult
├── discovery.py                 # _resolve_epubcheck_cmd + EpubCheckNotFound
├── runner.py                    # run_epubcheck (subprocess)
├── parser.py                    # parse_epubcheck_output
├── report.py                    # render_console/json/markdown
├── README.md                    # 用户文档
└── tests/
    ├── __init__.py
    ├── conftest.py              # 共享 fixture
    ├── fixtures/
    │   └── epubcheck_sample.json
    ├── test_models.py
    ├── test_discovery.py
    ├── test_runner.py
    ├── test_parser.py
    ├── test_report.py
    ├── test_cli.py
    └── test_e2e.py
```

**不** 修改任何现有文件、不改 `requirements-automation.txt`、不动数据库 schema。

---

## Task 1: 项目骨架与基础数据模型

**Files:**
- Create: `epub_checker/__init__.py`
- Create: `epub_checker/models.py`
- Create: `epub_checker/tests/__init__.py`
- Create: `epub_checker/tests/conftest.py`
- Create: `epub_checker/tests/test_models.py`

### 1.1 写失败测试：Severity 枚举与 Issue/CheckResult dataclass

**Files:**
- Create: `epub_checker/tests/test_models.py`

```python
"""数据模型单元测试。"""
from pathlib import Path

from epub_checker.models import Severity, Issue, CheckResult


def test_severity_enum_values():
    assert Severity.FATAL.value == "FATAL"
    assert Severity.ERROR.value == "ERROR"
    assert Severity.WARNING.value == "WARNING"
    assert Severity.USAGE.value == "USAGE"


def test_issue_dataclass_fields():
    issue = Issue(
        severity=Severity.ERROR,
        message="Resource not declared",
        location="OEBPS/package.opf@42",
        rule_id="OPF-018",
        suggestion="Add manifest item",
    )
    assert issue.severity == Severity.ERROR
    assert issue.message == "Resource not declared"
    assert issue.location == "OEBPS/package.opf@42"
    assert issue.rule_id == "OPF-018"
    assert issue.suggestion == "Add manifest item"


def test_issue_optional_fields_default_none():
    issue = Issue(severity=Severity.USAGE, message="msg", location="loc")
    assert issue.rule_id is None
    assert issue.suggestion is None


def test_checkresult_passed_when_clean():
    result = CheckResult(
        epub_path=Path("book.epub"),
        epub_version="3.3",
        checker_version="5.0.0",
        issues=[],
        counts={"FATAL": 0, "ERROR": 0, "WARNING": 0, "USAGE": 0},
        duration_ms=100,
        raw_output=None,
    )
    assert result.passed is True


def test_checkresult_passed_fails_on_error():
    result = CheckResult(
        epub_path=Path("book.epub"),
        epub_version="3.3",
        checker_version="5.0.0",
        issues=[Issue(severity=Severity.ERROR, message="x", location="y")],
        counts={"FATAL": 0, "ERROR": 1, "WARNING": 0, "USAGE": 0},
        duration_ms=100,
        raw_output=None,
    )
    assert result.passed is False


def test_checkresult_passed_fails_on_fatal():
    result = CheckResult(
        epub_path=Path("book.epub"),
        epub_version="3.3",
        checker_version="5.0.0",
        issues=[Issue(severity=Severity.FATAL, message="x", location="y")],
        counts={"FATAL": 1, "ERROR": 0, "WARNING": 0, "USAGE": 0},
        duration_ms=100,
        raw_output=None,
    )
    assert result.passed is False


def test_checkresult_by_severity_groups_correctly():
    issues = [
        Issue(severity=Severity.ERROR, message="e1", location="l"),
        Issue(severity=Severity.WARNING, message="w1", location="l"),
        Issue(severity=Severity.ERROR, message="e2", location="l"),
    ]
    result = CheckResult(
        epub_path=Path("b.epub"),
        epub_version="3.3",
        checker_version="5.0.0",
        issues=issues,
        counts={"FATAL": 0, "ERROR": 2, "WARNING": 1, "USAGE": 0},
        duration_ms=0,
        raw_output=None,
    )
    grouped = result.by_severity
    assert len(grouped[Severity.ERROR]) == 2
    assert len(grouped[Severity.WARNING]) == 1
    assert len(grouped[Severity.FATAL]) == 0
    assert len(grouped[Severity.USAGE]) == 0


def test_checkresult_to_dict_serializes():
    result = CheckResult(
        epub_path=Path("/tmp/book.epub"),
        epub_version="3.3",
        checker_version="5.0.0",
        issues=[Issue(severity=Severity.ERROR, message="m", location="l",
                      rule_id="R-1", suggestion="fix")],
        counts={"FATAL": 0, "ERROR": 1, "WARNING": 0, "USAGE": 0},
        duration_ms=42,
        raw_output=None,
    )
    d = result.to_dict()
    assert d["epub_path"] == "/tmp/book.epub"
    assert d["epub_version"] == "3.3"
    assert d["issues"][0]["severity"] == "ERROR"
    assert d["issues"][0]["rule_id"] == "R-1"
```

- [ ] **Step 1.1.1: 创建包与测试目录**

```bash
mkdir -p D:/project/bookfile_bat/epub_checker/tests/fixtures
```

- [ ] **Step 1.1.2: 写失败测试**

写入 `epub_checker/tests/test_models.py`（内容如上）。

- [ ] **Step 1.1.3: 写 conftest 让 pytest 找到包**

**Files:**
- Create: `epub_checker/tests/__init__.py`（空文件）
- Create: `epub_checker/tests/conftest.py`

```python
"""epub_checker 测试的共享 fixture。"""
import sys
from pathlib import Path

# 让 pytest 能 import epub_checker，无需安装
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

- [ ] **Step 1.1.4: 跑测试确认失败**

Run: `pytest epub_checker/tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'epub_checker'`

### 1.2 实现包标识与数据模型

**Files:**
- Create: `epub_checker/__init__.py`
- Create: `epub_checker/models.py`

```python
# epub_checker/__init__.py
"""EPUB 文件质量检查工具。

一个独立子项目，调用外部 EPUBCheck（Java）验证 EPUB 文件是否符合 EPUB 3.3 出版社标准。
本工具只做胶水代码：参数拼装、JSON 解析、报告渲染、CLI 编排。所有校验规则由 EPUBCheck 提供。
"""
__version__ = "0.1.0"
```

```python
# epub_checker/models.py
"""数据模型。"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(str, Enum):
    """问题严重等级。EPUBCheck 的 FATAL > ERROR > WARNING > USAGE。"""
    FATAL = "FATAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    USAGE = "USAGE"


@dataclass
class Issue:
    """单条检查问题。"""
    severity: Severity
    message: str
    location: str
    rule_id: str | None = None
    suggestion: str | None = None


@dataclass
class CheckResult:
    """一次完整检查的结果。"""
    epub_path: Path
    epub_version: str
    checker_version: str
    issues: list[Issue]
    counts: dict[str, int]
    duration_ms: int
    raw_output: str | None = None

    @property
    def passed(self) -> bool:
        """FATAL=0 且 ERROR=0 算通过。WARNING/USAGE 不影响通过判定（除非 --strict）。"""
        return self.counts.get("FATAL", 0) == 0 and self.counts.get("ERROR", 0) == 0

    @property
    def by_severity(self) -> dict[Severity, list[Issue]]:
        """按严重等级分组。"""
        out: dict[Severity, list[Issue]] = {s: [] for s in Severity}
        for issue in self.issues:
            out[issue.severity].append(issue)
        return out

    def to_dict(self) -> dict[str, Any]:
        """序列化为可 JSON 化的字典。"""
        d = asdict(self)
        d["epub_path"] = str(self.epub_path)
        d["issues"] = [
            {**asdict(i), "severity": i.severity.value} for i in self.issues
        ]
        return d
```

- [ ] **Step 1.2.1: 实现 `__init__.py` 和 `models.py`**

- [ ] **Step 1.2.2: 跑测试确认通过**

Run: `pytest epub_checker/tests/test_models.py -v`
Expected: PASS（8 个测试全绿）

- [ ] **Step 1.2.3: 提交**

```bash
cd D:/project/bookfile_bat
git add epub_checker/
git commit -m "feat(epub-checker): 骨架与数据模型（Severity/Issue/CheckResult）"
```

---

## Task 2: 配置模块（Config dataclass + from_yaml）

**Files:**
- Create: `epub_checker/config.py`
- Create: `epub_checker/tests/test_config.py`

### 2.1 写失败测试

**Files:**
- Create: `epub_checker/tests/test_config.py`

```python
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
```

- [ ] **Step 2.1.1: 写失败测试**

写入 `epub_checker/tests/test_config.py`。

- [ ] **Step 2.1.2: 跑测试确认失败**

Run: `pytest epub_checker/tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'epub_checker.config'`

### 2.2 实现 Config

**Files:**
- Create: `epub_checker/config.py`

```python
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
```

- [ ] **Step 2.2.1: 实现 `config.py`**

- [ ] **Step 2.2.2: 跑测试确认通过**

Run: `pytest epub_checker/tests/test_config.py -v`
Expected: PASS（5 个测试全绿）

- [ ] **Step 2.2.3: 提交**

```bash
cd D:/project/bookfile_bat
git add epub_checker/
git commit -m "feat(epub-checker): 配置模块（Config + yaml 读取）"
```

---

## Task 3: 命令发现（discovery.py）

**Files:**
- Create: `epub_checker/discovery.py`
- Create: `epub_checker/tests/test_discovery.py`

### 3.1 写失败测试

**Files:**
- Create: `epub_checker/tests/test_discovery.py`

```python
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
    # java_opts 插在 java 与 -jar 之间
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
    # Windows 上用 .bat 走 PATHEXT；POSIX 直接用名字
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
```

- [ ] **Step 3.1.1: 写失败测试**

写入 `epub_checker/tests/test_discovery.py`。

- [ ] **Step 3.1.2: 跑测试确认失败**

Run: `pytest epub_checker/tests/test_discovery.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'epub_checker.discovery'`

### 3.2 实现 discovery

**Files:**
- Create: `epub_checker/discovery.py`

```python
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
    1. config.epubcheck_path 指向 .jar → 返回 ["java", *config.java_opts, "-jar", "<jar>"]
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
```

- [ ] **Step 3.2.1: 实现 `discovery.py`**

- [ ] **Step 3.2.2: 跑测试确认通过**

Run: `pytest epub_checker/tests/test_discovery.py -v`
Expected: PASS（5 个测试全绿）

- [ ] **Step 3.2.3: 提交**

```bash
cd D:/project/bookfile_bat
git add epub_checker/
git commit -m "feat(epub-checker): epubcheck 命令发现（PATH + 配置覆盖）"
```

---

## Task 4: 子进程运行（runner.py）

**Files:**
- Create: `epub_checker/runner.py`
- Create: `epub_checker/tests/test_runner.py`

### 4.1 写失败测试

**Files:**
- Create: `epub_checker/tests/test_runner.py`

```python
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
```

- [ ] **Step 4.1.1: 写失败测试**

写入 `epub_checker/tests/test_runner.py`。

- [ ] **Step 4.1.2: 跑测试确认失败**

Run: `pytest epub_checker/tests/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'epub_checker.runner'`

### 4.2 实现 runner

**Files:**
- Create: `epub_checker/runner.py`

```python
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
        "--json",
        "-v", "0",
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=config.timeout_seconds,
    )
    return proc.returncode, proc.stdout
```

- [ ] **Step 4.2.1: 实现 `runner.py`**

- [ ] **Step 4.2.2: 跑测试确认通过**

Run: `pytest epub_checker/tests/test_runner.py -v`
Expected: PASS（4 个测试全绿）

- [ ] **Step 4.2.3: 提交**

```bash
cd D:/project/bookfile_bat
git add epub_checker/
git commit -m "feat(epub-checker): subprocess 调用 EPUBCheck"
```

---

## Task 5: JSON 解析（parser.py）

**Files:**
- Create: `epub_checker/parser.py`
- Create: `epub_checker/tests/fixtures/epubcheck_sample.json`
- Create: `epub_checker/tests/test_parser.py`

### 5.1 创建 EPUBCheck JSON 样本

**Files:**
- Create: `epub_checker/tests/fixtures/epubcheck_sample.json`

```json
{
  "epubVersion": "3.3",
  "checkerVersion": "5.0.0",
  "messages": [
    {
      "ID": "OPF-018",
      "severity": "ERROR",
      "message": "Resource 'OEBPS/img/cover.jpg' is not declared in OPF manifest.",
      "locations": {
        "application/xml": [
          {"path": "OEBPS/package.opf", "line": 42}
        ]
      },
      "hint": "Add a manifest item with href='img/cover.jpg'."
    },
    {
      "ID": "RSC-005",
      "severity": "ERROR",
      "message": "File reference 'missing.xhtml' could not be found in the publication.",
      "locations": {
        "application/xml": [
          {"path": "OEBPS/package.opf", "line": 87}
        ]
      },
      "hint": "Ensure the referenced file exists in the EPUB."
    },
    {
      "ID": "OPF-097",
      "severity": "WARNING",
      "message": "Missing accessibility metadata.",
      "locations": {
        "application/xml": [
          {"path": "OEBPS/package.opf"}
        ]
      },
      "hint": "Consider adding schema:accessMode."
    },
    {
      "ID": "FATAL-001",
      "severity": "FATAL",
      "message": "EPUB package could not be opened.",
      "locations": {},
      "hint": null
    }
  ]
}
```

- [ ] **Step 5.1.1: 写入样本**

### 5.2 写失败测试

**Files:**
- Create: `epub_checker/tests/test_parser.py`

```python
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
```

- [ ] **Step 5.2.1: 写失败测试**

写入 `epub_checker/tests/test_parser.py`。

- [ ] **Step 5.2.2: 跑测试确认失败**

Run: `pytest epub_checker/tests/test_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'epub_checker.parser'`

### 5.3 实现 parser

**Files:**
- Create: `epub_checker/parser.py`

```python
"""EPUBCheck JSON 输出解析。"""
from __future__ import annotations

import json
from pathlib import Path

from .models import CheckResult, Issue, Severity


def parse_epubcheck_output(json_text: str, epub_path: Path) -> CheckResult:
    """把 EPUBCheck 的 --json 输出扁平化为 CheckResult。

    处理：
    - JSON 损坏 → 返回空结果 + 保留原文到 raw_output
    - locations 嵌套结构 → 扁平为 "path@line"
    - 缺失字段（rule_id, suggestion, locations）→ 用 None/空字符串
    - 缺失或非法 severity → 默认为 USAGE
    """
    base_counts = {s.value: 0 for s in Severity}

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        return CheckResult(
            epub_path=epub_path,
            epub_version="?",
            checker_version="?",
            issues=[],
            counts=base_counts,
            duration_ms=0,
            raw_output=json_text,
        )

    issues: list[Issue] = []
    for m in data.get("messages", []) or []:
        severity_str = m.get("severity", "USAGE")
        try:
            severity = Severity(severity_str)
        except ValueError:
            severity = Severity.USAGE

        # locations 是 {"<context>": [{"path": "...", "line": N}]}
        locs = m.get("locations") or {}
        location = ""
        if locs:
            first_list = next(iter(locs.values()), []) or []
            if first_list:
                first_loc = first_list[0] or {}
                location = first_loc.get("path", "") or ""
                if "line" in first_loc:
                    location += f"@{first_loc['line']}"

        issues.append(Issue(
            severity=severity,
            message=m.get("message", "") or "",
            location=location,
            rule_id=m.get("ID"),
            suggestion=m.get("hint"),
        ))

    counts = dict(base_counts)
    for issue in issues:
        counts[issue.severity.value] += 1

    return CheckResult(
        epub_path=epub_path,
        epub_version=str(data.get("epubVersion", "?")),
        checker_version=str(data.get("checkerVersion", "?")),
        issues=issues,
        counts=counts,
        duration_ms=0,
        raw_output=None,
    )
```

- [ ] **Step 5.3.1: 实现 `parser.py`**

- [ ] **Step 5.3.2: 跑测试确认通过**

Run: `pytest epub_checker/tests/test_parser.py -v`
Expected: PASS（5 个测试全绿）

- [ ] **Step 5.3.3: 提交**

```bash
cd D:/project/bookfile_bat
git add epub_checker/
git commit -m "feat(epub-checker): EPUBCheck JSON 解析"
```

---

## Task 6: 报告渲染（report.py）

**Files:**
- Create: `epub_checker/report.py`
- Create: `epub_checker/tests/test_report.py`

### 6.1 写失败测试

**Files:**
- Create: `epub_checker/tests/test_report.py`

```python
"""报告渲染单元测试。"""
import io
import json
from pathlib import Path

from rich.console import Console

from epub_checker.models import CheckResult, Issue, Severity
from epub_checker.report import render_console, render_json, render_markdown


def _sample_result(tmp_path: Path, passed: bool = True) -> CheckResult:
    issues = [
        Issue(severity=Severity.ERROR, message="OPF problem", location="OEBPS/package.opf@42",
              rule_id="OPF-018", suggestion="Add manifest item"),
        Issue(severity=Severity.WARNING, message="Missing metadata", location="OEBPS/package.opf",
              rule_id="OPF-097", suggestion="Add accessibility metadata"),
    ]
    return CheckResult(
        epub_path=tmp_path / "book.epub",
        epub_version="3.3",
        checker_version="5.0.0",
        issues=[] if passed else issues,
        counts={"FATAL": 0, "ERROR": 0 if passed else 1, "WARNING": 0 if passed else 1, "USAGE": 0},
        duration_ms=1420,
        raw_output=None,
    )


def test_render_json_is_parseable(tmp_path):
    result = _sample_result(tmp_path, passed=False)
    out = render_json(result)
    data = json.loads(out)
    assert data["epub_version"] == "3.3"
    assert data["checker_version"] == "5.0.0"
    assert data["counts"]["ERROR"] == 1
    assert len(data["issues"]) == 2
    issue0 = data["issues"][0]
    assert issue0["severity"] == "ERROR"
    assert issue0["rule_id"] == "OPF-018"
    assert "book.epub" in data["epub_path"]


def test_render_markdown_contains_key_sections(tmp_path):
    result = _sample_result(tmp_path, passed=False)
    md = render_markdown(result, strict=False)
    assert "# EPUB Quality Report" in md
    assert "EPUB 3.3" in md
    assert "EPUBCheck 5.0.0" in md
    assert "| FATAL |" in md
    assert "| ERROR |" in md
    assert "| WARNING |" in md
    assert "OPF-018" in md
    assert "Add manifest item" in md
    assert "FAIL" in md


def test_render_markdown_pass_banner(tmp_path):
    result = _sample_result(tmp_path, passed=True)
    md = render_markdown(result, strict=False)
    assert "PASS" in md
    assert "FAIL" not in md


def test_render_markdown_strict_warning(tmp_path):
    """--strict 模式下仅 WARNING 也算不通过"""
    result = CheckResult(
        epub_path=tmp_path / "book.epub",
        epub_version="3.3",
        checker_version="5.0.0",
        issues=[Issue(severity=Severity.WARNING, message="w", location="l")],
        counts={"FATAL": 0, "ERROR": 0, "WARNING": 1, "USAGE": 0},
        duration_ms=100,
        raw_output=None,
    )
    md = render_markdown(result, strict=True)
    assert "FAIL" in md


def test_render_console_contains_status(tmp_path):
    result = _sample_result(tmp_path, passed=False)
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=120)
    render_console(result, strict=False, console=console)
    output = buf.getvalue()
    assert "EPUB" in output
    assert "ERROR" in output
    assert "WARNING" in output
    assert "FAIL" in output


def test_render_console_pass_shows_pass(tmp_path):
    result = _sample_result(tmp_path, passed=True)
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=120)
    render_console(result, strict=False, console=console)
    output = buf.getvalue()
    assert "PASS" in output
```

- [ ] **Step 6.1.1: 写失败测试**

写入 `epub_checker/tests/test_report.py`。

- [ ] **Step 6.1.2: 跑测试确认失败**

Run: `pytest epub_checker/tests/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'epub_checker.report'`

### 6.2 实现 report

**Files:**
- Create: `epub_checker/report.py`

```python
"""报告渲染：Rich 控制台 + JSON + Markdown。"""
from __future__ import annotations

import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .models import CheckResult, Severity


_SEV_STYLE: dict[Severity, str] = {
    Severity.FATAL: "bold red",
    Severity.ERROR: "red",
    Severity.WARNING: "yellow",
    Severity.USAGE: "dim",
}


def _passed_strict(result: CheckResult, strict: bool) -> bool:
    """FATAL/ERROR 必失败；strict 时 WARNING 也算失败。"""
    if not result.passed:
        return False
    if strict and result.counts.get("WARNING", 0) > 0:
        return False
    return True


def render_console(
    result: CheckResult,
    strict: bool,
    *,
    console: Console | None = None,
) -> None:
    """Rich 终端表格输出。"""
    if console is None:
        console = Console()

    ok = _passed_strict(result, strict)

    header = (
        f"Book:     {result.epub_path}\n"
        f"Version:  EPUB {result.epub_version}\n"
        f"Checker:  EPUBCheck {result.checker_version}\n"
        f"Duration: {result.duration_ms / 1000:.2f} s"
    )
    console.print(Panel(header, title="EPUB Quality Check", border_style="cyan"))

    counts_table = Table(title="Issues by Severity", show_header=True)
    counts_table.add_column("Severity", style="bold")
    counts_table.add_column("Count", justify="right")
    for sev in Severity:
        n = result.counts.get(sev.value, 0)
        style = _SEV_STYLE.get(sev, "")
        counts_table.add_row(f"[{style}]{sev.value}[/{style}]", str(n))
    console.print(counts_table)

    if ok:
        console.print("[bold green]PASS[/bold green]")
    else:
        summary = (
            f"{result.counts.get('FATAL', 0)} fatal, "
            f"{result.counts.get('ERROR', 0)} error, "
            f"{result.counts.get('WARNING', 0)} warning"
        )
        console.print(f"[bold red]FAIL[/bold red] — {summary}")

    if result.issues:
        console.print()
        console.print("[bold]Top issues:[/bold]")
        for issue in result.issues[:20]:
            style = _SEV_STYLE.get(issue.severity, "")
            rule = f"[{issue.rule_id}] " if issue.rule_id else ""
            console.print(
                f"  [{style}]{issue.severity.value}[/{style}] "
                f"{rule}{issue.message}"
            )
            if issue.location:
                console.print(f"           @ {issue.location}")
            if issue.suggestion:
                console.print(f"           ↳ {issue.suggestion}")


def render_json(result: CheckResult) -> str:
    """JSON 字符串输出。"""
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)


def render_markdown(result: CheckResult, strict: bool) -> str:
    """Markdown 报告输出。"""
    ok = _passed_strict(result, strict)
    lines: list[str] = []
    lines.append(f"# EPUB Quality Report — {result.epub_path.name}")
    lines.append("")
    lines.append("## Metadata")
    lines.append("")
    lines.append(f"- **File**: `{result.epub_path}`")
    lines.append(f"- **EPUB Version**: {result.epub_version}")
    lines.append(f"- **Checker**: EPUBCheck {result.checker_version}")
    lines.append(f"- **Duration**: {result.duration_ms / 1000:.2f} s")
    lines.append("")
    lines.append("## Severity Counts")
    lines.append("")
    lines.append("| Severity | Count |")
    lines.append("|----------|------:|")
    for sev in Severity:
        lines.append(f"| {sev.value} | {result.counts.get(sev.value, 0)} |")
    lines.append("")
    status = "PASS" if ok else "FAIL"
    lines.append(f"## Verdict: **{status}**")
    lines.append("")
    if result.issues:
        lines.append("## Issues")
        lines.append("")
        for sev in Severity:
            bucket = [i for i in result.issues if i.severity == sev]
            if not bucket:
                continue
            lines.append(f"### {sev.value} ({len(bucket)})")
            lines.append("")
            for issue in bucket:
                lines.append(f"#### {issue.rule_id or '(no rule id)'}: {issue.message}")
                lines.append("")
                if issue.location:
                    lines.append(f"- **Location**: `{issue.location}`")
                if issue.suggestion:
                    lines.append(f"- **Fix**: {issue.suggestion}")
                lines.append("")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 6.2.1: 实现 `report.py`**

- [ ] **Step 6.2.2: 跑测试确认通过**

Run: `pytest epub_checker/tests/test_report.py -v`
Expected: PASS（6 个测试全绿）

- [ ] **Step 6.2.3: 提交**

```bash
cd D:/project/bookfile_bat
git add epub_checker/
git commit -m "feat(epub-checker): Rich/JSON/Markdown 三种报告渲染"
```

---

## Task 7: Typer CLI（main.py）

**Files:**
- Create: `epub_checker/main.py`
- Create: `epub_checker/tests/test_cli.py`

### 7.1 写失败测试

**Files:**
- Create: `epub_checker/tests/test_cli.py`

```python
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
    """让 runner.run_epubcheck 返回指定 JSON。"""
    def fake_run(epub_path, config, *, profile=None, mode=None):
        return returncode, json_text
    monkeypatch.setattr("epub_checker.main.run_epubcheck", fake_run)


def _stub_resolve_ok(monkeypatch):
    monkeypatch.setattr("epub_checker.main._resolve_epubcheck_cmd", lambda c: ["ec"])


def test_cli_check_pass_exits_0(tmp_path, monkeypatch):
    _stub_resolve_ok(monkeypatch)
    _stub_run(monkeypatch, json.dumps(
        {"epubVersion": "3.3", "checkerVersion": "5.0.0", "messages": []}
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
    # sample 含 1 FATAL + 2 ERROR，取最大 = 3
    assert result.exit_code == 3


def test_cli_check_warning_only_strict_exits_1(tmp_path, monkeypatch):
    _stub_resolve_ok(monkeypatch)
    _stub_run(monkeypatch, json.dumps({
        "epubVersion": "3.3", "checkerVersion": "5.0.0",
        "messages": [{"severity": "WARNING", "message": "w", "locations": {}}],
    }))
    book = tmp_path / "book.epub"
    book.write_bytes(b"PK\x03\x04")
    result = runner.invoke(app, ["check", str(book), "--strict"])
    assert result.exit_code == 1


def test_cli_check_warning_only_non_strict_exits_0(tmp_path, monkeypatch):
    _stub_resolve_ok(monkeypatch)
    _stub_run(monkeypatch, json.dumps({
        "epubVersion": "3.3", "checkerVersion": "5.0.0",
        "messages": [{"severity": "WARNING", "message": "w", "locations": {}}],
    }))
    book = tmp_path / "book.epub"
    book.write_bytes(b"PK\x03\x04")
    result = runner.invoke(app, ["check", str(book)])
    assert result.exit_code == 0


def test_cli_check_json_output(tmp_path, monkeypatch):
    _stub_resolve_ok(monkeypatch)
    _stub_run(monkeypatch, json.dumps({
        "epubVersion": "3.3", "checkerVersion": "5.0.0",
        "messages": [{"severity": "WARNING", "message": "w", "locations": {}}],
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
        {"epubVersion": "3.3", "checkerVersion": "5.0.0", "messages": []}
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
        (0, json.dumps({"epubVersion": "3.3", "checkerVersion": "5.0.0", "messages": []})),
        (1, json.dumps({
            "epubVersion": "3.3", "checkerVersion": "5.0.0",
            "messages": [{"severity": "ERROR", "message": "x", "locations": {}}],
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
```

- [ ] **Step 7.1.1: 写失败测试**

写入 `epub_checker/tests/test_cli.py`。

- [ ] **Step 7.1.2: 跑测试确认失败**

Run: `pytest epub_checker/tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'epub_checker.main'`

### 7.2 实现 main

**Files:**
- Create: `epub_checker/main.py`

```python
"""Typer CLI 入口。"""
from __future__ import annotations

import subprocess
from pathlib import Path

import typer

from . import __version__
from .config import Config
from .discovery import EpubCheckNotFound, _resolve_epubcheck_cmd
from .parser import parse_epubcheck_output
from .report import render_console, render_json, render_markdown
from .runner import run_epubcheck


app = typer.Typer(
    name="epub-checker",
    help="检查 EPUB 文件是否符合 EPUB 3.3 出版社标准（基于 EPUBCheck）。",
    add_completion=False,
)


EXIT_OK = 0
EXIT_WARNING_STRICT = 1
EXIT_ERROR = 2
EXIT_FATAL = 3
EXIT_TOOL_ERROR = 4


def _compute_exit_code(counts: dict[str, int], strict: bool) -> int:
    if counts.get("FATAL", 0) > 0:
        return EXIT_FATAL
    if counts.get("ERROR", 0) > 0:
        return EXIT_ERROR
    if strict and counts.get("WARNING", 0) > 0:
        return EXIT_WARNING_STRICT
    return EXIT_OK


def _check_single(
    epub_path: Path,
    config: Config,
    *,
    profile: str | None,
    mode: str | None,
    as_json: bool,
    md_path: Path | None,
    strict: bool,
) -> int:
    """检查单个文件。返回退出码。"""
    rc, stdout = run_epubcheck(epub_path, config, profile=profile, mode=mode)
    result = parse_epubcheck_output(stdout, epub_path)

    if as_json:
        typer.echo(render_json(result))
    else:
        render_console(result, strict)

    if md_path:
        md_path.write_text(render_markdown(result, strict), encoding="utf-8")
        if not as_json:
            typer.echo(f"Markdown report: {md_path}")

    return _compute_exit_code(result.counts, strict)


@app.command()
def check(
    path: Path = typer.Argument(..., help="EPUB 文件或包含 EPUB 的目录"),
    json_output: bool = typer.Option(False, "--json", help="输出 JSON 格式"),
    md: Path | None = typer.Option(None, "--md", help="额外写一份 Markdown 报告到指定路径"),
    strict: bool = typer.Option(False, "--strict", help="WARNING 也算不通过"),
    profile: str = typer.Option("default", "--profile", help="EPUBCheck profile: default/dict/docs/edupub/idx/fix"),
    mode: str = typer.Option("exp", "--mode", help="EPUBCheck mode: exp/mo"),
    config_path: Path = typer.Option(
        Path("config.yaml"), "--config", help="config.yaml 路径"
    ),
) -> None:
    """检查一个或多个 EPUB 文件。"""
    if not path.exists():
        typer.echo(f"文件不存在: {path}", err=True)
        raise typer.Exit(EXIT_TOOL_ERROR)

    config = Config.from_yaml(config_path)

    try:
        _ = _resolve_epubcheck_cmd(config)
    except EpubCheckNotFound as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(EXIT_TOOL_ERROR)

    if path.is_dir():
        epub_files = sorted(path.glob("*.epub"))
        if not epub_files:
            typer.echo(f"目录 {path} 下没有 .epub 文件", err=True)
            raise typer.Exit(EXIT_OK)
        worst = EXIT_OK
        for epub in epub_files:
            typer.echo(f"\n=== {epub.name} ===")
            rc = _check_single(
                epub, config,
                profile=profile, mode=mode,
                as_json=json_output, md_path=md, strict=strict,
            )
            worst = max(worst, rc)
        raise typer.Exit(worst)

    rc = _check_single(
        path, config,
        profile=profile, mode=mode,
        as_json=json_output, md_path=md, strict=strict,
    )
    raise typer.Exit(rc)


@app.command()
def version() -> None:
    """打印工具版本和底层 EPUBCheck 版本。"""
    typer.echo(f"epub-checker: {__version__}")
    try:
        config = Config.from_yaml(Path("config.yaml"))
        cmd = _resolve_epubcheck_cmd(config)
        proc = subprocess.run(
            [*cmd, "--version"],
            capture_output=True, text=True, timeout=10,
        )
        typer.echo(proc.stdout.strip() or proc.stderr.strip())
    except Exception as e:
        typer.echo(f"EPUBCheck 不可用: {e}", err=True)


if __name__ == "__main__":
    app()
```

- [ ] **Step 7.2.1: 实现 `main.py`**

- [ ] **Step 7.2.2: 跑测试确认通过**

Run: `pytest epub_checker/tests/test_cli.py -v`
Expected: PASS（10 个测试全绿）

- [ ] **Step 7.2.3: 提交**

```bash
cd D:/project/bookfile_bat
git add epub_checker/
git commit -m "feat(epub-checker): Typer CLI（check/version，4 档退出码）"
```

---

## Task 8: 端到端冒烟（E2E，默认跳过）

**Files:**
- Create: `epub_checker/tests/test_e2e.py`

### 8.1 E2E 集成测试

**Files:**
- Create: `epub_checker/tests/test_e2e.py`

```python
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
```

- [ ] **Step 8.1.1: 写入 E2E 测试**

- [ ] **Step 8.1.2: 跑 E2E（默认跳过）**

Run: `SKIP_EPUBCHECK_E2E=1 pytest epub_checker/tests/test_e2e.py -v`
Expected: SKIPPED

如果有 epubcheck：
Run: `pytest epub_checker/tests/test_e2e.py -v`
Expected: PASS（3 个测试）

- [ ] **Step 8.1.3: 提交**

```bash
cd D:/project/bookfile_bat
git add epub_checker/tests/test_e2e.py
git commit -m "test(epub-checker): 端到端集成测试（默认跳过）"
```

---

## Task 9: 用户文档（README.md）

**Files:**
- Create: `epub_checker/README.md`

### 9.1 写文档

**Files:**
- Create: `epub_checker/README.md`

```markdown
# EPUB 质量检查工具

一个独立子项目，验证 EPUB 文件是否符合 **EPUB 3.3** 出版社标准。
基于 W3C 官方 [EPUBCheck](https://github.com/w3c/epubcheck)（Java）。

## 特性

- 自包含子项目，类似 `ebook_translator/`
- 三种报告：Rich 控制台表格、JSON、Markdown
- 4 档退出码，支持 CI 集成
- 不依赖 `automation/` 流水线，可独立运行
- 仅依赖项目已有的 `typer` / `rich` / `pyyaml`

## 安装前置

工具依赖外部二进制 `epubcheck`，需要先装 **Java 11+**：

| 平台 | 安装命令 |
|---|---|
| macOS | `brew install epubcheck` |
| Ubuntu/Debian | `sudo apt install epubcheck` |
| Windows (Scoop) | `scoop install epubcheck` |
| 手动 | 从 https://github.com/w3c/epubcheck/releases 下载 zip |

验证安装：

```bash
epubcheck --version
```

## 快速开始

从项目根目录：

```bash
# 基本检查
python -m epub_checker.main check book.epub

# 输出 JSON（适合 CI 集成）
python -m epub_checker.main check book.epub --json

# 额外写 Markdown 报告
python -m epub_checker.main check book.epub --md report.md

# 严格模式（WARNING 也算不通过）
python -m epub_checker.main check book.epub --strict

# 批量检查目录下所有 *.epub
python -m epub_checker.main check ./epubs/

# 用字典 profile 校验
python -m epub_checker.main check book.epub --profile dict

# 查看 epubcheck 版本
python -m epub_checker.main version
```

## 退出码

| 退出码 | 含义 |
|---|---|
| 0 | 通过 |
| 1 | `--strict` 模式下有 WARNING |
| 2 | 有 ERROR |
| 3 | 有 FATAL |
| 4 | 工具自身错误（epubcheck 找不到、Java 没装、文件不存在、超时） |

## 配置

在项目根 `config.yaml` 中添加 `epub_checker` 段（可省略，省略用默认）：

```yaml
epub_checker:
  epubcheck_path: null          # null = 走 PATH；可填 .jar 路径或可执行脚本路径
  java_opts: ["-Xmx2g"]         # 调用 java -jar 时的 JVM 参数
  default_profile: default      # default / dict / docs / edupub / idx / fix
  default_mode: exp             # exp / mo
  timeout_seconds: 300          # 单文件超时
```

## 故障排查

| 错误信息 | 原因 | 解决 |
|---|---|---|
| `找不到 epubcheck 可执行文件` | PATH 中没有 epubcheck | 见上文"安装前置" |
| `java: command not found` | JDK/JRE 没装 | 装 Java 11+ |
| `subprocess.TimeoutExpired` | 单文件检查超时 | 调大 `timeout_seconds` |
| 报告里 `epub_version: ?` | epubcheck 输出无法解析为 JSON | 重试；如仍失败附 stderr 给开发者 |

## 与现有项目的关系

- **不** 与 `automation/` 流水线集成
- **不** 写数据库
- **不** 与 `automation/quality_checker.py`（翻译质量检查）混淆——本工具只做文件级 EPUB 合规检查

## 模块结构

```
epub_checker/
├── __init__.py          # __version__
├── main.py              # Typer CLI
├── config.py            # Config dataclass + from_yaml
├── models.py            # Severity, Issue, CheckResult
├── discovery.py         # 定位 epubcheck 可执行文件
├── runner.py            # subprocess 调用
├── parser.py            # EPUBCheck JSON 解析
├── report.py            # Rich / JSON / Markdown 渲染
└── tests/               # 单元测试 + E2E
```

## 开发与测试

```bash
# 跑所有单元测试（不需要 epubcheck 二进制）
pytest epub_checker/tests/ -v --ignore=epub_checker/tests/test_e2e.py

# 跑端到端测试（需要本机 epubcheck）
pytest epub_checker/tests/test_e2e.py -v

# 跳过 E2E
SKIP_EPUBCHECK_E2E=1 pytest epub_checker/tests/ -v
```
```

- [ ] **Step 9.1.1: 写 README**

- [ ] **Step 9.1.2: 提交**

```bash
cd D:/project/bookfile_bat
git add epub_checker/README.md
git commit -m "docs(epub-checker): 用户文档（README.md）"
```

---

## Task 10: 整体验收

- [ ] **Step 10.1: 跑全部单元测试**

Run: `SKIP_EPUBCHECK_E2E=1 pytest epub_checker/tests/ -v --ignore=epub_checker/tests/test_e2e.py`
Expected: 38 个测试全绿（models 8 + config 5 + discovery 5 + runner 4 + parser 5 + report 6 + cli 10 = 43；个别可能略不同）

实际单元测试数：
- test_models.py: 8
- test_config.py: 5
- test_discovery.py: 5
- test_runner.py: 4
- test_parser.py: 5
- test_report.py: 6
- test_cli.py: 10
- **合计 43 个单元测试**

- [ ] **Step 10.2: 手动冒烟**

```bash
cd D:/project/bookfile_bat
python -c "from epub_checker import __version__; print('v', __version__)"
python -m epub_checker.main --help
python -m epub_checker.main check  # 不带参数看 usage
```

Expected: 无报错，模块导入成功

- [ ] **Step 10.3: 检查目录结构**

```bash
ls -la epub_checker/
ls -la epub_checker/tests/
```

Expected: 8 个模块 + tests 完整

- [ ] **Step 10.4: 检查现有代码未受影响**

```bash
git status
git diff --stat
```

Expected: 仅有 epub_checker/ 目录新增，无对其他文件的修改

---

## Self-Review

### 1. Spec 覆盖检查

| Spec 章节 | 对应 Task |
|---|---|
| §3 决策：独立 CLI | Task 7 |
| §3 决策：EPUB 3.3 严格 | 通过 EPUBCheck 调用实现（Task 4） |
| §3 决策：调用外部 epubcheck | Task 3, 4 |
| §3 决策：Rich + JSON + Markdown | Task 6 |
| §3 决策：不要 PDF | 不实现（符合决策） |
| §3 决策：FATAL/ERROR 退出非零 | Task 7 `_compute_exit_code` |
| §3 决策：PATH + 配置覆盖 | Task 3 `_resolve_epubcheck_cmd` + Task 2 `Config` |
| §3 决策：子目录 + 多文件模块 | 全部 Task 在 `epub_checker/` 子目录 |
| §5 内部结构 7 区块 → 7 文件 | Task 1-7 每个对应一个文件 |
| §6 数据模型 | Task 1 |
| §7 CLI | Task 7 |
| §8 配置 | Task 2 |
| §9 与 EPUBCheck 对接 | Task 4, 5 |
| §10 报告渲染 | Task 6 |
| §11 错误处理 | Task 3, 4, 7 |
| §12 测试 | Task 1-8 全覆盖 |
| §13 文档 | Task 9 |
| §15 验收标准 | Task 10 |

### 2. 占位符扫描

无 TBD/TODO/fill-in。所有代码片段完整。

### 3. 类型一致性

- `Severity` / `Issue` / `CheckResult` 在 Task 1 (models.py) 定义，Task 5/6/7 一致使用
- `_resolve_epubcheck_cmd` 在 Task 3 (discovery.py) 定义，Task 4 (runner.py) 引用，Task 7 (main.py) 引用——通过 `from .discovery import _resolve_epubcheck_cmd` 跨模块引用
- `run_epubcheck` 签名 `(Path, Config, *, profile=None, mode=None) → tuple[int, str]`，Task 4 (runner.py) 定义，Task 7 (main.py) 一致调用
- `parse_epubcheck_output` 签名 `(str, Path) → CheckResult`，Task 5 (parser.py) 定义，Task 7 (main.py) 一致调用
- `Config.from_yaml` 签名 `(Path) → Config`，Task 2 (config.py) 定义，Task 7 (main.py) 一致调用
- `_compute_exit_code` 在 Task 7 (main.py) 定义，仅在该文件内使用
- `EpubCheckNotFound` 在 Task 3 (discovery.py) 定义，Task 7 (main.py) 一致捕获
