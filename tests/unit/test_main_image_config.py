"""测试图片生成器配置"""

from automation.config import Config


def test_image_generator_config_exists():
    """验证 image_generator 配置存在"""
    config = Config()
    image_gen_config = config.image_generator_config
    assert isinstance(image_gen_config, dict)
    assert len(image_gen_config) > 0


def test_image_generator_has_prompt():
    """验证提示词包含 {title} {summary} 占位符"""
    config = Config()
    html_prompt = config.image_generator_config.get("html_prompt", "")
    assert "{title}" in html_prompt
    assert "{summary}" in html_prompt


def test_image_generator_has_dimensions():
    """验证 width=800 height=800"""
    config = Config()
    assert config.image_generator_config.get("width") == 800
    assert config.image_generator_config.get("height") == 800
