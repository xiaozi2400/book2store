"""测试闲鱼发布时使用主图"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pathlib import Path
from unittest.mock import patch, MagicMock
from automation.xianyu_publisher import XianyuPublisher


@patch('automation.xianyu_publisher.XianyuPublisher._close')
@patch('automation.xianyu_publisher.XianyuPublisher._start_browser')
@patch('automation.xianyu_publisher.XianyuPublisher._login')
@patch('automation.xianyu_publisher.XianyuPublisher._navigate_to_publish')
@patch('automation.xianyu_publisher.XianyuPublisher._fill_description')
@patch('automation.xianyu_publisher.XianyuPublisher._select_category')
@patch('automation.xianyu_publisher.XianyuPublisher._setup_skus')
@patch('automation.xianyu_publisher.XianyuPublisher._submit_and_get_url')
@patch('automation.xianyu_publisher.XianyuPublisher._save_result')
@patch('automation.xianyu_publisher.DatabaseManager')
@patch('automation.xianyu_publisher.config')
def test_publish_uses_main_images_when_available(
    mock_config, mock_db,
    mock_save, mock_submit, mock_skus, mock_category, mock_desc,
    mock_navigate, mock_login, mock_browser, mock_close
):
    """有主图时应优先上传主图序列，而非 cover.jpg"""
    mock_config.output_dir = "."
    mock_config.xianyu_cookie_path = "cookie.json"
    mock_config.get.side_effect = lambda key, default=None: {"xianyu.headless": True}.get(key, default)

    mock_book = MagicMock()
    mock_book.filename = "test.epub"
    mock_db_instance = MagicMock()
    mock_db_instance.get_book_by_id.return_value = mock_book
    mock_db.return_value = mock_db_instance

    meta_dir = Path("test_metadata")
    meta_dir.mkdir(exist_ok=True)
    (meta_dir / "xianyu_listing.txt").write_text("测试文案", encoding="utf-8")
    (meta_dir / "main_image_01.jpg").write_text("img1", encoding="utf-8")
    (meta_dir / "main_image_02.jpg").write_text("img2", encoding="utf-8")

    publisher = XianyuPublisher()
    publisher.page = MagicMock()
    file_input_mock = publisher.page.locator.return_value.first

    try:
        publisher.publish("test-book-001")
    except Exception:
        pass

    # 验证上传调用中使用了主图文件（使用预先保存的 mock 引用）
    call_args = file_input_mock.set_input_files.call_args
    assert call_args is not None, "set_input_files 未被调用，说明未上传主图"
    img_paths = [str(p) for p in call_args[0][0]]
    assert any("main_image_01.jpg" in p for p in img_paths), f"应上传主图, 实际: {img_paths}"

    # 清理
    import shutil
    shutil.rmtree(meta_dir, ignore_errors=True)