"""
AI客户端封装 - 支持多种AI翻译提供商
"""
import os
import sys
from typing import Optional, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 先读取 config.yaml 并设置环境变量，再导入 Translator
from .config import config
os.environ["TRANSLATION_PROVIDER"] = config.ai_config.get("provider", "deepseek")

from ebook_translator.translator.translator import Translator


class AIClient:
    """AI客户端封装"""

    def __init__(self, provider: str = None):
        self.ai_config = config.ai_config

        self.provider = provider or self.ai_config.get("provider", "deepseek")

        self.translator = Translator(self.provider)
        print(f"[AI Client] 使用 {self.provider.upper()} 模型")

    def translate(self, text: str, max_retries: int = None) -> str:
        """翻译文本"""
        retries = max_retries or self.ai_config.get("retry_times", 3)
        return self.translator.translate(text, max_retries=retries)

    def chat(self, prompt: str, max_retries: int = None, max_tokens: int = None) -> tuple:
        """通用对话，返回 (text, usage)"""
        from automation.progress import event
        event(f"调用 DeepSeek Chat ({len(prompt)} 字符)")
        retries = max_retries or self.ai_config.get("retry_times", 3)
        result = self.translator.chat_raw(prompt, max_retries=retries, max_tokens=max_tokens)
        text = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        usage = result.get("usage", {})
        return text, usage

    def generate_xianyu_listing(self, book_info: Dict[str, Any]) -> str:
        """生成闲鱼商品文案，返回原始文案文本"""
        copywriting_cfg = config.copywriting_config
        prompt_template = copywriting_cfg.get(
            "xianyu_listing_prompt",
            "你是一个闲鱼二手书卖家。用户提供了以下书籍信息：\n\n书名：{title}\n作者：{author}\n摘要：{summary}"
        )

        prompt = prompt_template.format(
            title=book_info.get('title', 'Unknown'),
            author=book_info.get('author', 'Unknown'),
            summary=book_info.get('summary', '暂无摘要信息'),
        )

        return self.chat(prompt)

    def generate_xiaohongshu_note(self, book_info: Dict[str, Any]) -> str:
        """生成小红书种草笔记"""
        copywriting_cfg = config.copywriting_config
        prompt_template = copywriting_cfg.get(
            "xiaohongshu_note_prompt",
            "你是一位小红书读书博主。请为《{title}》生成种草笔记。"
        )

        summary = book_info.get('summary', '')

        prompt = prompt_template.format(
            title=book_info.get('title', 'Unknown'),
            author=book_info.get('author', 'Unknown'),
            summary=summary,
        )

        return self.chat(prompt, max_tokens=2000)

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """解析JSON响应"""
        import re

        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        match = re.search(json_pattern, response, re.DOTALL)

        if match:
            import json
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return {
            "error": "解析失败",
            "raw_response": response[:500]
        }
