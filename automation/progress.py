"""阶段进度输出工具

提供 phase() 上下文管理器和 event() 函数，
用于在耗时阶段开始/结束/关键事件输出信息到终端，
避免用户误以为系统卡死。
"""
import sys
import time
import threading
from contextlib import contextmanager


# 确保 stdout 使用 UTF-8 编码，支持 emoji
try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, OSError):
    pass  # Python < 3.7 或不支持 reconfigure


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
