"""
翻译处理器 - 直接复用ebook_translator主程序
"""
import os
import sys
import json
import tempfile
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

    def process(self, book_id: str, epub_path: str, skip_cache: bool = False) -> bool:
        """处理书籍：调用ebook_translator进行翻译和PDF转换"""
        logger.info(f"开始翻译处理: {book_id}")

        try:
            self.db.update_book_status(book_id, "translating")
            self.db.add_log(book_id, "translating", "start", "开始翻译")

            base_name = Path(epub_path).stem
            short_name = base_name.split('_')[0].strip()

            bilingual_dir = ensure_dir(self.output_dir / base_name / f"双语-{short_name}")
            chinese_dir = ensure_dir(self.output_dir / base_name / f"中文-{short_name}")
            english_dir = ensure_dir(self.output_dir / base_name / f"英文-{short_name}")

            bilingual_epub = bilingual_dir / f"双语-{short_name}.epub"
            chinese_epub = chinese_dir / f"中文-{short_name}.epub"
            english_epub = english_dir / f"英文-{short_name}.epub"
            bilingual_pdf = bilingual_dir / f"双语-{short_name}.pdf"
            chinese_pdf = chinese_dir / f"中文-{short_name}.pdf"
            english_pdf = english_dir / f"英文-{short_name}.pdf"

            cmd = [
                sys.executable,
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "ebook_translator", "main.py"),
                epub_path,
                "--output-dir", str(self.output_dir / base_name),
                "--book-id", book_id
            ]
            if skip_cache:
                cmd.append("--skip-cache")

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
                    print(line.rstrip(), flush=True)
                if process.poll() is not None:
                    break

            process.wait()

            if process.returncode != 0:
                logger.error(f"翻译失败，返回码: {process.returncode}")
                self.db.update_book_status(book_id, "failed", f"返回码: {process.returncode}")
                self.db.add_log(book_id, "translating", "error", f"返回码: {process.returncode}")
                return False

            base_name = Path(epub_path).stem
            short_name = base_name.split('_')[0].strip()
            bilingual_dir = ensure_dir(self.output_dir / base_name / f"双语-{short_name}")
            chinese_dir = ensure_dir(self.output_dir / base_name / f"中文-{short_name}")
            english_dir = ensure_dir(self.output_dir / base_name / f"英文-{short_name}")

            bilingual_epub = bilingual_dir / f"双语-{short_name}.epub"
            chinese_epub = chinese_dir / f"中文-{short_name}.epub"
            english_epub = english_dir / f"英文-{short_name}.epub"
            bilingual_pdf = bilingual_dir / f"双语-{short_name}.pdf"
            chinese_pdf = chinese_dir / f"中文-{short_name}.pdf"
            english_pdf = english_dir / f"英文-{short_name}.pdf"

            self.db.update_book_output(
                book_id,
                english_pdf=str(english_pdf) if english_pdf.exists() else None,
                bilingual_epub=str(bilingual_epub) if bilingual_epub.exists() else None,
                chinese_epub=str(chinese_epub) if chinese_epub.exists() else None,
                bilingual_pdf=str(bilingual_pdf) if bilingual_pdf.exists() else None,
                chinese_pdf=str(chinese_pdf) if chinese_pdf.exists() else None
            )

            self.db.add_log(book_id, "translating", "success", "翻译完成")

            stats_file = os.path.join(tempfile.gettempdir(), f"translation_stats_{book_id}.json")
            if os.path.exists(stats_file):
                try:
                    with open(stats_file, "r", encoding="utf-8") as f:
                        stats = json.load(f)
                    os.remove(stats_file)
                    self.db.record_token_usage(
                        book_id=book_id,
                        step="translation",
                        input_tokens=stats.get("prompt_tokens", 0),
                        output_tokens=stats.get("completion_tokens", 0)
                    )
                    logger.info(f"翻译Token消耗: 输入={stats.get('prompt_tokens', 0)}, "
                                f"输出={stats.get('completion_tokens', 0)}")
                except Exception as e:
                    logger.warning(f"读取翻译Token统计失败: {e}")

            logger.info(f"翻译处理完成: {book_id}")
            return True

        except Exception as e:
            logger.error(f"翻译处理失败: {book_id}, 错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.db.update_book_status(book_id, "failed", str(e))
            self.db.add_log(book_id, "translating", "error", str(e))
            return False


def translate_book(book_id: str, epub_path: str, skip_cache: bool = False) -> bool:
    """翻译书籍"""
    processor = TranslationProcessor()
    return processor.process(book_id, epub_path, skip_cache)


if __name__ == "__main__":
    print("翻译处理器测试")
