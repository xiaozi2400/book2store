# EPUB 质量检查工具实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个独立 CLI 工具 `epub_checker.py`，通过调用外部 EPUBCheck 验证 EPUB 文件是否符合 EPUB 3.3 出版社标准。

**Architecture:** 单文件 Python 脚本（约 350 行），内部 7 个区块用 `# ===` 分割：常量配置、数据模型、命令发现、子进程运行、JSON 解析、报告渲染、Typer CLI。EPUBCheck 作为外部黑盒引擎，Python 层只做参数拼装、JSON 解析、报告渲染——零校验规则复写。报告支持 Rich 控制台 / JSON / Markdown 三种格式，4 档退出码支持 CI 集成。

**Tech Stack:** Python 3.11+、Typer（CLI）、Rich（终端输出）、PyYAML（可选配置）、subprocess（EPUBCheck 调用）、pytest + pytest-monkeypatch（测试）

---

## File Structure

| 文件 | 状态 | 职责 |
|---|---|---|
| `epub_checker.py` | 新建 | 单文件 CLI 工具（约 350 行） |
| `tests/test_epub_checker.py` | 新建 | 单元测试，mock subprocess |
| `tests/fixtures/epubcheck_sample.json` | 新建 | EPUBCheck 5.x JSON 样本 |
| `docs/epub_checker.md` | 新建 | 用户文档：装 Java → 装 epubcheck → 跑 CLI |

**不** 修改任何现有文件、不改 `requirements-automation.txt`、不动数据库 schema。

---

## Task 1: 项目骨架与基础数据模型

**Files:**
- Create: `epub_checker.py`
- Create: `tests/test_epub_checker.py`
- Create: `tests/__init__.py`（如不存在）

### 1.1 写失败测试：Severity 枚举与 Issue dataclass

**Files:**
- Create: `tests/test_epub_checker.py`

```python
"""EPUB 质量检查工具的单元测试。所有测试 mock subprocess，不依赖真实 epubcheck。"""
from pathlib import Path
import json

from epub_checker import Severity, Issue, CheckResult


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


def test_issue_optional_fields():
    issue = Issue(
        severity=Severity.USAGE,
        message="msg",
        location="loc",
    )
    assert issue.rule_id is None
    assert issue.suggestion is None


def test_checkresult_passed_no_errors():
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


def test_checkresult_by_severity_groups():
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
```

- [ ] **Step 1.1.1: 写失败测试**

把上面的代码写入 `tests/test_epub_checker.py`。

- [ ] **Step 1.1.2: 跑测试确认失败**

Run: `pytest tests/test_epub_checker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'epub_checker'`

### 1.2 实现最小代码：常量与数据模型

**Files:**
- Create: `epub_checker.py`

```python
"""EPUB 文件质量检查工具。

一个独立 CLI，调用外部 EPUBCheck（Java）验证 EPUB 文件是否符合 EPUB 3.3 出版社标准。
本工具只做胶水代码：参数拼装、JSON 解析、报告渲染、CLI 编排。所有校验规则由 EPUBCheck 提供。
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


# ============================================================
# 区块 1：常量与配置
# ============================================================

DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_JAVA_OPTS = ["-Xmx1g"]
DEFAULT_PROFILE = "default"
DEFAULT_MODE = "exp"
EXIT_OK = 0
EXIT_WARNING_STRICT = 1
EXIT_ERROR = 2
EXIT_FATAL = 3
EXIT_TOOL_ERROR = 4

logger = logging.getLogger("epub_checker")


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


# ============================================================
# 区块 2：数据模型
# ============================================================

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

- [ ] **Step 1.2.1: 实现区块 1+2**

把上面的代码写入 `epub_checker.py`。

- [ ] **Step 1.2.2: 跑测试确认通过**

Run: `pytest tests/test_epub_checker.py -v`
Expected: PASS（7 个测试全绿）

- [ ] **Step 1.2.3: 提交**

```bash
cd D:/project/bookfile_bat
git add epub_checker.py tests/test_epub_checker.py
git commit -m "feat(epub-checker): 骨架与数据模型（Severity/Issue/CheckResult）"
```

---

## Task 2: 命令发现（epubcheck 可执行文件定位）

**Files:**
- Modify: `epub_checker.py`（新增区块 3）
- Modify: `tests/test_epub_checker.py`

### 2.1 写失败测试：命令发现

**Files:**
- Modify: `tests/test_epub_checker.py`

在文件末尾追加：

```python
from epub_checker import Config, EpubCheckNotFound, _resolve_epubcheck_cmd


