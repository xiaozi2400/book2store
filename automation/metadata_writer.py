import logging
from pathlib import Path

from automation.config import config
from automation.utils import ensure_dir

logger = logging.getLogger(__name__)


class MetadataWriter:
    """文案元数据写入器"""

    def __init__(self):
        self.output_dir = Path(config.output_dir).resolve()

    def write_copywriting(self, book_id: str, xianyu_text: str, xiaohongshu_text: str) -> bool:
        """写入文案到 meta_dir 下的 txt 文件"""
        from automation.database import DatabaseManager
        db = DatabaseManager()
        book = db.get_book_by_id(book_id)
        if not book:
            logger.warning(f"书籍不存在: {book_id}")
            return False

        base_name = Path(book.filename).stem.strip()
        meta_dir = ensure_dir(self.output_dir / f"{base_name}_metadata")

        xianyu_path = meta_dir / "xianyu_listing.txt"
        with open(xianyu_path, "w", encoding="utf-8") as f:
            f.write(xianyu_text)
        logger.info(f"闲鱼文案已写入: {xianyu_path}")

        if xiaohongshu_text:
            xhs_path = meta_dir / "xiaohongshu_note.txt"
            with open(xhs_path, "w", encoding="utf-8") as f:
                f.write(xiaohongshu_text)
            logger.info(f"小红书笔记已写入: {xhs_path}")

        return True