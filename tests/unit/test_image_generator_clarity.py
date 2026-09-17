"""测试 ImageGenerator 截图参数透传(清晰度优化)"""
import sys, os
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from automation.image_generator import ImageGenerator


def _build_generator_with_config(cfg: dict) -> ImageGenerator:
    """构造一个 ImageGenerator,通过 mock 让 config 可控"""
    with patch('automation.image.image_generator.config') as mock_config, \
         patch('automation.image.image_generator.AIClient'), \
         patch('automation.image.image_generator.DatabaseManager'):
        mock_config.image_generator_config = cfg
        mock_config.output_dir = "."
        gen = ImageGenerator()
    return gen


@patch('playwright.sync_api.sync_playwright')
def test_screenshot_passes_device_scale_factor(mock_sync_playwright):
    """device_scale_factor 应透传到 browser.new_page"""
    cfg = {
        "enabled": True, "width": 800, "height": 800,
        "device_scale_factor": 2, "screenshot_quality": 92,
    }
    gen = _build_generator_with_config(cfg)

    # 构造 playwright mock 链
    mock_container = MagicMock()
    mock_page = MagicMock()
    mock_page.query_selector_all.return_value = [mock_container]
    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page

    mock_p = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser
    mock_sync_playwright.return_value.__enter__.return_value = mock_p

    # 调 _screenshot_html,output_dir 用一个临时目录
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        gen._screenshot_html(
            html="<html><body><div class='page'></div></body></html>",
            output_dir=__import__('pathlib').Path(tmp),
            img_cfg=cfg,
        )

    # 断言:new_page 收到 viewport + device_scale_factor
    kwargs = mock_browser.new_page.call_args.kwargs
    assert kwargs.get("viewport") == {"width": 800, "height": 800}, \
        f"viewport 应是 {{'width': 800, 'height': 800}},实际 {kwargs.get('viewport')}"
    assert kwargs.get("device_scale_factor") == 2, \
        f"device_scale_factor 应是 2,实际 {kwargs.get('device_scale_factor')}"


@patch('playwright.sync_api.sync_playwright')
def test_screenshot_passes_jpeg_quality(mock_sync_playwright):
    """screenshot_quality 应透传到 container.screenshot 的 type/quality"""
    cfg = {
        "enabled": True, "width": 800, "height": 800,
        "device_scale_factor": 2, "screenshot_quality": 92,
    }
    gen = _build_generator_with_config(cfg)

    mock_container = MagicMock()
    mock_page = MagicMock()
    mock_page.query_selector_all.return_value = [mock_container]
    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page

    mock_p = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser
    mock_sync_playwright.return_value.__enter__.return_value = mock_p

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        gen._screenshot_html(
            html="<html><body><div class='page'></div></body></html>",
            output_dir=__import__('pathlib').Path(tmp),
            img_cfg=cfg,
        )

    # 断言:container.screenshot 收到 type='jpeg' + quality=92
    ckwargs = mock_container.screenshot.call_args.kwargs
    assert ckwargs.get("type") == "jpeg", \
        f"screenshot type 应是 'jpeg',实际 {ckwargs.get('type')}"
    assert ckwargs.get("quality") == 92, \
        f"screenshot quality 应是 92,实际 {ckwargs.get('quality')}"


@patch('playwright.sync_api.sync_playwright')
def test_screenshot_defaults_when_config_missing(mock_sync_playwright):
    """config 缺新字段时,默认值应为 device_scale_factor=2, quality=92"""
    cfg = {"enabled": True, "width": 800, "height": 800}  # 无新字段
    gen = _build_generator_with_config(cfg)

    mock_container = MagicMock()
    mock_page = MagicMock()
    mock_page.query_selector_all.return_value = [mock_container]
    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page

    mock_p = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser
    mock_sync_playwright.return_value.__enter__.return_value = mock_p

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        gen._screenshot_html(
            html="<html><body><div class='page'></div></body></html>",
            output_dir=__import__('pathlib').Path(tmp),
            img_cfg=cfg,
        )

    kwargs = mock_browser.new_page.call_args.kwargs
    assert kwargs.get("device_scale_factor") == 2, \
        f"缺省时 device_scale_factor 应是 2,实际 {kwargs.get('device_scale_factor')}"

    ckwargs = mock_container.screenshot.call_args.kwargs
    assert ckwargs.get("type") == "jpeg", "缺省时 type 应是 jpeg"
    assert ckwargs.get("quality") == 92, f"缺省时 quality 应是 92,实际 {ckwargs.get('quality')}"