def test_resolve_uses_config_path_when_set(tmp_path, monkeypatch):
    fake_epubcheck = tmp_path / "my-epubcheck"
    fake_epubcheck.write_text("#!/bin/sh\necho ok\n")
    cfg = Config(epubcheck_path=str(fake_epubcheck))
    cmd = _resolve_epubcheck_cmd(cfg)
    # 当 epubcheck_path 指向 .jar 时应该包成 java -jar
    assert cmd[0] == "java"
    assert cmd[1] == "-jar"
    assert cmd[2] == str(fake_epubcheck)


def test_resolve_falls_back_to_path_unix(tmp_path, monkeypatch):
    fake = tmp_path / "epubcheck"
    fake.write_text("#!/bin/sh\necho ok\n")
    monkeypatch.setenv("PATH", str(tmp_path))
    cfg = Config()
    cmd = _resolve_epubcheck_cmd(cfg)
    # PATH 上有可执行文件，直接用它
    assert cmd == [str(fake)] or cmd[-1] == "epubcheck"


def test_resolve_finds_epubcheck_bat(tmp_path, monkeypatch):
    bat = tmp_path / "epubcheck.bat"
    bat.write_text("@echo off\necho ok\n")
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr("sys.platform", "win32")
    cfg = Config()
    cmd = _resolve_epubcheck_cmd(cfg)
    assert cmd[-1] in ("epubcheck.bat", "epubcheck")


def test_resolve_raises_when_not_found(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))  # 空目录
    cfg = Config()
    try:
        _resolve_epubcheck_cmd(cfg)
    except EpubCheckNotFound as e:
        assert "epubcheck" in str(e).lower()
    else:
        raise AssertionError("应该抛出 EpubCheckNotFound")
```

- [ ] **Step 2.1.1: 写失败测试**

追加到 `tests/test_epub_checker.py`。

- [ ] **Step 2.1.2: 跑测试确认失败**

Run: `pytest tests/test_epub_checker.py -v`
Expected: FAIL with `ImportError: cannot import name 'EpubCheckNotFound'`

### 2.2 实现命令发现

**Files:**
- Modify: `epub_checker.py`

在区块 2 后面追加区块 3：

```python
# ============================================================
# 区块 3：命令发现
# ============================================================

class EpubCheckNotFound(Exception):
    """找不到 epubcheck 可执行文件时抛出。"""


