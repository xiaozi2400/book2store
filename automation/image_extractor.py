"""
图片提取器 - 提取EPUB封面和PDF目录预览图
"""
import os
import sys
import io
import zipfile
from pathlib import Path
from typing import Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

from .database import DatabaseManager
from .config import config
from .utils import logger, ensure_dir


class ImageExtractor:
    """图片提取器"""

    def __init__(self):
        self.db = DatabaseManager()
        self.output_dir = Path(config.output_dir)
        self.image_config = config.image_config

    def extract(self, book_id: str, epub_path: str, pdf_path: str = None) -> bool:
        """提取封面和目录预览图"""
        logger.info(f"开始提取图片: {book_id}")

        try:
            self.db.update_book_status(book_id, "extracting")
            self.db.add_log(book_id, "extracting", "start", "开始提取图片")

            book_output_dir = ensure_dir(self.output_dir / book_id)

            cover_path = self._extract_cover(epub_path, book_output_dir)

            toc_preview_path = None
            if pdf_path and os.path.exists(pdf_path):
                toc_preview_path = self._extract_toc_preview(pdf_path, book_output_dir)

            self.db.update_book_output(
                book_id,
                cover_image=cover_path,
                toc_preview_image=toc_preview_path
            )

            self.db.add_log(book_id, "extracting", "success", "图片提取完成")
            logger.info(f"图片提取完成: {book_id}")
            return True

        except Exception as e:
            logger.error(f"提取图片失败: {book_id}, 错误: {e}")
            self.db.add_log(book_id, "extracting", "error", str(e))
            return False

    def _extract_cover(self, epub_path: str, output_dir: Path) -> Optional[str]:
        """提取封面图片"""
        try:
            with zipfile.ZipFile(epub_path, 'r') as zf:
                namelist = zf.namelist()

                cover_file = None
                for name in namelist:
                    if 'cover' in name.lower() and name.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                        cover_file = name
                        break

                if not cover_file:
                    for name in namelist:
                        if name.endswith(('.jpg', '.jpeg', '.png')) and 'image' in name:
                            if not any(x in name.lower() for x in ['thumb', 'icon', 'logo']):
                                cover_file = name
                                break

                if not cover_file:
                    logger.warning(f"未找到封面图片: {epub_path}")
                    return None

                cover_data = zf.read(cover_file)
                img = Image.open(io.BytesIO(cover_data))

                if img.mode == 'RGBA':
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                output_path = output_dir / "cover.jpg"
                img.thumbnail(
                    (self.image_config['max_width'], self.image_config['max_height']),
                    Image.Resampling.LANCZOS
                )
                img.save(output_path, 'JPEG', quality=self.image_config['quality'])

                logger.info(f"封面提取成功: {output_path}")
                return str(output_path)

        except Exception as e:
            logger.error(f"提取封面失败: {epub_path}, 错误: {e}")
            return None

    def _extract_toc_preview(self, pdf_path: str, output_dir: Path) -> Optional[str]:
        """从PDF中提取目录预览图"""
        try:
            import fitz

            doc = fitz.open(pdf_path)

            toc = doc.get_toc()
            toc_page_num = None

            for i, (level, title, page) in enumerate(toc):
                if "目录" in title.lower() or "contents" in title.lower():
                    toc_page_num = page - 1
                    break

            if toc_page_num is None:
                for page_num in range(min(5, len(doc))):
                    page = doc[page_num]
                    text = page.get_text()
                    if "目录" in text or "contents" in text.lower():
                        toc_page_num = page_num
                        break

            if toc_page_num is None:
                toc_page_num = 0

            page = doc[toc_page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))

            output_path = output_dir / "toc_preview.jpg"
            pix.save(str(output_path))

            doc.close()

            logger.info(f"目录预览提取成功: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"提取目录预览失败: {pdf_path}, 错误: {e}")
            return None


def extract_images(book_id: str, epub_path: str, pdf_path: str = None) -> bool:
    """提取图片"""
    extractor = ImageExtractor()
    return extractor.extract(book_id, epub_path, pdf_path)


if __name__ == "__main__":
    print("图片提取器测试")
