# EPUB 文件质量检查工具 — 设计文档

**日期**：2026-06-15
**类型**：独立工具（standalone CLI）
**目的**：检查 EPUB 文件是否符合出版社级别的格式标准（EPUB 3.3 严格合规）

---

## 1. 背景与目标

### 1.1 现状
项目里已有 `automation/quality_checker.py`（27KB），是**翻译内容质量**的 8 维度规则检查（completeness / consistency / language / ...），零 API 成本，跑在翻译缓存上。

但**缺少一个文件级 EPUB 验证工具**：检查 EPUB 包的格式是否合法、是否符合 W3C EPUB 3.3 规范。这是出版平台（Apple Books、Kobo、Google Play Books 等）拒收一本书的最常见原因。

### 1.2 目标
- 提供一个独立 CLI：`python epub_checker.py check <file.epub>`
- 严格对齐 W3C **EPUBCheck**（行业事实标准）输出
- 报告 Rich 表格 + JSON + Markdown 三种格式
- 退出码支持 CI 集成

### 1.3 非目标
- **不**做翻译内容质量检查（已有 `quality_checker.py`）
- **不**检查排版美观度（字体选择、版心比例等视觉问题）
- **不**集成到 `automation` 流水线（用户决策：保持独立）
- **不**重新实现任何 EPUB 校验规则（严格只写胶水代码）

---

## 2. 选型：EPUBCheck

| 项目 | 说明 |
|---|---|
| 维护方 | W3C（官方） |
| 最新版本 | 5.x（支持 EPUB 3.3） |
| 语言 | Java（开源，BSD-3 许可） |
| 仓库 | github.com/w3c/epubcheck |
| 依赖 | Java 11+ JRE |
| 产物 | 单个 `epubcheck.jar`（约 4.7 MB） |
| 输出格式 | text / JSON（`--json`）/ XMP（`--xmp`） |
| 严重等级 | FATAL / ERROR / WARNING / USAGE |

**为什么选它**：
1. W3C 官方，主流分发平台都用它做合规判断
2. 单个 jar，跨平台，离线运行
3. JSON 输出便于程序解析
4. 用户决策：调用外部命令 + 解析输出（纯胶水代码）

---

## 3. 用户决策摘要

| 维度 | 决策 |
|---|---|
| 与流水线关系 | 独立 CLI，不集成到 `auto` |
| 合规级别 | EPUB 3.3 + OPF/NCX 严格（直接 EPUBCheck） |
| 验证引擎 | 调用外部 `epubcheck` + 解析 JSON |
| 报告格式 | Rich 控制台 + JSON + Markdown |
| PDF 报告 | 不要 |
| 退出码 | FATAL/ERROR 退出非零；`--strict` 把 WARNING 也算不通过 |
| epubcheck 发现 | PATH + `epubcheck_path` 配置项覆盖 |
| 架构形态 | **单文件脚本**（约 350 行） |

---

## 4. 文件布局

```
epub_checker.py              # 单文件 CLI 工具
tests/
  test_epub_checker.py       # 单元测试（mock subprocess + 样本 JSON）
docs/
  epub_checker.md            # 用户文档：装 Java → 装 epubcheck → 跑 CLI
```

**不** 改动 `automation/`、`requirements-automation.txt`、数据库 schema。EPUBCheck 是外部二进制，不是 Python 依赖。

---

## 5. 单文件内部结构（约 350 行）

```
epub_checker.py
├── 区块 1：常量与配置（~30 行）
│   - SEVERITIES, DEFAULT_TIMEOUT
│   - @dataclass Config（epubcheck_path, java_opts, default_profile, ...）
│   - load_config()：从 config.yaml 读 epub_checker 段（可选）
├── 区块 2：数据模型（~30 行）
│   - class Severity(str, Enum)
│   - @dataclass Issue
│   - @dataclass CheckResult（含 passed 属性和 by_severity 字典）
├── 区块 3：命令发现（~25 行）
│   - class EpubCheckNotFound(Exception)
│   - _resolve_epubcheck_cmd(config) → list[str]
├── 区块 4：进程运行（~30 行）
│   - run_epubcheck(epub_path, config) → tuple[int, str]
│       subprocess.run，capture_output，timeout=300
├── 区块 5：JSON 解析（~50 行）
│   - parse_epubcheck_output(json_text, epub_path) → CheckResult
│       扁平化嵌套结构 → list[Issue]
├── 区块 6：报告渲染（~70 行）
│   - render_console(result, strict) → None（Rich 表格 + pass/fail banner）
│   - render_json(result) → str
│   - render_markdown(result, strict) → str
└── 区块 7：Typer CLI（~50 行）
    - app = typer.Typer()
    - check(path, json, md, strict, profile, mode) → 退出码
    - version() → 打印 epubcheck 版本
```