def _resolve_epubcheck_cmd(config: Config) -> list[str]:
    """定位 epubcheck 命令。返回完整的命令行前缀。

    优先级：
    1. config.epubcheck_path 指向 .jar → 返回 ["java", "-jar", "<jar>"]
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
            # 如果 PATH 找到的是 jar 后缀（罕见），也包成 java -jar
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

- [ ] **Step 2.2.1: 实现区块 3**

追加到 `epub_checker.py`。

- [ ] **Step 2.2.2: 跑测试确认通过**

Run: `pytest tests/test_epub_checker.py -v`
Expected: PASS（11 个测试全绿）

- [ ] **Step 2.2.3: 提交**

```bash
cd D:/project/bookfile_bat
git add epub_checker.py tests/test_epub_checker.py
git commit -m "feat(epub-checker): epubcheck 命令发现（PATH + 配置覆盖）"
```

---

## Task 3: 子进程运行

**Files:**
- Modify: `epub_checker.py`（新增区块 4）
- Modify: `tests/test_epub_checker.py`

### 3.1 写失败测试

**Files:**
- Modify: `tests/test_epub_checker.py`

在末尾追加：

```python
import subprocess
from epub_checker import run_epubcheck, _resolve_epubcheck_cmd as _resolve  # noqa


def _make_completed_process(returncode: int, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_run_epubcheck_calls_with_correct_args(tmp_path, monkeypatch):
    """验证命令拼装：epubcheck 命令前缀 + epub 路径 + mode + profile + --json + -v 0"""
    fake_epubcheck = tmp_path / "ec"
    fake_epubcheck.write_text("#!/bin/sh\n")
    cfg = Config(epubcheck_path=str(fake_epubcheck))

    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["timeout"] = kwargs.get("timeout")
        captured["text"] = kwargs.get("text")
        captured["capture_output"] = kwargs.get("capture_output")
        return _make_completed_process(0, stdout='{"messages": []}')

    monkeypatch.setattr("epub_checker.subprocess.run", fake_run)

    book = tmp_path / "book.epub"
    book.write_bytes(b"PK\x03\x04dummy")
    rc, out = run_epubcheck(book, cfg, profile="dict", mode="mo")

    assert rc == 0
    assert out == '{"messages": []}'
    assert captured["cmd"][0:1] == [str(fake_epubcheck)]
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
    fake_epubcheck = tmp_path / "ec"
    fake_epubcheck.write_text("")
    cfg = Config(epubcheck_path=str(fake_epubcheck))

    def fake_run(cmd, **kwargs):
        return _make_completed_process(1, stdout='{"messages": [{"severity":"ERROR"}]}')

    monkeypatch.setattr("epub_checker.subprocess.run", fake_run)

    rc, out = run_epubcheck(tmp_path / "book.epub", cfg)
    assert rc == 1
    assert "ERROR" in out


def test_run_epubcheck_timeout_raises_tool_error(tmp_path, monkeypatch):
    fake_epubcheck = tmp_path / "ec"
    fake_epubcheck.write_text("")
    cfg = Config(epubcheck_path=str(fake_epubcheck))

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=10)

    monkeypatch.setattr("epub_checker.subprocess.run", fake_run)

    import pytest
    with pytest.raises(subprocess.TimeoutExpired):
        run_epubcheck(tmp_path / "book.epub", cfg)
```

- [ ] **Step 3.1.1: 写失败测试**

追加到 `tests/test_epub_checker.py`。

- [ ] **Step 3.1.2: 跑测试确认失败**

Run: `pytest tests/test_epub_checker.py -v`
Expected: FAIL with `ImportError: cannot import name 'run_epubcheck'`

### 3.2 实现 run_epubcheck

**Files:**
- Modify: `epub_checker.py`

在区块 3 后追加区块 4：

```python
# ============================================================
# 区块 4：进程运行
# ============================================================

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

- [ ] **Step 3.2.1: 实现区块 4**

追加到 `epub_checker.py`。

- [ ] **Step 3.2.2: 跑测试确认通过**

Run: `pytest tests/test_epub_checker.py -v`
Expected: PASS（14 个测试全绿）

- [ ] **Step 3.2.3: 提交**

```bash
cd D:/project/bookfile_bat
git add epub_checker.py tests/test_epub_checker.py
git commit -m "feat(epub-checker): subprocess 调用 EPUBCheck"
```

---

## Task 4: JSON 解析

**Files:**
- Create: `tests/fixtures/epubcheck_sample.json`
- Modify: `epub_checker.py`（新增区块 5）
- Modify: `tests/test_epub_checker.py`

### 4.1 创建 EPUBCheck JSON 样本

**Files:**
- Create: `tests/fixtures/epubcheck_sample.json`

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

- [ ] **Step 4.1.1: 写入样本**

把上面的 JSON 写入 `tests/fixtures/epubcheck_sample.json`。

### 4.2 写失败测试

**Files:**
- Modify: `tests/test_epub_checker.py`

在末尾追加：

```python
from epub_checker import parse_epubcheck_output


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
    assert "OPF" in opf018.message or "manifest" in opf018.message
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
    assert result.passed is True  # 没有 issues 时算通过


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
```

- [ ] **Step 4.2.1: 写失败测试**

追加到 `tests/test_epub_checker.py`。

- [ ] **Step 4.2.2: 跑测试确认失败**

Run: `pytest tests/test_epub_checker.py -v`
Expected: FAIL with `ImportError: cannot import name 'parse_epubcheck_output'`

### 4.3 实现 parse_epubcheck_output

**Files:**
- Modify: `epub_checker.py`

在区块 4 后追加区块 5：

```python
# ============================================================
# 区块 5：JSON 解析
# ============================================================

def parse_epubcheck_output(json_text: str, epub_path: Path) -> CheckResult:
    """把 EPUBCheck 的 --json 输出扁平化为 CheckResult。

    处理：
    - JSON 损坏 → 返回空结果 + 保留原文到 raw_output
    - locations 嵌套结构 → 扁平为 "path@line"
    - 缺失字段（rule_id, suggestion, locations）→ 用 None/空字符串
    - 缺失 severity → 默认为 USAGE
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
            # 取第一组 context 的第一个位置
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

