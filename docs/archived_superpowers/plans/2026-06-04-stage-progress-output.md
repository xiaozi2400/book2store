# 阶段进度输出 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在每个耗时阶段的开始/结束/关键事件输出信息到终端，避免用户误以为系统卡死。

**架构：** 新建 `automation/progress.py` 提供 `phase()` 上下文管理器、`@phase()` 装饰器、`event()` 函数。`print` 直接输出到终端（不受日志级别过滤）。改动 main.py 和 5 个关键模块用 `phase()` 包裹主流程。

**技术栈：** Python, pytest

---

### 任务 1：创建 progress.py 模块 + 单元测试

**文件：**
- 创建：`d:\project\bookfile_bat\automation\progress.py`
- 创建：`d:\project\bookfile_bat\tests\test_progress.py`

- [ ] **步骤 1.1：创建单元测试文件**

在 `tests/test_progress.py` 中写入：

```python
"""测试 progress 模块的阶段输出"""
import io
import sys
import time
import pytest

sys.path.insert(0, '.')

from automation.progress import phase, event, phase_decorator


def test_phase_normal_outputs_start_and_end(capsys):
    """正常 phase 输出开始和结束标记"""
    with phase("测试阶段"):
        pass
    captured = capsys.readouterr()
    assert "⏳ 正在测试阶段..." in captured.out
    assert "✓ 测试阶段完成" in captured.out


def test_phase_outputs_duration_format_seconds(capsys):
    """耗时 < 60 秒显示为 Xs"""
    with phase("快速任务"):
        time.sleep(0.05)
    captured = capsys.readouterr()
    # 包含耗时数字
    assert "s)" in captured.out or "ms)" in captured.out


def test_phase_exception_outputs_failure(capsys):
    """异常时输出失败标记但不吞掉异常"""
    with pytest.raises(ValueError):
        with phase("失败任务"):
            raise ValueError("测试异常")
    captured = capsys.readouterr()
    assert "✗ 失败任务失败" in captured.out
    assert "ValueError" in captured.out


def test_phase_nested_indentation(capsys):
    """嵌套 phase 缩进正确"""
    with phase("外层"):
        with phase("内层"):
            pass
    captured = capsys.readouterr()
    # 内层应有更多缩进
    lines = captured.out.split("\n")
    outer_start = next(l for l in lines if "⏳ 正在外层" in l)
    inner_start = next(l for l in lines if "⏳ 正在内层" in l)
    assert outer_start.count("  ") < inner_start.count("  ")


def test_event_outputs_with_indicator(capsys):
    """event 输出关键事件标记"""
    with phase("测试"):
        event("调用 API")
    captured = capsys.readouterr()
    assert "└─ 调用 API" in captured.out


def test_decorator_form(capsys):
    """装饰器形式工作正常"""
    @phase_decorator("装饰任务")
    def do_work():
        return "完成"

    result = do_work()
    captured = capsys.readouterr()
    assert result == "完成"
    assert "⏳ 正在装饰任务..." in captured.out
    assert "✓ 装饰任务完成" in captured.out


def test_decorator_with_exception(capsys):
    """装饰器形式异常处理"""
    @phase_decorator("失败装饰")
    def fail():
        raise RuntimeError("错误")

    with pytest.raises(RuntimeError):
        fail()
    captured = capsys.readouterr()
    assert "✗ 失败装饰失败" in captured.out


if __name__ == '__main__':
    test_phase_normal_outputs_start_and_end()
    test_phase_exception_outputs_failure()
    test_event_outputs_with_indicator()
    test_decorator_form()
    print("基本测试通过")
```

- [ ] **步骤 1.2：运行测试验证失败（模块未实现）**

```powershell
& "D:\project\bookfile_bat\.venv\Scripts\python.exe" -m pytest tests/test_progress.py -v
```

预期：FAIL（`ModuleNotFoundError: No module named 'automation.progress'`）

- [ ] **步骤 1.3：创建 progress.py 模块**

写入 `d:\project\bookfile_bat\automation\progress.py`：

