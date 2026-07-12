"""测试 AIClient 传递摘要到闲鱼提示词"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch
from automation.ai_client import AIClient


@patch('automation.ai_client.AIClient.chat')
@patch('automation.ai_client.config')
def test_generate_xianyu_listing_passes_summary(mock_config, mock_chat):
    mock_chat.return_value = ("测试文案", {})
    mock_config.ai_config = {"provider": "deepseek"}
    mock_config.copywriting_config = {
        "xianyu_listing_prompt": "书名：{title}\n作者：{author}\n摘要：{summary}"
    }

    client = AIClient()
    book_info = {
        'title': '测试书',
        'author': '测试作者',
        'summary': '这是一本关于测试的书'
    }
    client.generate_xianyu_listing(book_info)

    args, _ = mock_chat.call_args
    prompt = args[0]
    assert "这是一本关于测试的书" in prompt, f"摘要应出现在提示词中, 实际: {prompt}"


@patch('automation.ai_client.AIClient.chat')
@patch('automation.ai_client.config')
def test_generate_xianyu_listing_handles_missing_summary(mock_config, mock_chat):
    mock_chat.return_value = ("测试文案", {})
    mock_config.ai_config = {"provider": "deepseek"}
    mock_config.copywriting_config = {
        "xianyu_listing_prompt": "书名：{title}\n摘要：{summary}"
    }

    client = AIClient()
    book_info = {'title': '测试书', 'author': '测试作者'}
    client.generate_xianyu_listing(book_info)

    args, _ = mock_chat.call_args
    prompt = args[0]
    assert "暂无摘要信息" in prompt, f"无摘要时应有默认值, 实际: {prompt}"