每个区块用 `# ===` 注释分隔，区块内 docstring 标明职责。

---

## 6. 数据模型

```python
class Severity(str, Enum):
    FATAL = "FATAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    USAGE = "USAGE"

@dataclass
class Issue:
    severity: Severity
    message: str
    location: str            # 例 "OEBPS/chapter3.xhtml@12:5"
    rule_id: str | None      # 例 "RSC-005"
    suggestion: str | None   # 从 epubcheck "hint" 字段提取

@dataclass
class CheckResult:
    epub_path: Path
    epub_version: str          # 来自 epubcheck JSON 的 epubVersion
    checker_version: str       # 来自 checkerVersion
    issues: list[Issue]
    counts: dict[str, int]     # {"FATAL": 0, "ERROR": 2, "WARNING": 1, "USAGE": 0}
    duration_ms: int
    raw_output: str | None     # JSON 解析失败时保留原文

    @property
    def passed(self) -> bool:
        return self.counts.get("FATAL", 0) == 0 and self.counts.get("ERROR", 0) == 0

    @property
    def by_severity(self) -> dict[Severity, list[Issue]]:
        out = {s: [] for s in Severity}
        for i in self.issues:
            out[i.severity].append(i)
        return out
```

---

## 7. CLI 设计

### 7.1 命令

```bash
# 单文件
python epub_checker.py check book.epub
python epub_checker.py check book.epub --json
python epub_checker.py check book.epub --md report.md
python epub_checker.py check book.epub --strict
python epub_checker.py check book.epub --profile dict
python epub_checker.py check book.epub --mode mo

# 批量（扫描目录下所有 *.epub）
python epub_checker.py check ./epubs/

# 元信息
python epub_checker.py version
```

### 7.2 选项

| 选项 | 默认 | 含义 |
|---|---|---|
| `--json` | off | 输出机器可读 JSON（不打印 Rich 表格） |
| `--md PATH` | off | 额外写一份 Markdown 报告到 PATH |
| `--strict` | off | WARNING 也算不通过（退出码 1） |
| `--profile NAME` | `default` | `default` / `dict` / `docs` / `edupub` / `idx` / `fix` |
| `--mode MODE` | `exp` | `exp`（expanded）/ `mo`（monolithic） |

### 7.3 退出码

| 退出码 | 含义 |
|---|---|
| 0 | 通过（FATAL=0, ERROR=0，且 `--strict` 下 WARNING=0） |
| 1 | `--strict` 模式下有 WARNING |
| 2 | 有 ERROR |
| 3 | 有 FATAL |
| 4 | 工具自身错误（epubcheck 找不到、Java 没装、文件不存在、超时） |

### 7.4 Rich 控制台输出样例

```
╭─ EPUB Quality Check ─────────────────────────────────╮
│ Book:     book.epub                                   │
│ Version:  EPUB 3.3                                    │
│ Checker:  EPUBCheck 5.0.0                             │
│ Duration: 1.42 s                                      │
╰───────────────────────────────────────────────────────╯

 Severity   Count   Examples
 ─────────────────────────────────────
 FATAL          0
 ERROR          2   OPF-018, RSC-005
 WARNING        1   OPF-018
 USAGE          0

 FAIL — 2 errors, 1 warning

Top issues:
  [ERROR] OPF-018 — OEBPS/img/cover.jpg is not declared in OPF manifest
           @ OEBPS/package.opf:42
           ↳ Add a manifest item with href='img/cover.jpg'.
  ...
```

---

## 8. 配置

### 8.1 `Config` dataclass

```python
@dataclass
class Config:
    epubcheck_path: str | None = None  # None = 走 PATH
    java_opts: list[str] = field(default_factory=lambda: ["-Xmx1g"])
    default_profile: str = "default"
    default_mode: str = "exp"
    timeout_seconds: int = 300
```

