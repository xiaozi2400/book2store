# 终端输出优化设计文档

## 概述

优化 `auto()` 命令运行时的终端输出：

1. **保留翻译进度**：显示实时翻译进度（段号/百分比）
2. **其他步骤简化**：只显示“正在xxx”和“xxx已完成”
3. **细节日志仅写入文件**：翻译细节、AI 调用、闲鱼发布步骤、图片处理等，只写入日志文件，不打印到终端

---

## 问题陈述

### 现状输出

- `ebook_translator/translator/translator.py` 中 `print()` 输出翻译进度（实时更新）
- `main.py` 中 `console.print()` 输出高层次状态（正在翻译、已完成等）
- `setup_logging()` 同时输出 `logger.info` 到文件和终端（StreamHandler + FileHandler，都是 INFO 级别）
- 翻译过程的细节日志、闲鱼发布步骤日志、AI 调用日志、图片处理日志都打印到终端，造成噪音过大

### 用户需求

| 内容 | 输出到终端 | 仅写入日志文件 | 说明 |
|------|----------|----------|------|
| 翻译进度（print("进度: 150/200 (75.0%)")） | ✅ | ❌ | 用户要求保留实时翻译进度 |
| main.py 高层次状态（正在翻译、已完成、耗时） | ✅ | ❌ | console.print 直接输出 |
| Token 消耗表格 | ✅ | ❌ | main.py 展示 |
| 翻译质量报告汇总 | ✅ | ❌ | main.py 展示 |
| logger.warning/logger.error（错误和警告） | ✅ | ✅ | 需要关注的问题 |
| logger.info（翻译细节、AI调用、闲鱼步骤、图片处理） | ❌ | ✅ | 只写入日志文件 |

---

## 设计方案

### 改动点

只修改一个文件：`automation/utils.py` 中的 `setup_logging()` 函数

修改前：

```python
def setup_logging(log_dir: str = "./logs"):
    """配置日志"""
    Path(log_dir).mkdir(exist_ok=True)

    log_file = Path(log_dir) / f"automation_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()  # 终端：当前是 INFO 级别
        ]
    )
```

修改后：

```python
def setup_logging(log_dir: str = "./logs"):
    """配置日志"""
    Path(log_dir).mkdir(exist_ok=True)

    log_file = Path(log_dir) / f"automation_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler() 
        ]
    )
    # 关键改动：仅终端输出 WARNING 及以上（保留错误和警告）
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            handler.setLevel(logging.WARNING)
```

---

## 行为确认

| 输出位置 | 类型 | 终端显示 | 日志文件写入 | 说明 |
|--------|------|---------|---------|------|
| `translator.py` 的 `print()` | stdout | ✅ | ❌ | 翻译进度直接输出 |
| `main.py` 的 `console.print()` | stdout | ✅ | ❌ | 高层次状态直接输出 |
| `logger.info("翻译段落...")` | StreamHandler | ❌ | ✅ | 仅写入日志文件 |
| `logger.info("AI调用完成...")` | StreamHandler | ❌ | ✅ | 仅写入日志文件 |
| `logger.info("闲鱼正在点击...")` | StreamHandler | ❌ | ✅ | 仅写入日志文件 |
| `logger.warning("WeasyPrint回退...")` | StreamHandler | ✅ | ✅ | 显示在终端和文件中 |
| `logger.error("翻译失败...")` | StreamHandler | ✅ | ✅ | 显示在终端和文件中 |

---

## 验证清单

- ✅ `auto()` 运行时，翻译进度 `print()` 正常显示（实时更新）
- ✅ `auto()` 运行时，main.py 中 `console.print()` 正常显示（正在xxx、完成）
- ✅ 所有 `logger.info()` 只写入日志文件，不显示在终端
- ✅ `logger.warning()` 和 `logger.error()` 仍然显示在终端
- ✅ 日志文件完整记录所有 INFO/WARNING/ERROR

---

## 范围

- 仅修改 `automation/utils.py`
- 不改动任何业务逻辑或 `console.print()`/`print()` 调用
- 仅调整日志输出级别
