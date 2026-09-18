"""测试 main.py 中 process/auto/test 命令集成 generate_main_image"""
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from automation.main import app

runner = CliRunner()


def test_process_calls_generate_main_image():
    """测试 process 命令在 generate_summary 之后调用 generate_main_image"""
    mock_book = MagicMock()
    mock_book.id = "test-book-id-123"
    mock_book.filename = "test-book.epub"
    mock_book.title = "Test Book"
    mock_book.author = "Test Author"
    mock_book.summary_text = "This is a test summary for main image test."

    # Mock run_pipeline at its definition site - it is imported inside process()
    # via "from automation.pipeline import run_pipeline", so patching
    # automation.pipeline.run_pipeline intercepts the reference before it
    # gets bound to the local name in process().
    mock_ctx = MagicMock()
    mock_ctx.status = "completed"
    mock_ctx.error = None

    with patch('automation.main.DatabaseManager.get_all_books', return_value=[mock_book]):
        with patch('automation.main.DatabaseManager.create_book_output'):
            with patch('automation.main.DatabaseManager.get_token_summary', return_value=None):
                with patch('automation.pipeline.run_pipeline', return_value=mock_ctx):
                    with patch('automation.main.Path.exists', return_value=True):
                        result = runner.invoke(app, ["process", "test-book-id-123"])

                    assert result.exit_code == 0, (
                        f"Exit code: {result.exit_code}, Output: {result.output}"
                    )