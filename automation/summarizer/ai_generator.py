"""
AI摘要生成模块 - 调用 AI 生成书籍摘要
"""
import os
import sys
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from automation.ai_client import AIClient
from automation.database import DatabaseManager
from automation.config import config
from automation.summarizer.template_generator import TemplateGenerator, detect_and_generate_prompt
from automation.utils import logger


class SummaryAIGenerator:
    """AI摘要生成器"""

    def __init__(self):
        self.ai = AIClient()
        self.db = DatabaseManager()
        self.template_gen = TemplateGenerator()

    def generate(self, book_id: str, book_info: Dict, chapters: list, suitability_result=None) -> Optional[Dict[str, Any]]:
        """使用AI生成摘要"""
        combined_content = "\n\n".join([
            f"{ch['title']}:\n{ch['content'][:5000]}"
            for ch in chapters[:8]
        ])

        logger.info(f"提取章节数量: {len(chapters)}, 总内容长度: {len(combined_content)}")

        if len(combined_content) < 100:
            logger.warning(f"章节内容过少: {combined_content}")

        book_type = self.template_gen.detect_book_type(book_info)

        logger.info(f"检测到书籍类型: {book_type}")

        template_result = self.template_gen.detect_and_generate_prompt(book_info)

        try:
            prompt = self._build_summary_prompt(book_info, combined_content, template_result.prompt_for_ai)

            prompt_len = len(prompt)
            logger.info(f"精简版生成提示词: 长度={prompt_len}, 前500字符: {prompt[:500]}")

            logger.info("开始调用AI...")
            result, usage = self.ai.chat(prompt, max_tokens=15000)
            logger.info(f"AI调用完成, 返回长度: {len(result) if result else 0}")

            if usage:
                self.db.record_token_usage(
                    book_id, "summarizing",
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0)
                )

            logger.info(f"精简版AI响应（前500字符）: {str(result)[:500] if result else '空'}")

            if not result or 'error' in str(result).lower():
                warn_msg = f"AI生成失败，返回结果为空或包含错误: result长度={len(result) if result else 0}，使用默认摘要"
                logger.warning(warn_msg)
                self.db.add_log(book_id, "summarizing", "warning", warn_msg)
                return self._get_default_summary(book_info, chapters)

            parsed_result = self._parse_summary_result(result)

            final_content = parsed_result.get('content', result)
            logger.info(f"解析后内容长度: {len(final_content) if final_content else 0}")

            return {
                'title': book_info.get('title', 'Unknown'),
                'author': book_info.get('author', 'Unknown'),
                'book_type': book_type,
                'content': final_content
            }

        except Exception as e:
            error_msg = f"精简版生成失败: {str(e)}"
            logger.error(error_msg)
            self.db.add_log(book_id, "summarizing", "failed", error_msg)
            self.db.update_book_status(book_id, "failed", error_msg)
            return None

    def _build_summary_prompt(self, book_info: Dict, content: str, template_prompt: str) -> str:
        """构建摘要生成提示词 - 替换所有占位符"""
        summarizer_cfg = config.summarizer_config()

        try:
            return template_prompt.format(
                title=book_info.get('title', '未知书籍'),
                author=book_info.get('author', '未知作者'),
                core_insight_length=summarizer_cfg.get('core_insight_length', '300-500'),
                chapter_summary_length=summarizer_cfg.get('chapter_summary_length', '150-200'),
                max_quotes=summarizer_cfg.get('max_quotes', 15),
                content=content
            )
        except KeyError as e:
            logger.warning(f"提示词占位符替换失败，使用默认值: {e}")
            return template_prompt.replace("{content}", content)

    def _parse_summary_result(self, result: str) -> Dict[str, Any]:
        """解析AI返回的结果"""
        import json
        import re

        stripped = result.strip()
        if stripped.startswith('#') or stripped.startswith('##') or stripped.startswith('- '):
            return {'content': result}

        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass

        return {'content': result}

    @staticmethod
    def _get_default_summary(book_info: Dict, chapters: list) -> Dict[str, Any]:
        """获取默认摘要 - 新格式支持 Markdown"""
        chapter_texts = "\n\n".join([
            f"## {ch['title']}\n\n{ch['content'][:500]}"
            for ch in chapters[:5]
        ])

        default_content = f"""## 核心观点

本书包含丰富的知识和见解，值得深入阅读。

{chapter_texts}

## 总结

本书是关于{book_info.get('title', '该主题')}的专业书籍，适合对相关领域感兴趣的读者学习参考。
"""

        return {
            'title': book_info.get('title', 'Unknown'),
            'author': book_info.get('author', 'Unknown'),
            'content': default_content
        }
