"""
章节提取模块 - 从 EPUB 提取章节内容
"""
import os
import sys
from pathlib import Path
from typing import Optional, List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from automation.utils import logger
from automation.config import config


def extract_chapters(book_id: str, epub_path: str) -> List[Dict[str, str]]:
    """提取章节内容 - 优先从中文版本EPUB提取"""
    if epub_path:
        output_dir = Path(config.output_dir) / Path(epub_path).stem.strip() / "EPUB"
        chinese_epub_path = output_dir / f"{Path(epub_path).stem.strip()}-中文版本.epub"
    else:
        chinese_epub_path = None

    if chinese_epub_path and chinese_epub_path.exists():
        logger.info(f"从中文EPUB提取章节: {chinese_epub_path}")
        return extract_from_chinese_epub(str(chinese_epub_path))

    return extract_from_epub(epub_path)


def extract_from_chinese_epub(epub_path: str) -> List[Dict[str, str]]:
    """从中文EPUB提取章节内容，按HTML标题标签(h1/h2/h3)智能分割章节"""
    try:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup

        book = epub.read_epub(epub_path)
        chapters = []
        current_chapter = {"title": "前言", "content": ""}

        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                content = item.get_content().decode('utf-8')
                soup = BeautifulSoup(content, 'html.parser')

                body = soup.body
                if body is None:
                    text = soup.get_text(separator='\n', strip=True)
                    if text:
                        current_chapter["content"] += text + "\n"
                    continue

                headings = body.find_all(['h1', 'h2', 'h3'])
                if not headings:
                    text = body.get_text(separator='\n', strip=True)
                    if text and len(text) > 200:
                        title = _extract_title(soup)
                        chapters.append({
                            "title": title or f"第{len(chapters)+1}章",
                            "content": text[:5000]
                        })
                    elif text:
                        current_chapter["content"] += text + "\n"
                else:
                    _process_chapter_nodes(body, chapters, current_chapter)

        if current_chapter["content"].strip():
            chapters.append(current_chapter)

        logger.info(f"从中文EPUB提取到 {len(chapters)} 个章节")
        return chapters[:10]
    except Exception as e:
        logger.warning(f"从中文EPUB提取章节失败: {e}")
        import traceback
        logger.warning(traceback.format_exc())
        return []


def _process_chapter_nodes(parent, chapters, current_chapter):
    """递归处理HTML节点，在标题标签处分割章节"""
    from bs4 import Tag

    for elem in parent.children:
        if not isinstance(elem, Tag):
            continue

        if elem.name in ('h1', 'h2', 'h3'):
            title_text = elem.get_text().strip()
            if title_text and len(title_text) < 100:
                if current_chapter["content"].strip():
                    chapters.append(dict(current_chapter))
                current_chapter.clear()
                current_chapter.update({"title": title_text, "content": ""})
        else:
            child_headings = elem.find_all(['h1', 'h2', 'h3'])
            if child_headings:
                _process_chapter_nodes(elem, chapters, current_chapter)
            else:
                text = elem.get_text(separator='\n', strip=True)
                if text:
                    current_chapter["content"] += text + "\n"


def extract_from_epub(epub_path: str) -> List[Dict[str, str]]:
    """从EPUB提取章节内容"""
    import ebooklib
    from ebooklib import epub

    chapters = []
    try:
        book = epub.read_epub(epub_path)

        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(item.get_content(), 'html.parser')

                text = soup.get_text()
                if len(text) > 500:
                    title = _extract_title(soup)
                    chapters.append({
                        'title': title or f"第{len(chapters)+1}章",
                        'content': text[:5000]
                    })

    except Exception as e:
        logger.warning(f"提取章节失败: {e}")

    return chapters[:10]


def _extract_title(soup) -> Optional[str]:
    """提取标题"""
    for tag in soup.find_all(['h1', 'h2', 'h3', 'title']):
        text = tag.get_text().strip()
        if text and len(text) < 100:
            return text
    return None


def extract_chinese_title(book_id: str, epub_path: str = None) -> Optional[str]:
    """从中文版本EPUB中提取中文书名"""
    if epub_path:
        output_dir = Path(config.output_dir) / Path(epub_path).stem.strip() / "EPUB"
        chinese_epub_path = output_dir / f"{Path(epub_path).stem.strip()}-中文版本.epub"
    else:
        return None

    if not chinese_epub_path.exists():
        return None

    try:
        import ebooklib
        from ebooklib import epub

        book = epub.read_epub(str(chinese_epub_path))
        metadata = book.get_metadata()
        if metadata and metadata[0] and metadata[0].get('title'):
            return metadata[0]['title'][0]
    except Exception as e:
        logger.warning(f"从EPUB提取中文书名失败: {e}")

    return None
