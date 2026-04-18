"""
翻译处理器 - 复用ebook_translator的翻译和PDF转换功能
"""
import os
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ebook_translator.translator.deepseek_api import DeepSeekTranslator
from ebook_translator.translator.epub_parser import EpubParser
from ebook_translator.translator.epub_generator import EpubGenerator
from ebook_translator.translator.pdf_converter import PDFConverter
from .database import DatabaseManager
from .config import config
from .utils import logger, ensure_dir


class TranslationProcessor:
    """翻译处理器 - 复用现有ebook_translator"""

    def __init__(self):
        self.db = DatabaseManager()
        self.output_dir = Path(config.output_dir)
        self.translator = DeepSeekTranslator()
        self.parser = EpubParser()
        self.generator = EpubGenerator()
        self.converter = PDFConverter()

    def process(self, book_id: str, epub_path: str) -> bool:
        """处理书籍：翻译并生成PDF"""
        logger.info(f"开始翻译处理: {book_id}")

        try:
            self.db.update_book_status(book_id, "translating")
            self.db.add_log(book_id, "translating", "start", "开始翻译")

            book_obj = self.db.get_all_books()[0]
            base_name = Path(epub_path).stem

            book_output_dir = ensure_dir(self.output_dir / book_id)

            english_pdf = book_output_dir / f"英文原版-{base_name}.pdf"
            bilingual_epub = book_output_dir / f"中英双语-{base_name}.epub"
            chinese_epub = book_output_dir / f"中文版-{base_name}.epub"
            bilingual_pdf = book_output_dir / f"中英双语-{base_name}.pdf"
            chinese_pdf = book_output_dir / f"中文版-{base_name}.pdf"

            logger.info("步骤1: 解析EPUB...")
            parsed_data = self.parser.parse(epub_path)
            all_paragraphs = parsed_data.get('paragraphs', [])

            logger.info(f"步骤2: 翻译 {len(all_paragraphs)} 个段落...")
            translated_paragraphs = self._translate_paragraphs(all_paragraphs)

            logger.info("步骤3: 生成中英双语EPUB...")
            if self.generator.generate_bilingual_epub(translated_paragraphs, str(bilingual_epub)):
                logger.info(f"双语EPUB生成成功: {bilingual_epub}")
            else:
                logger.warning("双语EPUB生成失败")

            logger.info("步骤4: 生成纯中文EPUB...")
            if self.generator.generate_chinese_epub(translated_paragraphs, str(chinese_epub)):
                logger.info(f"中文EPUB生成成功: {chinese_epub}")
            else:
                logger.warning("中文EPUB生成失败")

            logger.info("步骤5: 转换为PDF...")
            if bilingual_epub.exists():
                self.converter.convert_to_pdf(str(bilingual_epub), str(bilingual_pdf), is_bilingual=True)
                logger.info(f"双语PDF生成成功: {bilingual_pdf}")

            if chinese_epub.exists():
                self.converter.convert_to_pdf(str(chinese_epub), str(chinese_pdf), is_bilingual=False)
                logger.info(f"中文PDF生成成功: {chinese_pdf}")

            self.db.update_book_output(
                book_id,
                english_pdf=str(english_pdf),
                bilingual_epub=str(bilingual_epub),
                chinese_epub=str(chinese_epub),
                bilingual_pdf=str(bilingual_pdf),
                chinese_pdf=str(chinese_pdf)
            )

            self.db.add_log(book_id, "translating", "success", "翻译完成")
            logger.info(f"翻译处理完成: {book_id}")
            return True

        except Exception as e:
            logger.error(f"翻译处理失败: {book_id}, 错误: {e}")
            self.db.update_book_status(book_id, "failed", str(e))
            self.db.add_log(book_id, "translating", "error", str(e))
            return False

    def _translate_paragraphs(self, paragraphs: list) -> list:
        """翻译段落"""
        translated = []

        for i, para in enumerate(paragraphs):
            if i % 50 == 0:
                logger.info(f"翻译进度: {i}/{len(paragraphs)}")

            text = para.get('text', '')
            if not text or len(text.strip()) < 5:
                translated.append(para)
                continue

            try:
                translated_text = self.translator.translate(text)
                para['translated'] = translated_text
            except Exception as e:
                logger.warning(f"翻译段落 {i} 失败: {e}")
                para['translated'] = text

            translated.append(para)

        return translated


def translate_book(book_id: str, epub_path: str) -> bool:
    """翻译书籍"""
    processor = TranslationProcessor()
    return processor.process(book_id, epub_path)


if __name__ == "__main__":
    print("翻译处理器测试")
