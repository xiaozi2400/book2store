"""测试 main.py 中 process/auto/test 命令的 summary 字段传递"""
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from automation.main import app

runner = CliRunner()


def test_process_command_passes_summary_to_copywriting():
    """测试 process 命令调用 generate_copywriting 时，book_info 包含 summary 字段"""
    mock_book = MagicMock()
    mock_book.id = "test-book-id-123"
    mock_book.filename = "test-book.epub"
    mock_book.title = "Test Book"
    mock_book.author = "Test Author"
    mock_book.summary_text = "This is a test summary content for the book."

    with patch('automation.main.DatabaseManager.get_all_books', return_value=[mock_book]):
        with patch('automation.main.DatabaseManager.create_book_output'):
            with patch('automation.main.DatabaseManager.get_token_summary', return_value=None):
                with patch('automation.main.generate_copywriting') as mock_gen:
                    with patch('automation.translation_processor.translate_book'):
                        with patch('automation.main.generate_summary'):
                            with patch('automation.main.extract_images'):
                                with patch('automation.main.publish_to_xianyu'):
                                    with patch('automation.main.Path.exists', return_value=True):
                                        result = runner.invoke(app, ["process", "test-book-id-123"])

                                        assert result.exit_code == 0, (
                                            f"Exit code: {result.exit_code}, Output: {result.output}"
                                        )

                                        mock_gen.assert_called_once()
                                        args, kwargs = mock_gen.call_args
                                        book_id_arg, book_info_arg = args

                                        assert 'summary' in book_info_arg, (
                                            f"book_info should contain 'summary' field, got {book_info_arg}"
                                        )
                                        assert book_info_arg['summary'] == 'This is a test summary content for the book.', (
                                            f"summary mismatch, got {book_info_arg['summary']}"
                                        )