- [ ] **Step 4.3.1: 实现区块 5**

追加到 `epub_checker.py`。

- [ ] **Step 4.3.2: 跑测试确认通过**

Run: `pytest tests/test_epub_checker.py -v`
Expected: PASS（18 个测试全绿）

- [ ] **Step 4.3.3: 提交**

```bash
cd D:/project/bookfile_bat
git add epub_checker.py tests/test_epub_checker.py tests/fixtures/epubcheck_sample.json
git commit -m "feat(epub-checker): EPUBCheck JSON 解析"
```

---

## Task 5: 报告渲染（Rich + JSON + Markdown）

**Files:**
- Modify: `epub_checker.py`（新增区块 6）
- Modify: `tests/test_epub_checker.py`

### 5.1 写失败测试

**Files:**
- Modify: `tests/test_epub_checker.py`

在末尾追加：

```python
import io
from rich.console import Console
from epub_checker import render_console, render_json, render_markdown, Severity, Issue, CheckResult


def _make_sample_result(tmp_path: Path, passed: bool = True) -> CheckResult:
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
    result = _make_sample_result(tmp_path, passed=False)
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
    result = _make_sample_result(tmp_path, passed=False)
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
    result = _make_sample_result(tmp_path, passed=True)
    md = render_markdown(result, strict=False)
    assert "PASS" in md
    assert "FAIL" not in md


def test_render_markdown_strict_warning(tmp_path):
    """--strict 模式下，仅 WARNING 也算不通过"""
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
    result = _make_sample_result(tmp_path, passed=False)
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=120)
    render_console(result, strict=False, console=console)
    output = buf.getvalue()
    assert "EPUB" in output
    assert "ERROR" in output
    assert "WARNING" in output
    assert "FAIL" in output
```

- [ ] **Step 5.1.1: 写失败测试**

追加到 `tests/test_epub_checker.py`。

- [ ] **Step 5.1.2: 跑测试确认失败**

Run: `pytest tests/test_epub_checker.py -v`
Expected: FAIL with `ImportError: cannot import name 'render_console'`

### 5.2 实现渲染器

**Files:**
- Modify: `epub_checker.py`

在区块 5 后追加区块 6：

```python
# ============================================================
# 区块 6：报告渲染
# ============================================================

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


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

    # Header panel
    header = (
        f"Book:     {result.epub_path}\n"
        f"Version:  EPUB {result.epub_version}\n"
        f"Checker:  EPUBCheck {result.checker_version}\n"
        f"Duration: {result.duration_ms / 1000:.2f} s"
    )
    console.print(Panel(header, title="EPUB Quality Check", border_style="cyan"))

    # Counts table
    counts_table = Table(title="Issues by Severity", show_header=True)
    counts_table.add_column("Severity", style="bold")
    counts_table.add_column("Count", justify="right")
    for sev in Severity:
        n = result.counts.get(sev.value, 0)
        style = _SEV_STYLE.get(sev, "")
        counts_table.add_row(f"[{style}]{sev.value}[/{style}]", str(n))
    console.print(counts_table)

    # Banner
    if ok:
        console.print("[bold green]PASS[/bold green]")
    else:
        summary = (
            f"{result.counts.get('FATAL', 0)} fatal, "
            f"{result.counts.get('ERROR', 0)} error, "
            f"{result.counts.get('WARNING', 0)} warning"
        )
        console.print(f"[bold red]FAIL[/bold red] — {summary}")

    # Top issues (前 20 条，避免洪水)
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

- [ ] **Step 5.2.1: 实现区块 6**

追加到 `epub_checker.py`。

- [ ] **Step 5.2.2: 跑测试确认通过**

Run: `pytest tests/test_epub_checker.py -v`
Expected: PASS（23 个测试全绿）

- [ ] **Step 5.2.3: 提交**

```bash
cd D:/project/bookfile_bat
git add epub_checker.py tests/test_epub_checker.py
git commit -m "feat(epub-checker): Rich/JSON/Markdown 三种报告渲染"
```

---

## Task 6: Typer CLI（check / version 命令）

**Files:**
- Modify: `epub_checker.py`（新增区块 7）
- Modify: `tests/test_epub_checker.py`

### 6.1 写失败测试

**Files:**
- Modify: `tests/test_epub_checker.py`

在末尾追加：

```python
import subprocess
from typer.testing import CliRunner
from epub_checker import app


