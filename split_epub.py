"""
EPUB拆分脚本 - 保留原书1/10正文
保留：出版信息、目录、正文前1/10章节
"""
import os
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from pathlib import Path
import re


def is_front_matter(name: str) -> bool:
    """是否前页/版权页"""
    n = name.lower()
    return 'front' in n or 'titlepage' in n or n.startswith('title') or 'copyright' in n


def is_chapter(name: str) -> bool:
    """是否是章节"""
    n = name.lower()
    base = n.split('.')[0]
    if base.startswith('c') and len(base) > 1:
        suffix = base[1:]
        if suffix.isdigit():
            return True
    if 'contents' in n:
        return False
    if 'chapter' in n:
        return True
    return False


def is_back_matter(name: str) -> bool:
    """是否后记/附录"""
    n = name.lower()
    return 'back' in n or 'appendix' in n or 'index' in n


def split_epub(input_path: str, output_path: str = None, ratio: float = 0.1):
    """拆分EPUB，保留1/10正文"""
    input_file = Path(input_path)
    stem = input_file.stem

    if output_path is None:
        output_path = input_file.parent / f"{stem}_test.epub"

    print(f"读取EPUB: {input_path}")
    book = epub.read_epub(input_path)

    items = list(book.get_items())

    doc_items = [item for item in items if item.get_type() == ebooklib.ITEM_DOCUMENT]

    chapters = [item for item in doc_items if is_chapter(item.get_name())]
    front_items = [item for item in doc_items if is_front_matter(item.get_name())]
    back_items = [item for item in doc_items if is_back_matter(item.get_name())]
    toc_items = [item for item in doc_items if 'toc' in item.get_name().lower()]

    print(f"总章节数: {len(chapters)}, 前页: {len(front_items)}, 后记: {len(back_items)}")

    keep_chapter_count = max(1, int(len(chapters) * ratio))
    keep_chapters = chapters[:keep_chapter_count]
    print(f"保留章节数: {keep_chapter_count} ({ratio*100:.0f}%)")

    new_book = epub.EpubBook()

    for meta_key in ['title', 'creator', 'language', 'publisher', 'identifier', 'description']:
        meta = book.get_metadata('DC', meta_key)
        if meta:
            new_book.add_metadata('DC', meta_key, meta[0][0])

    kept_items = []

    for item in items:
        item_name = item.get_name()
        item_type = item.get_type()

        if item_type == ebooklib.ITEM_COVER:
            new_book.add_item(item)
            kept_items.append(item)
            continue

        if item_type == ebooklib.ITEM_IMAGE:
            if 'cover' in item_name.lower():
                new_book.add_item(item)
                kept_items.append(item)
            continue

        if item_type == ebooklib.ITEM_STYLE:
            new_book.add_item(item)
            kept_items.append(item)
            continue

        if item_type == ebooklib.ITEM_DOCUMENT:
            if item in toc_items:
                new_book.add_item(item)
                kept_items.append(item)
            elif item in front_items:
                new_book.add_item(item)
                kept_items.append(item)
            elif item in keep_chapters:
                new_book.add_item(item)
                kept_items.append(item)
            elif item in back_items:
                new_book.add_item(item)
                kept_items.append(item)

    spine_items = []
    for item in kept_items:
        if item.get_type() == ebooklib.ITEM_DOCUMENT and item not in toc_items:
            spine_items.append(item)

    new_book.spine = spine_items

    new_toc = []
    for i, item in enumerate(spine_items):
        title = f"Chapter {i+1}"
        try:
            content = item.get_content().decode('utf-8', errors='ignore')
            soup = BeautifulSoup(content, 'html.parser')
            h = soup.find(['h1', 'h2', 'h3', 'title'])
            if h:
                title = h.get_text(strip=True)[:50]
        except:
            pass
        new_toc.append(new_book.toc.append(
            epub.Link(item.get_name(), title, f"chapter_{i+1}")
        ))

    new_book.add_item(epub.EpubNcx())
    new_book.add_item(epub.EpubNav())

    print(f"保存EPUB: {output_path}")
    try:
        epub.write_epub(output_path, new_book, {})
    except Exception as e:
        print(f"警告: {e}")

    output_size = os.path.getsize(output_path)
    print(f"✅ 完成! 拆分后的文件: {output_path} ({output_size/1024:.1f}KB)")
    print(f"保留: 前页 {len(front_items)}个, 章节 {len(keep_chapters)}个, 后记 {len(back_items)}个")
    return output_path


if __name__ == "__main__":
    input_dir = r"E:\ebooks\input"
    input_file = os.path.join(input_dir, "Company Of One _ Why Staying Small Is the Next Big Thing for -- Paul Jarvis, (Business writer).epub")
    output_file = os.path.join(input_dir, "test_10percent.epub")
    split_epub(input_file, output_file, ratio=0.1)
