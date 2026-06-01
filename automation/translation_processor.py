
"""
翻译处理器 - 直接调用 ebook_translator 库函数，支持并行处理
"""
import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .database import DatabaseManager
from .config import config
from .utils import logger, ensure_dir
from .translation_cache import SQLiteTranslationCache

# 导入 library 模块
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ebook_translator'))
from ebook_translator.library import translate_epub, convert_english_pdf_only


class TranslationProcessor:
    """翻译处理器 - 直接调用 library 接口，支持并行"""

    def __init__(self):
        self.db = DatabaseManager()
        self.output_dir = Path(config.output_dir)

    def process(self, book_id, epub_path, skip_cache=False):
        """处理书籍：翻译 + 并行 PDF 转换"""
        logger.info(f"开始翻译处理: {book_id}")

        try:
            self.db.update_book_status(book_id, "translating")
            self.db.add_log(book_id, "translating", "start", "开始翻译")

            # 准备输出目录
            base_name = Path(epub_path).stem
            short_name = base_name.split('_')[0].strip()
            output_root = self.output_dir / base_name

            # 并行执行：翻译 + 英文 PDF 转换
            with ThreadPoolExecutor(max_workers=2) as executor:
                # 任务 1：翻译（后台线程）
                future_translate = executor.submit(
                    self._do_translate,
                    book_id,
                    epub_path,
                    str(output_root),
                    skip_cache
                )

                # 任务 2：英文 PDF 转换（立即开始）
                future_english_pdf = executor.submit(
                    convert_english_pdf_only,
                    epub_path,
                    str(output_root)
                )

                # 等待翻译完成
                translation_result = future_translate.result()

                # 获取英文 PDF 结果
                try:
                    english_pdf_path = future_english_pdf.result()
                except Exception as e:
                    logger.warning(f"英文 PDF 并行转换失败: {e}")
                    english_pdf_path = None

            if not translation_result.get("success", False):
                logger.error(f"翻译失败")
                self.db.update_book_status(book_id, "failed", "翻译失败")
                self.db.add_log(book_id, "translating", "error", "翻译失败")
                return False

            # 更新数据库
            self._update_database(book_id, translation_result, english_pdf_path)

            # 记录 Token 使用
            self._record_token_stats(book_id, translation_result)

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

    def _do_translate(self, book_id, epub_path, output_dir, skip_cache):
        """执行翻译任务（在线程中运行）"""
        # 使用 SQLite 缓存
        sqlite_cache = SQLiteTranslationCache()
        
        # 首次使用时，尝试从旧 JSON 缓存迁移数据
        if not skip_cache:
            # 查找旧 JSON 缓存文件的位置
            old_cache_path = None
            possible_paths = [
                "translation_cache.json",
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ebook_translator", "translation_cache.json")
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    old_cache_path = path
                    break
            
            if old_cache_path:
                logger.info(f"发现旧 JSON 缓存: {old_cache_path}，尝试迁移数据")
                sqlite_cache.migrate_from_json(old_cache_path)
        
        return translate_epub(
            epub_path=epub_path,
            output_dir=output_dir,
            book_id=book_id,
            skip_cache=skip_cache,
            cache=sqlite_cache
        )

    def _update_database(self, book_id, translation_result, english_pdf_path=None):
        """更新数据库中的输出文件信息"""
        # 从翻译结果获取路径
        bilingual_epub = translation_result.get("bilingual_epub")
        chinese_epub = translation_result.get("chinese_epub")
        english_epub = translation_result.get("english_epub")
        bilingual_pdf = translation_result.get("bilingual_pdf")
        chinese_pdf = translation_result.get("chinese_pdf")

        # 使用并行转换的英文 PDF（如果有）
        final_english_pdf = english_pdf_path or translation_result.get("english_pdf")

        self.db.update_book_output(
            book_id,
            english_pdf=final_english_pdf,
            bilingual_epub=bilingual_epub,
            chinese_epub=chinese_epub,
            bilingual_pdf=bilingual_pdf,
            chinese_pdf=chinese_pdf
        )

    def _record_token_stats(self, book_id, translation_result):
        """记录 Token 使用统计"""
        stats = translation_result.get("stats", {})
        if stats:
            self.db.record_token_usage(
                book_id=book_id,
                step="translation",
                input_tokens=stats.get("prompt_tokens", 0),
                output_tokens=stats.get("completion_tokens", 0)
            )
            logger.info(
                f"翻译Token消耗: 输入={stats.get('prompt_tokens', 0)}, "
                f"输出={stats.get('completion_tokens', 0)}"
            )


def translate_book(book_id, epub_path, skip_cache=False):
    """翻译书籍"""
    processor = TranslationProcessor()
    return processor.process(book_id, epub_path, skip_cache)


if __name__ == "__main__":
    print("翻译处理器测试")

