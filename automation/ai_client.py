"""
AI客户端封装 - 复用现有DeepSeek翻译器
"""
import os
import sys
from typing import Optional, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ebook_translator.translator.deepseek_api import DeepSeekTranslator
from .config import config


class AIClient:
    """AI客户端封装"""

    def __init__(self):
        self.translator = DeepSeekTranslator()
        self.ai_config = config.ai_config

    def translate(self, text: str, max_retries: int = None) -> str:
        """翻译文本"""
        retries = max_retries or self.ai_config.get("retry_times", 3)
        return self.translator.translate(text, max_retries=retries)

    def generate_summary(self, book_info: Dict[str, Any], content: str) -> Dict[str, Any]:
        """生成书籍摘要"""

        prompt = f"""你是一位专业的书籍摘要专家。请为以下书籍内容生成精简摘要：

【书名】: {book_info.get('title', 'Unknown')}
【作者】: {book_info.get('author', 'Unknown')}

【要求】:
1. 核心观点：用 300-500 字概括全书核心思想
2. 章节摘要：为每个章节生成 150-200 字摘要
3. 金句摘录：提取 10-15 条最有价值的句子
4. 适用人群：说明这本书适合谁阅读

【内容】:
{content[:10000]}

请以以下 JSON 格式输出：
{{
    "core_insight": "全书核心观点...",
    "chapter_summaries": [
        {{"chapter": "第1章标题", "summary": "摘要..."}}
    ],
    "quotes": ["金句1", "金句2", ...],
    "target_audience": "适用人群..."
}}"""

        response = self.translate(prompt)
        return self._parse_json_response(response)

    def generate_xianyu_listing(self, book_info: Dict[str, Any]) -> Dict[str, Any]:
        """生成闲鱼商品文案"""

        prompt = f"""你是一位闲鱼电商文案专家。请为以下书籍生成商品文案：

【书名】: {book_info.get('title', 'Unknown')}
【作者】: {book_info.get('author', 'Unknown')}

【SKU信息】:
- 纯英文原版 PDF: ¥3.99
- 完整套装(英文+中文+双语+精简版): ¥8.99

【要求】:
1. 标题：25-30字，吸引人，包含关键词
2. 描述：
   - 第一段：书籍价值和亮点
   - 第二段：包含内容说明（4个版本）
   - 第三段：购买须知和发货方式
3. 标签：5-8个相关标签
4. 语气：专业、友好、有说服力

请按以下 JSON 格式输出：
{{
    "title": "商品标题",
    "description": "商品描述（多段）",
    "tags": ["标签1", "标签2", ...]
}}"""

        response = self.translate(prompt)
        return self._parse_json_response(response)

    def generate_xiaohongshu_note(self, book_info: Dict[str, Any]) -> str:
        """生成小红书种草笔记"""

        prompt = f"""你是一位小红书读书博主。请为《{book_info.get('title', 'Unknown')}》生成种草笔记。

【作者】: {book_info.get('author', 'Unknown')}
【核心观点】: {book_info.get('summary', '暂无')}

【要求】:
1. 标题：爆款风格，带 emoji，20字内
2. 正文：
   - 开头：痛点引入或金句
   - 中间：书籍介绍 + 核心价值
   - 结尾：推荐理由 + 获取方式
3. 使用 emoji 增加可读性
4. 添加相关话题标签（#读书 #好书推荐 等）
5. 语气：亲切、真实、像朋友推荐

请按 Markdown 格式输出。"""

        return self.translate(prompt)

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
