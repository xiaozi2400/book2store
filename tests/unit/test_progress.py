"""测试 progress 模块的阶段输出"""
import re
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
    # 包含耗时数字，排除极端情况
    assert "s)" in captured.out or "ms)" in captured.out
    # 确保不出现异常耗时（如 1000s），排除极端慢的情况
    import re
    match = re.search(r'\d+\.?\d*\s*ms\)|(\d+\.?\d*)\s*s\)', captured.out)
    if match:
        value = float(match.group(1) or match.group().replace('ms)', '').replace('s)', ''))
        unit = 'ms' if 'ms' in match.group() else 's'
        if unit == 's':
            assert value < 60, f"耗时 {value}s 超过 60s，可能是 CI 慢导致的误报"
        else:
            assert value < 60000, f"耗时 {value}ms 超过 60s"


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
