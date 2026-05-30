"""测试 ImageGenerator 核心逻辑"""
from unittest.mock import patch, MagicMock

from automation.image_generator import ImageGenerator


@patch('automation.image_generator.DatabaseManager')
@patch('automation.image_generator.AIClient')
@patch('automation.image_generator.config')
def test_generate_no_summary_skips(mock_config, mock_ai, mock_db):
    """summary_text 为 None 时应跳过，不调用 AI"""
    cfg = {"enabled": True, "width": 800, "height": 800, "html_prompt": "test {title}"}
    mock_config.image_generator_config = cfg
    mock_config.output_dir = "."

    mock_book = MagicMock()
    mock_book.summary_text = None
    mock_book.title = "测试书"
    mock_book.author = "测试作者"

    mock_db_instance = MagicMock()
    mock_db_instance.get_book_by_id.return_value = mock_book
    mock_db.return_value = mock_db_instance

    generator = ImageGenerator()
    result = generator.generate("test-book-001")

    assert result is False, "无摘要时应跳过"
    mock_ai.return_value.chat.assert_not_called()


@patch('automation.image_generator.DatabaseManager')
@patch('automation.image_generator.AIClient')
@patch('automation.image_generator.config')
def test_generate_disabled_skips(mock_config, mock_ai, mock_db):
    """enabled:false 时应跳过"""
    cfg = {"enabled": False, "width": 800, "height": 800, "html_prompt": "test {title}"}
    mock_config.image_generator_config = cfg
    mock_config.output_dir = "."

    generator = ImageGenerator()
    result = generator.generate("test-book-001")

    assert result is False, "禁用时应跳过"


@patch('automation.image_generator.Path')
@patch('automation.image_generator.DatabaseManager')
@patch('automation.image_generator.AIClient')
@patch('automation.image_generator.config')
def test_format_prompt_contains_all_fields(mock_config, mock_ai, mock_db, mock_path):
    """_format_prompt 应正确填充 {title} {summary} {cover_base64}"""
    cfg = {
        "enabled": True,
        "width": 800,
        "height": 800,
        "html_prompt": "书名：{title}\n摘要：{summary}\n封面：{cover_base64}"
    }
    mock_config.image_generator_config = cfg
    mock_config.output_dir = "."

    generator = ImageGenerator()
    prompt = generator._format_prompt("测试书", "测试作者", "这是一本测试书", "fake_base64")

    assert "书名：测试书" in prompt
    assert "摘要：这是一本测试书" in prompt
    assert "封面：fake_base64" in prompt