runner = CliRunner()


def _stub_epubcheck(monkeypatch, json_path: Path, returncode: int = 0):
    """让 run_epubcheck 返回样本 JSON 的内容。"""
    def fake_run(epub_path, config, *, profile=None, mode=None):
        return returncode, json_path.read_text(encoding="utf-8")
    monkeypatch.setattr("epub_checker.run_epubcheck", fake_run)


def test_cli_check_pass_exits_0(tmp_path, monkeypatch):
    sample = Path(__file__).parent / "fixtures" / "epubcheck_sample.json"
    # 用一份无错版本
    clean = json.dumps({"epubVersion": "3.3", "checkerVersion": "5.0.0", "messages": []})
    clean_path = tmp_path / "clean.json"
    clean_path.write_text(clean, encoding="utf-8")
    _stub_epubcheck(monkeypatch, clean_path, returncode=0)

    book = tmp_path / "book.epub"
    book.write_bytes(b"PK\x03\x04")
    result = runner.invoke(app, ["check", str(book)])
    assert result.exit_code == 0


def test_cli_check_error_exits_2(tmp_path, monkeypatch):
    sample = Path(__file__).parent / "fixtures" / "epubcheck_sample.json"
    _stub_epubcheck(monkeypatch, sample, returncode=1)

    book = tmp_path / "book.epub"
    book.write_bytes(b"PK\x03\x04")
    result = runner.invoke(app, ["check", str(book)])
    # sample 里有 1 FATAL + 2 ERROR，取最大 = 3
    assert result.exit_code == 3


def test_cli_check_warning_only_strict_exits_1(tmp_path, monkeypatch):
    text = json.dumps({
        "epubVersion": "3.3",
        "checkerVersion": "5.0.0",
        "messages": [{"severity": "WARNING", "message": "w", "locations": {}}],
    })
    p = tmp_path / "warn.json"
    p.write_text(text, encoding="utf-8")
    _stub_epubcheck(monkeypatch, p, returncode=0)

    book = tmp_path / "book.epub"
    book.write_bytes(b"PK\x03\x04")
    result = runner.invoke(app, ["check", str(book), "--strict"])
    assert result.exit_code == 1


def test_cli_check_warning_only_non_strict_exits_0(tmp_path, monkeypatch):
    text = json.dumps({
        "epubVersion": "3.3",
        "checkerVersion": "5.0.0",
        "messages": [{"severity": "WARNING", "message": "w", "locations": {}}],
    })
    p = tmp_path / "warn.json"
    p.write_text(text, encoding="utf-8")
    _stub_epubcheck(monkeypatch, p, returncode=0)

    book = tmp_path / "book.epub"
    book.write_bytes(b"PK\x03\x04")
    result = runner.invoke(app, ["check", str(book)])
    assert result.exit_code == 0


def test_cli_check_json_output(tmp_path, monkeypatch):
    text = json.dumps({
        "epubVersion": "3.3", "checkerVersion": "5.0.0",
        "messages": [{"severity": "WARNING", "message": "w", "locations": {}}],
    })
    p = tmp_path / "warn.json"
    p.write_text(text, encoding="utf-8")
    _stub_epubcheck(monkeypatch, p, returncode=0)

    book = tmp_path / "book.epub"
    book.write_bytes(b"PK\x03\x04")
    result = runner.invoke(app, ["check", str(book), "--json"])
    # 退出码 0
    assert result.exit_code == 0
    # stdout 是 JSON，可被解析
    data = json.loads(result.stdout)
    assert data["epub_version"] == "3.3"


