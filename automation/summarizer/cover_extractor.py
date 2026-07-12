"""
封面提取模块 - 从 EPUB 中提取封面图片
"""
import os
import zipfile
import tempfile
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree

# 导入 logger
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from automation.utils import logger


def extract_cover_from_epub(epub_path: str) -> Optional[str]:
    """从EPUB中提取封面图片，返回临时文件路径

    Args:
        epub_path: EPUB文件路径

    Returns:
        临时封面文件路径，或 None
    """
    try:
        cover_data = None
        cover_name = None
        cover_epub_path = None

        with zipfile.ZipFile(epub_path, 'r') as z:
            all_files = z.namelist()

            # 第一步: 查找OPF文件
            opf_path = None
            for f in all_files:
                if f.lower().endswith('.opf'):
                    opf_path = f
                    break

            if opf_path:
                try:
                    opf_content = z.read(opf_path)
                    root = ElementTree.fromstring(opf_content)
                    ns = {'opf': 'http://www.idpf.org/2007/opf'}

                    # 查找元数据中的封面信息
                    for meta in root.findall('.//opf:meta', ns):
                        name = meta.get('name')
                        content = meta.get('content')
                        if name and name.lower() == 'cover':
                            cover_name = content
                            logger.info(f"从元数据找到封面ID: {cover_name}")
                            break

                    # 构建manifest id→href映射
                    manifest_items = {}
                    for item in root.findall('.//opf:item', ns):
                        item_id = item.get('id')
                        href = item.get('href')
                        if item_id and href:
                            manifest_items[item_id] = href

                    opf_dir = str(Path(opf_path).parent)
                    if opf_dir == '.':
                        opf_dir = ''

                    def resolve_manifest_path(href: str) -> str:
                        if opf_dir:
                            return str(Path(opf_dir) / href).replace('\\', '/')
                        return href

                    # 方法1: 通过meta中的cover ID查找manifest id→href映射
                    if cover_name and cover_name in manifest_items:
                        cover_href = manifest_items[cover_name]
                        cover_epub_path = resolve_manifest_path(cover_href)
                        if cover_epub_path in all_files:
                            cover_data = z.read(cover_epub_path)
                            logger.info(f"通过manifest id→href找到封面: {cover_epub_path}")

                    # 方法2: EPUB 3 properties="cover-image"
                    if not cover_data:
                        for item in root.findall('.//opf:item', ns):
                            props = item.get('properties', '')
                            if 'cover-image' in props.lower():
                                cover_href = item.get('href')
                                cover_epub_path = resolve_manifest_path(cover_href)
                                if cover_epub_path in all_files:
                                    cover_data = z.read(cover_epub_path)
                                    logger.info(f"通过EPUB3 properties找到封面: {cover_epub_path}")
                                    break

                    # 方法3: 尝试硬编码路径（作为后备）
                    if not cover_data and cover_name:
                        possible_paths = [
                            cover_name,
                            f'OEBPS/{cover_name}',
                            f'OEBPS/images/{cover_name}',
                            f'OEBPS/image/{cover_name}',
                        ]
                        for path in possible_paths:
                            if path in all_files:
                                cover_data = z.read(path)
                                cover_epub_path = path
                                logger.info(f"通过硬编码路径找到封面: {path}")
                                break
                except Exception as e:
                    logger.warning(f"解析OPF封面信息失败: {e}")

            # 降级: 取最大图片（作为最后后备）
            if not cover_data:
                logger.info("从元数据未找到封面，尝试使用最大的图片")
                images = []
                for f in all_files:
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                        try:
                            info = z.getinfo(f)
                            images.append((-info.file_size, f))
                        except Exception:
                            pass
                if images:
                    images.sort()
                    largest_size, largest_path = images[0]
                    cover_data = z.read(largest_path)
                    cover_epub_path = largest_path
                    logger.info(f"使用最大的图片作为封面: {largest_path} ({-largest_size} 字节)")

            if cover_data:
                ext = 'jpg'
                if cover_epub_path and '.' in cover_epub_path:
                    ext = cover_epub_path.split('.')[-1].lower()
                elif cover_name and '.' in cover_name:
                    ext = cover_name.split('.')[-1].lower()

                with tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False) as f:
                    f.write(cover_data)
                    return f.name

        return None
    except Exception as e:
        logger.warning(f"提取EPUB封面失败: {e}")
        import traceback
        logger.warning(traceback.format_exc())
        return None
