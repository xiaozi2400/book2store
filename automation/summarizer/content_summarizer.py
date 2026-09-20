"""
内容精简器 - 生成书籍核心内容精简版PDF（主编排器）
"""

import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from automation.config import config
from automation.database import DatabaseManager
from automation.summarizer.ai_generator import SummaryAIGenerator
from automation.summarizer.chapter_extractor import (
    extract_chapters,
    extract_chinese_title,
)
from automation.summarizer.cover_extractor import extract_cover_from_epub
from automation.summarizer.pdf_generator import SummaryPDFGenerator
from automation.summarizer.suitability_evaluator import SuitabilityEvaluator
from automation.utils import ensure_dir, logger


class ContentSummarizer:
    """内容精简器 - 主编排器"""

    def __init__(self):
        self.db = DatabaseManager()
        self.output_dir = Path(config.output_dir)
        self.evaluator = SuitabilityEvaluator()
        self.ai_generator = SummaryAIGenerator()
        self.pdf_generator = SummaryPDFGenerator()

    def summarize(self, book_id: str, epub_path: str) -> bool:
        """生成书籍精简版"""
        from automation.progress import event

        logger.info(f"开始生成精简版: {book_id}")

        try:
            self.db.update_book_status(book_id, "summarizing")
            self.db.add_log(book_id, "summarizing", "start", "开始生成精简版")

            output_dir = ensure_dir(self.output_dir / Path(epub_path).stem.strip())
            _base_name = Path(epub_path).stem.strip()
            output_path = output_dir / "精简版.pdf"

            if output_path.exists():
                logger.info(f"精简版已存在，将重新生成: {output_path}")
                output_path.unlink()

            book = self.db.get_book_by_id(book_id)
            if not book:
                all_books = self.db.get_all_books()
                book = all_books[0] if all_books else None

            if book:
                book.title = book.title or "Unknown"
                book.author = book.author or "Unknown"

            book_info = {
                "title": book.title if book else "书籍",
                "author": book.author if book else "Unknown",
                "summary": book.summary if book and hasattr(book, "summary") else "",
            }

            chinese_title = extract_chinese_title(book_id, epub_path)
            if chinese_title:
                book_info["title"] = chinese_title

            if output_path.exists():
                logger.info(f"精简版已存在，将重新生成: {output_path}")
                output_path.unlink()

            event("评估书籍适合度")
            suitability_result = self._check_suitability(book_info)
            self.db.add_log(
                book_id,
                "suitability",
                suitability_result.label,
                f"适合度: {suitability_result.score}分 - {suitability_result.recommendation}",
            )

            if not suitability_result.passed:
                logger.info(f"书籍不适合生成精简版: {suitability_result.recommendation}")
                self.db.update_book_status(book_id, "skipped", suitability_result.recommendation)
                self.db.add_log(book_id, "summarizing", "skipped", f"不适合生成精简版: {suitability_result.label}")
                return False

            logger.info(f"书籍适合度评估通过: {suitability_result.label}({suitability_result.score}分)")

            event("提取章节内容")
            chapters = extract_chapters(book_id, epub_path)

            event("调用 AI 生成摘要")
            summary_content = self.ai_generator.generate(book_id, book_info, chapters, suitability_result)

            if summary_content is None:
                logger.warning("精简版生成失败，跳过PDF创建")
                self.db.add_log(book_id, "summarizing", "skipped", "AI生成失败，跳过精简版")
                return False

            # 提取封面 - 只保存到 metadata 目录
            event("提取封面图片")
            cover_path = self._extract_and_save_cover(epub_path, output_dir)

            summary_text = self._format_summary_to_text(summary_content)
            self.db.update_book_summary(book_id, summary_text)

            event("生成精简版 PDF")
            self.pdf_generator.create(summary_content, str(output_path), cover_path)

            self.db.update_book_output(book_id, summary_pdf=str(output_path))

            self.db.add_log(book_id, "summarizing", "success", f"精简版生成完成: {output_path}")

            logger.info(f"精简版生成成功: {output_path}")
            return True

        except Exception as e:
            logger.error(f"生成精简版失败: {book_id}, 错误: {e}")
            self.db.update_book_status(book_id, "failed", str(e))
            self.db.add_log(book_id, "summarizing", "error", str(e))
            return False

    def _check_suitability(self, book_info: Dict[str, Any]):
        """检查书籍是否适合生成精简版"""
        return self.evaluator.evaluate(book_info)

    def _extract_and_save_cover(self, epub_path: str, output_dir: Path) -> Optional[str]:
        """提取封面并保存到 metadata 目录"""
        extracted_cover_path = extract_cover_from_epub(epub_path)
        if not extracted_cover_path:
            logger.warning("未能提取到封面")
            return None

        try:
            meta_dir = output_dir.parent / f"{output_dir.name}_metadata"
            os.makedirs(meta_dir, exist_ok=True)
            ext = os.path.splitext(extracted_cover_path)[1]
            meta_cover_path = meta_dir / f"cover{ext}"
            shutil.copy2(extracted_cover_path, meta_cover_path)
            logger.info(f"封面已复制到 metadata 目录: {meta_cover_path}")

            try:
                os.unlink(extracted_cover_path)
            except Exception:
                pass

            return str(meta_cover_path)
        except Exception as e:
            logger.warning(f"封面保存失败: {e}")
            return None

    @staticmethod
    def _format_summary_to_text(summary_content: Dict[str, Any]) -> str:
        """将摘要字典格式化为结构化文本"""
        title = summary_content.get("title", "")
        author = summary_content.get("author", "")
        book_type = summary_content.get("book_type", "")
        content = summary_content.get("content", "")
        parts = [f"书名：{title}", f"作者：{author}", f"类型：{book_type}", "", content]
        return "\n".join(parts)


def generate_summary(book_id: str, epub_path: str) -> bool:
    """生成书籍精简版"""
    summarizer = ContentSummarizer()
    return summarizer.summarize(book_id, epub_path)


if __name__ == "__main__":
    print("内容精简器测试")