### 8.2 `config.yaml`（可选段）

```yaml
epub_checker:
  epubcheck_path: null          # null = PATH
  java_opts: ["-Xmx2g"]
  default_profile: default
  timeout_seconds: 300
```

`load_config()` 读项目根的 `config.yaml`，找不到对应段时全部用默认值。

### 8.3 命令发现优先级

1. `--epubcheck-path` CLI 参数（**未实现**——太细化，先用 config）
2. `config.yaml` 的 `epub_checker.epubcheck_path`
3. PATH 中 `epubcheck`（Linux/macOS）
4. PATH 中 `epubcheck.bat`（Windows）
5. 都找不到 → `EpubCheckNotFound`，退出 4，提示安装

**Java 假设**：工具不负责发现 `java` 命令。如果 `config.epubcheck_path` 是 jar 文件（绝对路径），会拼成 `["java", "-jar", "<jar>", ...]`，依赖系统 PATH 中的 `java`；如果 `epubcheck_path` 指向一个可执行包装脚本（brew/scoop 装的 `epubcheck`），就当成单命令调用，不再前置 `java`。两种形态都受支持。

---

## 9. 与 EPUBCheck 的对接

### 9.1 进程运行

```python
def run_epubcheck(epub_path: Path, config: Config,
                  *, profile: str | None = None,
                  mode: str | None = None) -> tuple[int, str]:
    cmd_prefix = _resolve_epubcheck_cmd(config)  # ["java", "-jar", "..."] or ["epubcheck"]
    cmd = [
        *cmd_prefix,
        str(epub_path),
        "--mode", mode or config.default_mode,
        "--profile", profile or config.default_profile,
        "--json", "-v", "0",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=config.timeout_seconds)
    # epubcheck 在有错时退出码可能是 1，但仍输出 JSON；只在 2+ 时视为崩溃
    return proc.returncode, proc.stdout
```

### 9.2 JSON 解析

EPUBCheck 5.x 的 `--json` 输出形如：

```json
{
  "epubVersion": "3.3",
  "checkerVersion": "5.0.0",
  "messages": [
    {
      "ID": "OPF-018",
      "severity": "ERROR",
      "message": "Resource '...' is not declared in OPF manifest.",
      "locations": {"application/xml": [{"path": "OEBPS/package.opf", "line": 42}]},
      "hint": "Add a manifest item with href='...'."
    }
  ]
}
```

`parse_epubcheck_output()` 把 `messages[]` 扁平化为 `list[Issue]`：

```python
def parse_epubcheck_output(json_text: str, epub_path: Path) -> CheckResult:
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        return CheckResult(
            epub_path=epub_path, epub_version="?",
            checker_version="?", issues=[], counts={s.value: 0 for s in Severity},
            duration_ms=0, raw_output=json_text,
        )

    issues = []
    for m in data.get("messages", []):
        locs = m.get("locations", {})
        first_loc = next(iter(locs.values()), [{}])[0] if locs else {}
        location = first_loc.get("path", "")
        if "line" in first_loc:
            location += f"@{first_loc['line']}"
        issues.append(Issue(
            severity=Severity(m.get("severity", "USAGE")),
            message=m.get("message", ""),
            location=location,
            rule_id=m.get("ID"),
            suggestion=m.get("hint"),
        ))

    counts = {s.value: 0 for s in Severity}
    for i in issues:
        counts[i.severity.value] += 1

    return CheckResult(
        epub_path=epub_path,
        epub_version=data.get("epubVersion", "?"),
        checker_version=data.get("checkerVersion", "?"),
        issues=issues,
        counts=counts,
        duration_ms=0,
        raw_output=None,
    )
```

---

## 10. 报告渲染

### 10.1 `render_console(result, strict)`（Rich 表格）

- 顶部：Rich `Panel` 打印文件路径、版本、checker 版本、耗时
- 中间：Rich `Table` 列出各严重等级的数量
- 底部：每条 issue 一行（用 `severity_color` 着色）
  - FATAL → bold red
  - ERROR → red
  - WARNING → yellow
  - USAGE → dim
- 末尾：PASS/FAIL banner + 退出码映射

### 10.2 `render_json(result)` → `str`

`CheckResult.to_dict()` 序列化。包含所有 issues 详情。

### 10.3 `render_markdown(result, strict)` → `str`

