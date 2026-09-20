"""
目录扫描器 - 扫描输入目录检测新书籍
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from ebooklib import epub

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .config import config
from .database import DatabaseManager
from .utils import extract_title_from_filename, is_valid_epub, logger


class DirectoryScanner:
    """目录扫描器"""

    def __init__(self):
        self.db = DatabaseManager()
        self.input_dir = Path(config.input_dir)
        self.logger = logger

    def scan(self) -> List[Dict]:
        """扫描输入目录，返回待处理书籍列表"""
        logger.info(f"开始扫描目录: {self.input_dir}")

        if not self.input_dir.exists():
            logger.warning(f"输入目录不存在: {self.input_dir}")
            return []

        # 先统一修复物理文件名（去除 stem 部分的尾随空格），确保路径一致
        self._fix_filenames()

        books = []
        for epub_file in self.input_dir.glob("*.epub"):
            if not self._should_process(epub_file):
                continue

            book_info = self._process_epub(epub_file)
            if book_info:
                books.append(book_info)

        logger.info(f"扫描完成，发现 {len(books)} 本新书籍")
        return books

    @staticmethod
    def _clean_filename(name: str) -> str:
        """清理文件名：去除 stem 部分的头尾空格"""
        stem, ext = os.path.splitext(name)
        return stem.strip() + ext

    def _fix_filenames(self):
        """修复输入目录中文件名的问题：尾随空格 + 长度截断 + --拆分"""
        for epub_file in list(self.input_dir.glob("*.epub")):
            stem = epub_file.stem
            ext = epub_file.suffix
            new_stem = stem.strip()

            # 1. 如果有 "--"，只保留前面部分
            if "--" in new_stem:
                new_stem = new_stem.split("--")[0].strip()

            # 2. 超过60字符截断末尾
            if len(new_stem) > 60:
                new_stem = new_stem[:60].strip()

            new_name = new_stem + ext
            if new_name != epub_file.name:
                new_path = epub_file.with_name(new_name)
                # 避免同名文件冲突（例如 Book--A.epub 和 Book.epub）
                if new_path.exists():
                    self.logger.warning(f"目标文件名已存在，跳过重命名: '{new_name}'")
                    continue
                epub_file.rename(new_path)
                self.logger.info(f"重命名文件: '{epub_file.name}' -> '{new_name}'")

    def _should_process(self, epub_path: Path) -> bool:
        """检查是否应该处理该文件"""
        if not is_valid_epub(str(epub_path)):
            logger.warning(f"无效的EPUB文件: {epub_path}")
            return False

        clean_name = self._clean_filename(epub_path.name)
        existing_book = self.db.get_book_by_filename(clean_name)
        if existing_book:
            output_dir = Path(config.output_dir)
            base_name = Path(clean_name).stem.strip()
            short_name = base_name.split("_")[0].strip()

            output_patterns = [
                output_dir / base_name / f"双语-{short_name}.epub",
                output_dir / base_name / f"双语-{short_name}.pdf",
                output_dir / base_name / f"中文-{short_name}.epub",
                output_dir / base_name / f"中文-{short_name}.pdf",
                output_dir / base_name / f"英文-{short_name}.epub",
                output_dir / base_name / f"英文-{short_name}.pdf",
            ]

            has_output = any(p.exists() for p in output_patterns)

            if has_output:
                logger.info(f"书籍已存在且处理完成，跳过: {epub_path.name}")
                return False
            else:
                logger.info(f"书籍记录存在但处理失败，将重新处理: {epub_path.name}")
                return True

        return True

    def _process_epub(self, epub_path: Path) -> Optional[Dict]:
        """处理单个EPUB文件"""
        try:
            book = epub.read_epub(str(epub_path))

            metadata = self._extract_metadata(book)

            clean_name = self._clean_filename(epub_path.name)
            existing_book = self.db.get_book_by_filename(clean_name)
            if existing_book:
                db_book = existing_book
                logger.info(f"复用已有书籍记录: {db_book.title}")
            else:
                db_book = self.db.create_book(
                    filename=clean_name,
                    title=metadata.get("title", extract_title_from_filename(clean_name)),
                    author=metadata.get("author"),
                )
                self.db.create_book_output(db_book.id)
                logger.info(f"书籍创建成功: {db_book.title}")

            self.db.update_book_status(db_book.id, "scanning")
            self.db.add_log(db_book.id, "scanning", "success", "书籍扫描完成")

            return {
                "id": db_book.id,
                "filename": db_book.filename,
                "title": db_book.title,
                "author": db_book.author,
                "path": str(epub_path),
                "language": metadata.get("language"),
                "page_count": metadata.get("page_count"),
            }

        except Exception as e:
            logger.error(f"处理EPUB失败: {epub_path}, 错误: {e}")
            return None

    def _extract_metadata(self, book) -> Dict:
        """提取EPUB元数据"""
        metadata = {"title": None, "author": None, "language": "en", "page_count": None}

        if book.get_metadata("DC", "title"):
            metadata["title"] = book.get_metadata("DC", "title")[0][0]

        if book.get_metadata("DC", "creator"):
            metadata["author"] = book.get_metadata("DC", "creator")[0][0]

        if book.get_metadata("DC", "language"):
            lang = book.get_metadata("DC", "language")[0][0]
            metadata["language"] = lang.lower()

        return metadata


def scan_input_directory():
    """扫描输入目录"""
    scanner = DirectoryScanner()
    return scanner.scan()


if __name__ == "__main__":
    books = scan_input_directory()
    print(f"发现 {len(books)} 本新书籍")
    for book in books:
        print(f"  - {book['title']} by {book.get('author', 'Unknown')}")