def test_cli_check_md_output_writes_file(tmp_path, monkeypatch):
    text = json.dumps({"epubVersion": "3.3", "checkerVersion": "5.0.0", "messages": []})
    p = tmp_path / "ok.json"
    p.write_text(text, encoding="utf-8")
    _stub_epubcheck(monkeypatch, p, returncode=0)

    book = tmp_path / "book.epub"
    book.write_bytes(b"PK\x03\x04")
    out = tmp_path / "report.md"
    result = runner.invoke(app, ["check", str(book), "--md", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert "EPUB Quality Report" in out.read_text(encoding="utf-8")


def test_cli_check_nonexistent_file(tmp_path):
    result = runner.invoke(app, ["check", str(tmp_path / "nope.epub")])
    # Typer BadParameter → exit 4
    assert result.exit_code == 4


def test_cli_check_directory_batch(tmp_path, monkeypatch):
    """目录扫描 *.epub，任一失败即整批失败"""
    # 准备 2 个 epub
    b1 = tmp_path / "a.epub"
    b2 = tmp_path / "b.epub"
    b1.write_bytes(b"PK\x03\x04")
    b2.write_bytes(b"PK\x03\x04")

    # 第一次调用返回 OK，第二次返回 ERROR
    responses = [
        (0, json.dumps({"epubVersion": "3.3", "checkerVersion": "5.0.0", "messages": []})),
        (1, json.dumps({
            "epubVersion": "3.3", "checkerVersion": "5.0.0",
            "messages": [{"severity": "ERROR", "message": "x", "locations": {}}],
        })),
    ]

    def fake_run(epub_path, config, *, profile=None, mode=None):
        return responses.pop(0)

    monkeypatch.setattr("epub_checker.run_epubcheck", fake_run)

    result = runner.invoke(app, ["check", str(tmp_path)])
    # 第二个文件失败 → 退出码 2（ERROR）
    assert result.exit_code == 2


def test_cli_check_epubcheck_not_found(tmp_path, monkeypatch):
    book = tmp_path / "book.epub"
    book.write_bytes(b"PK\x03\x04")

    def fake_resolve(config):
        raise EpubCheckNotFound("missing")

    monkeypatch.setattr("epub_checker._resolve_epubcheck_cmd", fake_resolve)

    result = runner.invoke(app, ["check", str(book)])
    assert result.exit_code == 4
    assert "epubcheck" in result.stdout.lower() or "epubcheck" in (result.stderr or "").lower()
```

- [ ] **Step 6.1.1: 写失败测试**

追加到 `tests/test_epub_checker.py`。

- [ ] **Step 6.1.2: 跑测试确认失败**

Run: `pytest tests/test_epub_checker.py -v`
Expected: FAIL with `ImportError: cannot import name 'app'`

### 6.2 实现 CLI

**Files:**
- Modify: `epub_checker.py`

在区块 6 后追加区块 7：

```python
# ============================================================
# 区块 7：Typer CLI
# ============================================================

import typer


app = typer.Typer(
    name="epub-checker",
    help="检查 EPUB 文件是否符合 EPUB 3.3 出版社标准（基于 EPUBCheck）。",
    add_completion=False,
)


def _compute_exit_code(result: CheckResult, strict: bool) -> int:
    """根据检查结果和 --strict 决定退出码。"""
    if result.counts.get("FATAL", 0) > 0:
        return EXIT_FATAL
    if result.counts.get("ERROR", 0) > 0:
        return EXIT_ERROR
    if strict and result.counts.get("WARNING", 0) > 0:
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
        print(render_json(result))
    else:
        render_console(result, strict)

    if md_path:
        md_path.write_text(render_markdown(result, strict), encoding="utf-8")
        if not as_json:
            print(f"Markdown report: {md_path}")

    return _compute_exit_code(result, strict)


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

    # 目录批量
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

    # 单文件
    rc = _check_single(
        path, config,
        profile=profile, mode=mode,
        as_json=json_output, md_path=md, strict=strict,
    )
    raise typer.Exit(rc)


@app.command()
def version() -> None:
    """打印工具版本和底层 EPUBCheck 版本。"""
    import epub_checker
    typer.echo(f"epub-checker: {getattr(epub_checker, '__version__', '0.1.0')}")
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


__version__ = "0.1.0"


if __name__ == "__main__":
    app()
```

- [ ] **Step 6.2.1: 实现区块 7**

追加到 `epub_checker.py`。

- [ ] **Step 6.2.2: 跑测试确认通过**

Run: `pytest tests/test_epub_checker.py -v`
Expected: PASS（32 个测试全绿）

- [ ] **Step 6.2.3: 提交**

```bash
cd D:/project/bookfile_bat
git add epub_checker.py tests/test_epub_checker.py
git commit -m "feat(epub-checker): Typer CLI（check/version，4 档退出码）"
```

---

## Task 7: 端到端冒烟（真实 epubcheck 集成，仅在已装环境跑）

**Files:**
- Create: `tests/test_epub_checker_e2e.py`

### 7.1 真实 epubcheck 集成测试

**Files:**
- Create: `tests/test_epub_checker_e2e.py`

```python
"""端到端集成测试——需要本机已装 epubcheck 与 Java。
通过环境变量 SKIP_EPUBCHECK_E2E=1 可跳过。"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_EPUBCHECK_E2E") == "1" or shutil.which("epubcheck") is None,
    reason="需要本机已装 epubcheck",
)


def test_real_epubcheck_call(tmp_path):
    """最小冒烟：随便一个空 zip 当 epub（epubcheck 会报 FATAL，但至少能跑通）"""
    from epub_checker import Config, run_epubcheck, parse_epubcheck_output

    fake = tmp_path / "fake.epub"
    fake.write_bytes(b"")  # 空文件

    cfg = Config()
    rc, stdout = run_epubcheck(fake, cfg, profile="default", mode="exp")

    assert rc != 0  # 空文件肯定不合法
    assert stdout.strip()  # 应该有 JSON 输出
    result = parse_epubcheck_output(stdout, fake)
    assert result.counts.get("FATAL", 0) >= 1


def test_real_epubcheck_cli_help():
    """CLI 帮助文本可访问"""
    from typer.testing import CliRunner
    from epub_checker import app

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "check" in result.stdout


def test_real_epubcheck_version_cmd():
    """version 命令在装好 epubcheck 时打印版本"""
    from typer.testing import CliRunner
    from epub_checker import app

    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    # 不强求 exit 0，只要求有输出
    assert "epubcheck" in result.stdout.lower() or "epub-checker" in result.stdout.lower()
```

- [ ] **Step 7.1.1: 写入 E2E 测试**

把上面的代码写入 `tests/test_epub_checker_e2e.py`。

- [ ] **Step 7.1.2: 跑 E2E 测试**

Run: `SKIP_EPUBCHECK_E2E=1 pytest tests/test_epub_checker_e2e.py -v`
Expected: SKIPPED（默认跳过）

如果有 epubcheck：
Run: `pytest tests/test_epub_checker_e2e.py -v`
Expected: PASS（3 个测试）

- [ ] **Step 7.1.3: 提交**

```bash
cd D:/project/bookfile_bat
git add tests/test_epub_checker_e2e.py
git commit -m "test(epub-checker): 端到端集成测试（默认跳过，需要本机 epubcheck）"
```

---

## Task 8: 用户文档

**Files:**
- Create: `docs/epub_checker.md`

### 8.1 写文档

**Files:**
- Create: `docs/epub_checker.md`

```markdown
# EPUB 质量检查工具

一个独立的 CLI 工具，验证 EPUB 文件是否符合 **EPUB 3.3** 出版社标准。
基于 W3C 官方 [EPUBCheck](https://github.com/w3c/epubcheck)（Java）。

## 特性

- 单文件脚本，零 Python 依赖（只复用项目已有的 `typer` / `rich` / `pyyaml`）
- 三种报告：Rich 控制台表格、JSON、Markdown
- 4 档退出码，支持 CI 集成
- 不依赖 `automation/` 流水线，可独立运行

## 安装

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

```bash
# 基本检查
python epub_checker.py check book.epub

# 输出 JSON（适合 CI 集成）
python epub_checker.py check book.epub --json

# 额外写 Markdown 报告
python epub_checker.py check book.epub --md report.md

# 严格模式（WARNING 也算不通过）
python epub_checker.py check book.epub --strict

# 批量检查目录下所有 *.epub
python epub_checker.py check ./epubs/

# 用字典 profile 校验
python epub_checker.py check book.epub --profile dict

# 查看 epubcheck 版本
python epub_checker.py version
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
| `找不到 epubcheck 可执行文件` | PATH 中没有 epubcheck | 见上文"安装" |
| `java: command not found` | JDK/JRE 没装 | 装 Java 11+ |
| `subprocess.TimeoutExpired` | 单文件检查超时 | 调大 `timeout_seconds` |
| 报告里 `epub_version: ?` | epubcheck 输出无法解析为 JSON | 重试；如仍失败附 stderr 给开发者 |

## 与现有流水线的关系

- **不** 与 `automation/` 流水线集成
- **不** 写数据库
- **不** 与 `automation/quality_checker.py`（翻译质量检查）混淆——本工具只做文件级 EPUB 合规检查

## 开发与测试

```bash
# 跑所有单元测试（不需要 epubcheck 二进制）
pytest tests/test_epub_checker.py -v

# 跑端到端测试（需要本机 epubcheck）
pytest tests/test_epub_checker_e2e.py -v

# 跳过 E2E
SKIP_EPUBCHECK_E2E=1 pytest tests/ -v
```
```

- [ ] **Step 8.1.1: 写文档**

把上面的内容写入 `docs/epub_checker.md`。

- [ ] **Step 8.1.2: 提交**

```bash
cd D:/project/bookfile_bat
git add docs/epub_checker.md
git commit -m "docs: EPUB 质量检查工具用户文档"
```

---

## Task 9: 整体验收

- [ ] **Step 9.1: 跑全部测试**

Run: `SKIP_EPUBCHECK_E2E=1 pytest tests/test_epub_checker.py -v`
Expected: 32 个测试全绿

- [ ] **Step 9.2: 手动冒烟**

```bash
cd D:/project/bookfile_bat
python -c "import epub_checker; print('导入成功')"
python epub_checker.py --help
python epub_checker.py version  # 若有 epubcheck
```

Expected: 无报错，输出符合预期

- [ ] **Step 9.3: 检查文件结构**

```bash
ls -la epub_checker.py tests/test_epub_checker.py tests/test_epub_checker_e2e.py docs/epub_checker.md tests/fixtures/epubcheck_sample.json
```

Expected: 5 个文件全部存在

- [ ] **Step 9.4: 检查现有代码未受影响**

```bash
git status
git diff --stat
```

Expected: 仅有新增文件，无对现有文件的修改

---

## Self-Review

### 1. Spec 覆盖检查

| Spec 章节 | 对应 Task |
|---|---|
| §3 决策：独立 CLI | Task 6 |
| §3 决策：EPUB 3.3 严格 | 通过 EPUBCheck 调用实现（Task 3） |
| §3 决策：调用外部 epubcheck | Task 2, 3 |
| §3 决策：Rich + JSON + Markdown | Task 5 |
| §3 决策：不要 PDF | 不实现（符合决策） |
| §3 决策：FATAL/ERROR 退出非零 | Task 6 `_compute_exit_code` |
| §3 决策：PATH + 配置覆盖 | Task 2 `_resolve_epubcheck_cmd` |
| §3 决策：单文件脚本 | 全部 Task 在 `epub_checker.py` |
| §5 内部结构 7 区块 | Task 1-6 每个对应一个区块 |
| §6 数据模型 | Task 1 |
| §7 CLI | Task 6 |
| §8 配置 | Task 1 `Config.from_yaml` |
| §9 与 EPUBCheck 对接 | Task 3, 4 |
| §10 报告渲染 | Task 5 |
| §11 错误处理 | Task 2, 3, 6 |
| §12 测试 | Task 1-7 全覆盖 |
| §13 文档 | Task 8 |
| §15 验收标准 | Task 9 |

### 2. 占位符扫描

无 TBD/TODO/fill-in。所有代码片段完整。

### 3. 类型一致性

- `Severity` / `Issue` / `CheckResult` 在 Task 1 定义，Task 4-6 一致使用
- `_resolve_epubcheck_cmd` 在 Task 2 定义，Task 3 引用，Task 6 引用
- `run_epubcheck` 签名 `(Path, Config, *, profile=None, mode=None) → tuple[int, str]`，Task 3 定义，Task 4 stub 测试，Task 6 CLI 全部一致
- `parse_epubcheck_output` 签名 `(str, Path) → CheckResult`，Task 4 定义，Task 5/6 一致
- `Config.from_yaml` 签名 `(Path) → Config`，Task 1 定义，Task 6 引用
- `_check_single` 在 Task 6 定义，Task 6 内部调用一致
- `_compute_exit_code` 在 Task 6 定义，Task 6 内部 + 测试一致
