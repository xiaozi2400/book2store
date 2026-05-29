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
        retries = max_retries or self.ai_config.get("retry_times", 3)
        result = self.translator.chat_raw(prompt, max_retries=retries, max_tokens=max_tokens)
        text = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        usage = result.get("usage", {})
        return text, usage

    def generate_summary(self, book_info: Dict[str, Any], content: str) -> Dict[str, Any]:
        """生成书籍摘要"""
        summarizer_cfg = config.summarizer_config()
        
        core_length = summarizer_cfg.get("core_insight_length", "300-500")
        chapter_length = summarizer_cfg.get("chapter_summary_length", "150-200")
        max_quotes = summarizer_cfg.get("max_quotes", 15)
        max_content = summarizer_cfg.get("max_content_length", 10000)
        
        prompt_template = summarizer_cfg.get("prompt", """你是一位专业的书籍摘要专家。请为以下书籍内容生成精简摘要：

【书名】: {title}
【作者】: {author}

【要求】:
1. 核心观点：用 {core_insight_length} 字概括全书核心思想
2. 章节摘要：为每个章节生成 {chapter_summary_length} 字摘要
3. 金句摘录：提取 {max_quotes} 条最有价值的句子
4. 适用人群：说明这本书适合谁阅读

【内容】:
{content}

请以以下 JSON 格式输出：
{{
    "core_insight": "全书核心观点...",
    "chapter_summaries": [
        {{"chapter": "第1章标题", "summary": "摘要..."}}
    ],
    "quotes": ["金句1", "金句2", ...],
    "target_audience": "适用人群..."
}}""")
        
        prompt = prompt_template.format(
            title=book_info.get('title', 'Unknown'),
            author=book_info.get('author', 'Unknown'),
            core_insight_length=core_length,
            chapter_summary_length=chapter_length,
            max_quotes=max_quotes,
            content=content[:max_content]
        )

        response, _ = self.chat(prompt, max_tokens=2000)
        return self._parse_json_response(response)

    def generate_xianyu_listing(self, book_info: Dict[str, Any]) -> str:
        """生成闲鱼商品文案，返回原始文案文本"""
        copywriting_cfg = config.copywriting_config
        prompt_template = copywriting_cfg.get(
            "xianyu_listing_prompt",
            "你是一个闲鱼二手书卖家。用户提供了以下书籍信息：\n\n书名：{title}\n作者：{author}\n\n请你执行以下步骤：\n\n## 1、自动搜索（真实优先）\n\n..."
        )

        prompt = prompt_template.format(
            title=book_info.get('title', 'Unknown'),
            author=book_info.get('author', 'Unknown'),
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
