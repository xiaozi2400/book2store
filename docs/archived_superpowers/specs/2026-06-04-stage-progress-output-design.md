# 阶段进度输出优化 — 设计文档

**日期**：2026-06-04
**状态**：待批准

---

## 目标

在每个耗时阶段的**开始、结束、关键中间事件**输出信息到终端，避免用户误以为系统卡死。

## 设计

### 核心模块

新建 `automation/progress.py`，提供：

1. **`phase(name)` 上下文管理器**
   - 进入时输出：`⏳ 正在{name}...`
   - 正常退出时输出：`✓ {name}完成 ({耗时})`
   - 异常退出时输出：`✗ {name}失败 ({异常})`
   - 支持嵌套：自动缩进展示层级

2. **`@phase(name)` 装饰器**
   - 等价于 `with phase(name):` 包裹整个函数

3. **`event(message, level='info')` 函数**
   - 阶段内输出关键事件：`  └─ {message}`
   - 不显示耗时（区别于 phase）

### 输出格式

```
⏳ 正在翻译...
  ⏳ 正在 EPUB 解析...
  ✓ EPUB 解析 完成 (0.3s)
  ⏳ 正在 AI 翻译...
    └─ 调用 DeepSeek API (32 段落)...
    └─ 解析响应: 28/32 成功
  ✓ AI 翻译 完成 (1分 23秒)
✓ 翻译 完成 (1分 24秒)
```

### 辅助函数实现要点

```python
# automation/progress.py
import time
import sys
import threading
from contextlib import contextmanager

_PHASE_INDENT = [0]  # 用列表避免 nonlocal
_INDENT_LOCK = threading.Lock()

def _format_duration(seconds):
    """格式化耗时：< 1秒显示小数，否则显示 分秒"""
    if seconds < 1:
        return f"{seconds:.1f}s"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}分 {secs}秒"

@contextmanager
def phase(name):
    indent = "  " * _PHASE_INDENT[0]
    start = time.time()
    print(f"{indent}⏳ 正在{name}...")
    sys.stdout.flush()
    with _INDENT_LOCK:
        _PHASE_INDENT[0] += 1
    try:
        yield
        elapsed = time.time() - start
        print(f"{indent}✓ {name}完成 ({_format_duration(elapsed)})")
    except Exception as e:
        elapsed = time.time() - start
        print(f"{indent}✗ {name}失败: {type(e).__name__}: {str(e)[:200]}")
        raise
    finally:
        with _INDENT_LOCK:
            _PHASE_INDENT[0] -= 1
        sys.stdout.flush()

def event(message):
    """阶段内的关键事件输出"""
    indent = "  " * _PHASE_INDENT[0]
    print(f"{indent}  └─ {message}")
    sys.stdout.flush()

def phase_decorator(name):
    """装饰器形式的 phase"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with phase(name):
                return func(*args, **kwargs)
        return wrapper
    return decorator
```

## 阶段识别（基于 main.py 当前流程）

| 主阶段 | 子阶段 | 典型耗时 |
|-------|-------|---------|
| 翻译 | EPUB 解析 / AI 翻译 / EPUB 生成 / 质量检查 | 5-30 分钟 |
| 生成 PDF | 英文 / 中文 / 双语 / 精简版 | 1-3 分钟 |
| 适合度评估 | AI 评估 | 10-30 秒 |
| 生成精简版 | AI 摘要 | 30-60 秒 |
| 生成主图 | AI 设计 / 渲染 / 合成 | 30-90 秒 |
| 提取图片 | PDF 图片提取 | 5-15 秒 |
| 生成文案 | 闲鱼文案 / 小红书文案 | 20-40 秒 |
| 发布到闲鱼 | 登录 / 上传 / 发布 | 30-60 秒 |

## 改动范围

| 文件 | 改动 |
|------|------|
| `automation/progress.py` | **新建** —— 辅助函数 |
| `automation/main.py` | 用 `phase()` 包裹主要步骤 |
| `automation/ai_client.py` | 关键 API 调用处加 `event()` |
| `automation/ai_copywriter.py` | 同上 |
| `automation/image_generator.py` | 同上 |
| `automation/content_summarizer.py` | 同上 |
| `automation/xianyu_publisher.py` | 同上 |

## 错误处理

- `phase()` 内部异常时显示 `✗ 阶段名失败: {异常类型}: {消息}`
- 异常会重新抛出，不改变原有错误流
- 嵌套 phase 失败时，最外层会显示所有内层失败状态

## 关键决策

1. **使用 `print` 而非 `logger`**：阶段信息要实时显示到终端，不受 StreamHandler WARNING 过滤影响
2. **保留现有 `print`**：避免替换现有 `print` 调用造成行为变化
3. **不依赖第三方库**：避免引入 rich 等新依赖
4. **线程安全**：用 `threading.Lock` 保护缩进计数（因为 ThreadPoolExecutor 可能会并行调用）

## 测试

1. **单元测试**：`progress.py` 的 `phase`/`event` 函数
   - 测试正常流程的开始/结束输出
   - 测试异常的显示
   - 测试嵌套缩进
   - 测试耗时格式化

2. **集成测试**：在 `main.py` 模拟一次完整处理流程
   - 验证终端输出包含所有阶段标记
   - 验证嵌套缩进正确

## 不在范围

- 不替换现有 `print` 和 `logger.info` 调用
- 不修改 `setup_logging()` 行为
- 不添加 rich 等第三方库
- 不做阶段超时报警（仅在异常时输出）
