"""
翻译处理器 - 直接复用ebook_translator主程序
"""
import os
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .database import DatabaseManager
from .config import config
from .utils import logger, ensure_dir


class TranslationProcessor:
    """翻译处理器 - 直接调用ebook_translator"""

    def __init__(self):
        self.db = DatabaseManager()
        self.output_dir = Path(config.output_dir)

    def process(self, book_id: str, epub_path: str) -> bool:
        """处理书籍：调用ebook_translator进行翻译和PDF转换"""
        logger.info(f"开始翻译处理: {book_id}")

        try:
            self.db.update_book_status(book_id, "translating")
            self.db.add_log(book_id, "translating", "start", "开始翻译")

            base_name = Path(epub_path).stem
            book_output_dir = ensure_dir(self.output_dir / base_name)

            cmd = [
                sys.executable,
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "ebook_translator", "main.py"),
                epub_path,
                "--output-dir", str(book_output_dir)
            ]

            logger.info(f"执行命令: {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding='utf-8',
                errors='replace',
                bufsize=1
            )

            for line in iter(process.stdout.readline, ''):
                if line:
                    print(line.rstrip())
                if process.poll() is not None:
                    break

            process.wait()

            if process.returncode != 0:
                logger.error(f"翻译失败，返回码: {process.returncode}")
                self.db.update_book_status(book_id, "failed", f"返回码: {process.returncode}")
                self.db.add_log(book_id, "translating", "error", f"返回码: {process.returncode}")
                return False

            base_name = Path(epub_path).stem
            bilingual_epub = book_output_dir / "EPUB" / f"中英双语-{base_name}.epub"
            chinese_epub = book_output_dir / "EPUB" / f"中文版本-{base_name}.epub"
            english_epub = book_output_dir / "EPUB" / f"英文原版-{base_name}.epub"
            bilingual_pdf = book_output_dir / "PDF" / f"中英双语-{base_name}.pdf"
            chinese_pdf = book_output_dir / "PDF" / f"中文版本-{base_name}.pdf"
            english_pdf = book_output_dir / "PDF" / f"英文原版-{base_name}.pdf"

            self.db.update_book_output(
                book_id,
                english_pdf=str(english_pdf) if english_pdf.exists() else None,
                bilingual_epub=str(bilingual_epub) if bilingual_epub.exists() else None,
                chinese_epub=str(chinese_epub) if chinese_epub.exists() else None,
                bilingual_pdf=str(bilingual_pdf) if bilingual_pdf.exists() else None,
                chinese_pdf=str(chinese_pdf) if chinese_pdf.exists() else None
            )

            self.db.add_log(book_id, "translating", "success", "翻译完成")
            logger.info(f"翻译处理完成: {book_id}")
            return True

        except Exception as e:
            logger.error(f"翻译处理失败: {book_id}, 错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.db.update_book_status(book_id, "failed", str(e))
            self.db.add_log(book_id, "translating", "error", str(e))
            return False


def translate_book(book_id: str, epub_path: str) -> bool:
    """翻译书籍"""
    processor = TranslationProcessor()
    return processor.process(book_id, epub_path)


if __name__ == "__main__":
    print("翻译处理器测试")