```python
"""阶段进度输出工具

提供 phase() 上下文管理器和 event() 函数，
用于在耗时阶段开始/结束/关键事件输出信息到终端，
避免用户误以为系统卡死。
"""
import sys
import time
import threading
from contextlib import contextmanager


_INDENT_LEVEL = [0]
_INDENT_LOCK = threading.Lock()


def _format_duration(seconds: float) -> str:
    """格式化耗时：< 1秒显示小数，否则显示 秒/分秒"""
    if seconds < 1:
        return f"{seconds:.2f}s"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}分 {secs}秒"


@contextmanager
def phase(name: str):
    """阶段上下文管理器

    用法:
        with phase("翻译"):
            ...

    进入时输出 '⏳ 正在{name}...'
    退出时输出 '✓ {name}完成 ({耗时})' 或 '✗ {name}失败: {异常}'
    支持嵌套：自动缩进展示层级
    """
    indent = "  " * _INDENT_LEVEL[0]
    start = time.time()
    print(f"{indent}⏳ 正在{name}...")
    sys.stdout.flush()
    with _INDENT_LOCK:
        _INDENT_LEVEL[0] += 1
    try:
        yield
        elapsed = time.time() - start
        print(f"{indent}✓ {name}完成 ({_format_duration(elapsed)})")
        sys.stdout.flush()
    except Exception as e:
        elapsed = time.time() - start
        print(f"{indent}✗ {name}失败: {type(e).__name__}: {str(e)[:200]}")
        sys.stdout.flush()
        raise
    finally:
        with _INDENT_LOCK:
            _INDENT_LEVEL[0] -= 1


def event(message: str) -> None:
    """阶段内输出关键事件

    用法:
        with phase("翻译"):
            event(f"调用 DeepSeek API (32 段落)")

    输出格式: '  └─ {message}'（带当前缩进）
    """
    indent = "  " * _INDENT_LEVEL[0]
    print(f"{indent}  └─ {message}")
    sys.stdout.flush()


def phase_decorator(name: str):
    """phase 装饰器形式

    用法:
        @phase_decorator("翻译")
        def translate_book(...):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with phase(name):
                return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator
```

- [ ] **步骤 1.4：运行测试验证通过**

```powershell
& "D:\project\bookfile_bat\.venv\Scripts\python.exe" -m pytest tests/test_progress.py -v
```

预期：所有 7 个测试通过。

- [ ] **步骤 1.5：手动验证输出效果**

```powershell
& "D:\project\bookfile_bat\.venv\Scripts\python.exe" -c "import time; from automation.progress import phase, event; 
with phase('外层'):
    time.sleep(0.1)
    with phase('内层'):
        event('调用 API')
        time.sleep(0.1)
    event('完成处理')
"
```

预期输出（缩进展示层级）：
```
⏳ 正在外层...
  ⏳ 正在内层...
    └─ 调用 API
  ✓ 内层完成 (0.1s)
  └─ 完成处理
✓ 外层完成 (0.2s)
```

### 任务 2：改造 main.py —— 用 phase 包裹主流程

**文件：**
- 修改：`d:\project\bookfile_bat\automation\main.py:1-260`

- [ ] **步骤 2.1：添加 progress 模块导入**

在 `main.py` 顶部 import 块（约 19 行附近）添加：

```python
from automation.progress import phase, event
```

放在其他 automation import 旁边。

- [ ] **步骤 2.2：包裹 process 命令的每个步骤**

修改 `process()` 命令（约 130-200 行），将 `progress.update(...)` 调用替换为 `phase()` 包裹：

```python
    with phase("翻译并生成 PDF"):
        if not translate_book(book_obj.id, str(input_path)):
            console.print("[bold red]翻译失败，停止处理[/bold red]")
            raise typer.Exit(1)

    with phase("生成精简版"):
        generate_summary(book_id, str(input_path))

    with phase("生成主图"):
        from automation.image_generator import generate_main_image
        generate_main_image(book_id)

    with phase("提取图片"):
        base_name = Path(input_path).stem.strip()
        pdf_path = Path(config.output_dir) / base_name / "PDF" / f"中英双语-{base_name}.pdf"
        extract_images(book_id, str(input_path), str(pdf_path) if pdf_path.exists() else None)

    with phase("生成文案"):
        generate_copywriting(book_id, {
            'title': book_obj.title,
            'author': book_obj.author,
            'summary': book_obj.summary_text or ''
        })

    if not skip_publish:
        with phase("发布到闲鱼"):
            publish_to_xianyu(book_id)
```

