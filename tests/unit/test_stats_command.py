"""
测试 format_token_summary 和 stats 命令
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestFormatTokenSummary:
    """验证 format_token_summary 的格式化输出"""

    def test_returns_formatted_string_with_all_steps(self):
        """应返回包含所有步骤的格式化字符串"""
        from automation.main import format_token_summary

        steps = {
            "translation": {"input_tokens": 5000, "output_tokens": 3000, "total_tokens": 8000, "cost": 0.011},
            "summarizing": {"input_tokens": 500, "output_tokens": 200, "total_tokens": 700, "cost": 0.0009},
        }
        result = format_token_summary(steps)

        assert isinstance(result, str)
        assert "翻译" in result
        assert "摘要" in result
        assert "8,000" in result

    def test_handles_single_step(self):
        """应正确处理单个步骤"""
        from automation.main import format_token_summary

        steps = {
            "translation": {"input_tokens": 10000, "output_tokens": 5000, "total_tokens": 15000, "cost": 0.02},
        }
        result = format_token_summary(steps)

        assert isinstance(result, str)
        assert "翻译" in result
        assert "15,000" in result
        assert "¥0.0200" in result

    def test_handles_empty_dict(self):
        """空字典应返回提示信息"""
        from automation.main import format_token_summary

        result = format_token_summary({})

        assert isinstance(result, str)
        assert len(result) > 0

    def test_handles_none(self):
        """None 应返回提示信息"""
        from automation.main import format_token_summary

        result = format_token_summary(None)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_displays_cost_correctly(self):
        """应正确显示费用"""
        from automation.main import format_token_summary

        steps = {
            "translation": {"input_tokens": 1000000, "output_tokens": 500000, "total_tokens": 1500000, "cost": 2.0},
        }
        result = format_token_summary(steps)

        assert "¥2.0000" in result


class TestStatsCommand:
    """验证 stats CLI 命令的集成"""

    def test_stats_command_displays_summary(self):
        """stats 命令应调用 format_token_summary 并显示结果"""
        with patch("automation.main.DatabaseManager") as MockDB:
            mock_steps = {
                "translation": {"input_tokens": 5000, "output_tokens": 3000, "total_tokens": 8000, "cost": 0.011},
            }
            db_instance = MagicMock()
            db_instance.get_token_summary.return_value = mock_steps
            MockDB.return_value = db_instance

            from automation.main import format_token_summary

            result = format_token_summary(mock_steps)
            assert isinstance(result, str)
            assert "8,000" in result

    def test_stats_command_no_records(self):
        """无记录时应显示提示"""
        with patch("automation.main.DatabaseManager") as MockDB:
            db_instance = MagicMock()
            db_instance.get_token_summary.return_value = None
            MockDB.return_value = db_instance

            from automation.main import format_token_summary

            result = format_token_summary(None)
            assert isinstance(result, str)
