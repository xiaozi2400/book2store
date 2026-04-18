"""
目录扫描器 - 扫描输入目录检测新书籍
"""
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
import ebooklib
from ebooklib import epub

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .database import DatabaseManager
from .config import config
from .utils import logger, is_valid_epub, extract_title_from_filename


class DirectoryScanner:
    """目录扫描器"""

    def __init__(self):
        self.db = DatabaseManager()
        self.input_dir = Path(config.input_dir)

    def scan(self) -> List[Dict]:
        """扫描输入目录，返回待处理书籍列表"""
        logger.info(f"开始扫描目录: {self.input_dir}")

        if not self.input_dir.exists():
            logger.warning(f"输入目录不存在: {self.input_dir}")
            return []

        books = []
        for epub_file in self.input_dir.glob("*.epub"):
            if not self._should_process(epub_file):
                continue

            book_info = self._process_epub(epub_file)
            if book_info:
                books.append(book_info)

        logger.info(f"扫描完成，发现 {len(books)} 本新书籍")
        return books

    def _should_process(self, epub_path: Path) -> bool:
        """检查是否应该处理该文件"""
        if not is_valid_epub(str(epub_path)):
            logger.warning(f"无效的EPUB文件: {epub_path}")
            return False

        existing_book = self.db.get_book_by_filename(epub_path.name)
        if existing_book:
            logger.info(f"书籍已存在，跳过: {epub_path.name}")
            return False

        return True

    def _process_epub(self, epub_path: Path) -> Optional[Dict]:
        """处理单个EPUB文件"""
        try:
            book = epub.read_epub(str(epub_path))

            metadata = self._extract_metadata(book)

            db_book = self.db.create_book(
                filename=epub_path.name,
                title=metadata.get('title', extract_title_from_filename(epub_path.name)),
                author=metadata.get('author')
            )

            self.db.update_book_status(db_book.id, "scanning")
            self.db.add_log(db_book.id, "scanning", "success", "书籍扫描完成")

            self.db.create_book_output(db_book.id)

            logger.info(f"书籍创建成功: {db_book.title}")

            return {
                'id': db_book.id,
                'filename': db_book.filename,
                'title': db_book.title,
                'author': db_book.author,
                'path': str(epub_path),
                'language': metadata.get('language'),
                'page_count': metadata.get('page_count')
            }

        except Exception as e:
            logger.error(f"处理EPUB失败: {epub_path}, 错误: {e}")
            return None

    def _extract_metadata(self, book) -> Dict:
        """提取EPUB元数据"""
        metadata = {
            'title': None,
            'author': None,
            'language': 'en',
            'page_count': None
        }

        if book.get_metadata('DC', 'title'):
            metadata['title'] = book.get_metadata('DC', 'title')[0][0]

        if book.get_metadata('DC', 'creator'):
            metadata['author'] = book.get_metadata('DC', 'creator')[0][0]

        if book.get_metadata('DC', 'language'):
            lang = book.get_metadata('DC', 'language')[0][0]
            metadata['language'] = lang.lower()

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