**注意**：移除原来包裹这些步骤的 `with Progress(...)` 块（如果保留会显示两次进度）。保留 Progress 块的初始化也行，但需要清除 `progress.update(task, ...)` 调用，避免重复显示。

- [ ] **步骤 2.3：运行测试确保无回归**

```powershell
& "D:\project\bookfile_bat\.venv\Scripts\python.exe" -m pytest tests/ -v 2>&1 | Select-Object -Last 30
```

预期：所有原有测试 + 新增 progress 测试都通过。

### 任务 3：在 AI 客户端添加 event 输出

**文件：**
- 修改：`d:\project\bookfile_bat\automation\ai_client.py:28,33`

- [ ] **步骤 3.1：在 translate() 和 chat() 中添加 event**

修改 `ai_client.py`，在 `translate()` 方法（约 28 行）和 `chat()` 方法（约 33 行）内部，在调用 API 之前添加 event：

```python
    def translate(self, text: str, max_retries: int = None) -> str:
        from automation.progress import event
        event(f"调用 DeepSeek API 翻译 ({len(text)} 字符)")
        # ... 原代码

    def chat(self, prompt: str, max_retries: int = None, max_tokens: int = None) -> tuple:
        from automation.progress import event
        event(f"调用 DeepSeek Chat ({len(prompt)} 字符)")
        # ... 原代码
```

### 任务 4：在内容生成模块添加 event 输出

**文件：**
- 修改：`d:\project\bookfile_bat\automation\content_summarizer.py`
- 修改：`d:\project\bookfile_bat\automation\ai_copywriter.py`
- 修改：`d:\project\bookfile_bat\automation\image_generator.py`

- [ ] **步骤 4.1：在 content_summarizer.py 添加 import 和 event**

在 `content_summarizer.py` 顶部 import 区域添加：

```python
from automation.progress import event
```

在调用 AI 摘要的函数（约 `generate_summary` 内部）添加：

```python
        event("AI 摘要生成中...")
        # ... AI 调用
        event("摘要生成完成")
```

- [ ] **步骤 4.2：在 ai_copywriter.py 添加 import 和 event**

在 `ai_copywriter.py` 顶部 import 区域添加：

```python
from automation.progress import event
```

在 `generate_copywriting` 内部添加：

```python
    event("生成闲鱼文案...")
    # ... 调用 AI
    event("生成小红书文案...")
    # ... 调用 AI
```

- [ ] **步骤 4.3：在 image_generator.py 添加 import 和 event**

在 `image_generator.py` 顶部 import 区域添加：

```python
from automation.progress import event
```

在主图生成流程中（`generate_main_image` 内部）添加：

```python
    event("AI 设计主图方案...")
    # ... AI 调用
    event("渲染主图 HTML...")
    # ... playwright 调用
    event("合成主图...")
```

### 任务 5：清理与最终验证

- [ ] **步骤 5.1：删除残留的 Rich Progress 块**

在 `main.py` 中如果保留了原来的 `with Progress(...)` 块，应该删除或调整以避免重复输出。检查并清理：

```powershell
Select-String -Path d:\project\bookfile_bat\automation\main.py -Pattern "Progress|progress.update"
```

如果还残留多余的 `progress.update(task, ...)` 调用，删除。

- [ ] **步骤 5.2：运行所有测试最终验证**

```powershell
& "D:\project\bookfile_bat\.venv\Scripts\python.exe" -m pytest tests/ -v 2>&1 | Select-Object -Last 30
```

预期：所有测试通过。

- [ ] **步骤 5.3：手动验证（可选）**

```powershell
& "D:\project\bookfile_bat\.venv\Scripts\python.exe" -m automation.main --help
& "D:\project\bookfile_bat\.venv\Scripts\python.exe" -c "from automation.progress import phase, event; from automation.main import process; print('导入成功')"
```

预期：模块正常导入，无语法错误。

