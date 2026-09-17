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