- 标题：`# EPUB Quality Report — <文件名>`
- 元信息表格
- 严重等级统计表
- Issue 详情（按严重等级分组，每条用 `> blockquote` 显示 message + location + 修复建议）

---

## 11. 错误处理

| 情况 | 行为 |
|---|---|
| `epubcheck` 找不到 | 抛 `EpubCheckNotFound`，捕获后用 Rich 打印安装指南（brew/scoop/apt 链接），退出 4 |
| Java 没装 | 透传到 `subprocess.run` 的 `FileNotFoundError`，捕获后提示，退出 4 |
| 文件不存在 | Typer 在解析参数时报 `BadParameter`，退出 4 |
| epubcheck 崩溃（returncode 2+） | 把 stderr 拼到报告，标 `passed=False` |
| JSON 解析失败 | `raw_output` 保留原文，报告里注明"无法解析" |
| 超时（>300s） | 终止子进程，提示用户调大 `timeout_seconds`，退出 4 |
| 输入是目录 | 扫描 `*.epub`，逐个跑 `check`，**任一失败即整批失败**（退出码取最大严重等级） |

---

## 12. 测试

`tests/test_epub_checker.py`（约 200 行）：

### 12.1 测试 `_resolve_epubcheck_cmd`
- 优先级：config 路径 > PATH `epubcheck` > PATH `epubcheck.bat`
- 都找不到时抛 `EpubCheckNotFound`
- 用 `monkeypatch.setenv("PATH", ...)` 和 `tmp_path` 构造文件系统

### 12.2 测试 `run_epubcheck`
- `monkeypatch.setattr("subprocess.run", ...)` 返回 `(0, json_text)`
- 验证命令拼装正确（epubcheck 路径 + 参数顺序 + 超时）
- 超时抛 `subprocess.TimeoutExpired` 时被正确转换为退出码 4

### 12.3 测试 `parse_epubcheck_output`
- 喂真实 epubcheck 5.x JSON 样本（写在 `tests/fixtures/epubcheck_sample.json`）
- 断言：issue 数量、字段映射、severity 枚举值
- 喂损坏 JSON：断言 `raw_output` 保留原文
- 喂空 messages：断言 `counts` 全 0

### 12.4 测试 `render_*`
- 喂 `CheckResult` fixture
- `render_json` 断言可被 `json.loads` 解析回原对象
- `render_markdown` 断言包含关键片段
- `render_console` 用 `rich.console.Console(file=StringIO(), record=True)` 捕获输出，断言关键字符串出现

### 12.5 测试 `check` CLI
- 用 `typer.testing.CliRunner`
- 全部 mock subprocess，验证：
  - 退出码映射（FATAL=3, ERROR=2, WARNING+strict=1, OK=0）
  - `--json` 不打印 Rich 表格
  - `--md` 写文件
  - 批量模式扫到所有 `.epub`

---

## 13. 文档

`docs/epub_checker.md`：

- 简介
- 安装（Java 11+ → 安装 EPUBCheck：brew / scoop / apt / 手动下载）
- 快速开始（5 个常用命令）
- 退出码表
- 配置文件
- 故障排查（epubcheck 找不到、Java 没装、JSON 解析失败）

---

## 14. 未来扩展（YAGNI：暂不做）

- HTML 报告（当前 Markdown 够用）
- 集成到 `auto` 流水线（用户决策：保持独立）
- 替换验证引擎（如 Pagina、Calibre check-book）：只需替换 `_resolve_epubcheck_cmd` 和 `parse_epubcheck_output`
- 并行批量检查：当前顺序跑，EPUBCheck 自带锁

---

## 15. 验收标准

1. `python epub_checker.py check tests/fixtures/sample.epub` 输出 Rich 表格
2. `python epub_checker.py check tests/fixtures/sample.epub --json` 输出有效 JSON
3. `python epub_checker.py check tests/fixtures/sample.epub --md r.md` 生成 Markdown 文件
4. `python epub_checker.py check tests/fixtures/bad.epub` 退出码非零
5. `python epub_checker.py check /nonexistent.epub` 退出码 4
6. `python epub_checker.py version` 打印 epubcheck 版本
7. `pytest tests/test_epub_checker.py` 全绿，不依赖真实 epubcheck 二进制
8. `docs/epub_checker.md` 含安装 + 用法 + 故障排查
