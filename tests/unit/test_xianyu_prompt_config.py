"""测试闲鱼提示词配置"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from automation.config import config


def test_xianyu_prompt_contains_summary_placeholder():
    prompt = config.copywriting_config.get("xianyu_listing_prompt", "")
    assert "{summary}" in prompt, "闲鱼提示词应包含 {summary} 占位符"


def test_xianyu_prompt_no_search():
    prompt = config.copywriting_config.get("xianyu_listing_prompt", "")
    assert "搜索" not in prompt and "联网" not in prompt, "闲鱼提示词不应包含联网搜索指令"


def test_xianyu_prompt_keeps_required_sections():
    prompt = config.copywriting_config.get("xianyu_listing_prompt", "")
    required_sections = ["作者简介", "适合谁看", "爆款标题", "核心内容", "优点", "缺点"]
    for section in required_sections:
        assert section in prompt, f"提示词应包含「{section}」模块"
