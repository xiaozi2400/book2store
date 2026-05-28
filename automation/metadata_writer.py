"""
上架元数据写入器 - 将文案和图片输出到独立的 metadata 目录
"""
import json
import shutil
from pathlib import Path
from typing import Optional

from .database import DatabaseManager
from .config import config
from .utils import logger, ensure_dir


class MetadataWriter:
    """上架元数据写入器"""

    def __init__(self):
        self.db = DatabaseManager()
        self.output_dir = Path(config.output_dir).resolve()
        self.sku_config = config.sku_config

    def write_full(self, book_id: str) -> bool:
        """写入完整的 metadata.json（全量刷新）"""
        book = self.db.get_book_by_id(book_id)
        if not book:
            logger.warning(f"书籍不存在: {book_id}")
            return False

        base_name = Path(book.filename).stem
        meta_dir = ensure_dir(self.output_dir / f"{base_name}_metadata")
        output = self.db.get_book_output(book_id)

        metadata = self._build_metadata(book, output, base_name)
        self._copy_cover(base_name, meta_dir)

        with open(meta_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"元数据写入成功: {meta_dir / 'metadata.json'}")
        return True

    def update_copywriting(self, book_id: str) -> bool:
        """仅更新文案/发布字段（文案生成阶段调用）"""
        book = self.db.get_book_by_id(book_id)
        if not book:
            return False

        base_name = Path(book.filename).stem
        meta_dir = ensure_dir(self.output_dir / f"{base_name}_metadata")
        meta_path = meta_dir / "metadata.json"

        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        else:
            metadata = self._build_metadata(book, self.db.get_book_output(book_id), base_name)

        output = self.db.get_book_output(book_id)
        if output:
            copywriting, publish = self._build_copywriting(output)
            metadata["copywriting"] = copywriting
            metadata["publish"] = publish

        self._copy_cover(base_name, meta_dir)

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        return True

    def _build_metadata(self, book, output, base_name: str) -> dict:
        """构建完整的元数据字典"""
        metadata = {
            "book_id": book.id,
            "title": book.title or "",
            "author": book.author or "",
            "filename": book.filename or "",
            "language": book.language or "",
            "files": {},
            "images": {},
            "sku": [],
            "copywriting": {},
            "publish": {},
        }

        if output:
            file_fields = {
                "bilingual_epub": "bilingual_epub",
                "chinese_epub": "chinese_epub",
                "bilingual_pdf": "bilingual_pdf",
                "chinese_pdf": "chinese_pdf",
                "english_pdf": "english_pdf",
                "summary_pdf": "summary_pdf",
            }
            for key, attr in file_fields.items():
                path = getattr(output, attr, None)
                if path:
                    metadata["files"][key] = self._relpath(path)

            copywriting, publish = self._build_copywriting(output)
            metadata["copywriting"] = copywriting
            metadata["publish"] = publish

        for sku in self.sku_config:
            metadata["sku"].append({
                "name": sku.get("name", ""),
                "price": sku.get("price", 0),
                "includes": sku.get("includes", []),
            })

        meta_dir = self.output_dir / f"{base_name}_metadata"
        cover_path = meta_dir / "cover.jpg"
        if cover_path.exists():
            metadata["images"]["cover"] = "cover.jpg"
        toc_path = meta_dir / "toc_preview.jpg"
        if toc_path.exists():
            metadata["images"]["toc_preview"] = "toc_preview.jpg"

        return metadata

    def _build_copywriting(self, output) -> tuple:
        """构建文案和发布信息"""
        copywriting = {}
        if output.xianyu_title:
            copywriting["xianyu"] = {
                "title": output.xianyu_title,
                "description": output.xianyu_description or "",
                "tags": [t.strip() for t in output.xianyu_tags.split(",") if t.strip()] if output.xianyu_tags else [],
            }
        if output.xiaohongshu_note:
            copywriting["xiaohongshu"] = {
                "note": output.xiaohongshu_note,
            }

        publish = {
            "pan_link_sku1": output.pan_link_sku1,
            "pan_link_sku2": output.pan_link_sku2,
            "pan_code": output.pan_code,
        }

        return copywriting, publish

    def _copy_cover(self, base_name: str, meta_dir: Path):
        """将封面图从电子书目录复制到 metadata 目录"""
        cover_src = self.output_dir / base_name / "cover.jpg"
        if cover_src.exists():
            shutil.copy2(cover_src, meta_dir / "cover.jpg")
            logger.info(f"封面图已复制到: {meta_dir / 'cover.jpg'}")

    def _relpath(self, path: str) -> str:
        """将绝对路径转为相对于 output 目录的路径"""
        try:
            return str(Path(path).relative_to(self.output_dir))
        except ValueError:
            return path


def write_metadata(book_id: str) -> bool:
    """便捷函数：写入完整元数据"""
    writer = MetadataWriter()
    return writer.write_full(book_id)
