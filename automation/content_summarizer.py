"""
内容精简器 - 生成书籍核心内容精简版PDF
"""
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .ai_client import AIClient
from .database import DatabaseManager
from .config import config
from .utils import logger, ensure_dir


class ContentSummarizer:
    """内容精简器"""

    def __init__(self):
        self.ai = AIClient()
        self.db = DatabaseManager()
        self.output_dir = Path(config.output_dir)

    def summarize(self, book_id: str, epub_path: str) -> bool:
        """生成书籍精简版"""
        logger.info(f"开始生成精简版: {book_id}")

        try:
            self.db.update_book_status(book_id, "summarizing")
            self.db.add_log(book_id, "summarizing", "start", "开始生成精简版")

            book = self.db.get_book_by_filename("")
            book = self.db.get_all_books()[0] if not book else None
            if book:
                book.title = book.title or "Unknown"

            book_info = {
                'title': '书籍',
                'author': 'Unknown',
                'summary': ''
            }

            chapters = self._extract_chapters(epub_path)

            summary_content = self._generate_summary(book_info, chapters)

            output_path = ensure_dir(self.output_dir / book_id) / "核心精简.pdf"

            self._create_pdf(summary_content, str(output_path))

            self.db.update_book_output(book_id, summary_pdf=str(output_path))

            self.db.add_log(book_id, "summarizing", "success", f"精简版生成完成: {output_path}")

            logger.info(f"精简版生成成功: {output_path}")
            return True

        except Exception as e:
            logger.error(f"生成精简版失败: {book_id}, 错误: {e}")
            self.db.update_book_status(book_id, "failed", str(e))
            self.db.add_log(book_id, "summarizing", "error", str(e))
            return False

    def _extract_chapters(self, epub_path: str) -> list:
        """提取章节内容"""
        import ebooklib
        from ebooklib import epub

        chapters = []
        try:
            book = epub.read_epub(epub_path)

            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(item.get_content(), 'html.parser')

                    text = soup.get_text()
                    if len(text) > 500:
                        title = self._extract_title(soup)
                        chapters.append({
                            'title': title or f"第{len(chapters)+1}章",
                            'content': text[:5000]
                        })

        except Exception as e:
            logger.warning(f"提取章节失败: {e}")

        return chapters[:10]

    def _extract_title(self, soup) -> Optional[str]:
        """提取标题"""
        for tag in soup.find_all(['h1', 'h2', 'h3', 'title']):
            text = tag.get_text().strip()
            if text and len(text) < 100:
                return text
        return None

    def _generate_summary(self, book_info: Dict, chapters: list) -> Dict[str, Any]:
        """使用AI生成摘要"""
        combined_content = "\n\n".join([
            f"{ch['title']}:\n{ch['content'][:2000]}"
            for ch in chapters[:5]
        ])

        try:
            result = self.ai.generate_summary(book_info, combined_content)

            if 'error' in result:
                logger.warning(f"AI生成失败，使用默认模板: {result.get('error')}")
                return self._get_default_summary(book_info, chapters)

            return {
                'title': book_info.get('title', 'Unknown'),
                'author': book_info.get('author', 'Unknown'),
                'core_insight': result.get('core_insight', ''),
                'chapter_summaries': result.get('chapter_summaries', []),
                'quotes': result.get('quotes', []),
                'target_audience': result.get('target_audience', '')
            }

        except Exception as e:
            logger.error(f"AI生成失败: {e}")
            return self._get_default_summary(book_info, chapters)

    def _get_default_summary(self, book_info: Dict, chapters: list) -> Dict[str, Any]:
        """获取默认摘要"""
        return {
            'title': book_info.get('title', 'Unknown'),
            'author': book_info.get('author', 'Unknown'),
            'core_insight': f"《{book_info.get('title')}》是一本有价值的书籍。",
            'chapter_summaries': [
                {'chapter': ch['title'], 'summary': ch['content'][:200]}
                for ch in chapters[:5]
            ],
            'quotes': ['本书包含丰富的知识和见解。'],
            'target_awesome': '适合对相关主题感兴趣的读者。'
        }

    def _create_pdf(self, content: Dict[str, Any], output_path: str):
        """生成PDF"""
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )

        styles = getSampleStyleSheet()
        story = []

        title = content.get('title', 'Unknown')
        author = content.get('author', 'Unknown')

        story.append(Paragraph(f"<b>{title}</b>", styles['Title']))
        story.append(Paragraph(f"作者: {author}", styles['Normal']))
        story.append(Spacer(1, 0.3 * inch))

        story.append(Paragraph("<b>核心观点</b>", styles['Heading1']))
        core_insight = content.get('core_insight', '')
        story.append(Paragraph(core_insight, styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))

        chapter_summaries = content.get('chapter_summaries', [])
        if chapter_summaries:
            story.append(Paragraph("<b>章节摘要</b>", styles['Heading1']))
            for ch in chapter_summaries:
                ch_title = ch.get('chapter', '')
                ch_summary = ch.get('summary', '')
                if ch_title or ch_summary:
                    story.append(Paragraph(f"<b>{ch_title}</b>", styles['Heading2']))
                    story.append(Paragraph(ch_summary, styles['Normal']))
                    story.append(Spacer(1, 0.1 * inch))

        quotes = content.get('quotes', [])
        if quotes:
            story.append(Paragraph("<b>金句摘录</b>", styles['Heading1']))
            for quote in quotes[:10]:
                story.append(Paragraph(f"• {quote}", styles['Normal']))

        target = content.get('target_audience', '')
        if target:
            story.append(Spacer(1, 0.3 * inch))
            story.append(Paragraph("<b>适用人群</b>", styles['Heading1']))
            story.append(Paragraph(target, styles['Normal']))

        doc.build(story)


def generate_summary(book_id: str, epub_path: str) -> bool:
    """生成书籍精简版"""
    summarizer = ContentSummarizer()
    return summarizer.summarize(book_id, epub_path)


if __name__ == "__main__":
    print("内容精简器测试")
