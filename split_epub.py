"""
EPUB拆分脚本 - 只保留前1/10内容用于测试
"""
import os
import sys
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from pathlib import Path


def split_epub(input_path: str, output_path: str = None, ratio: float = 0.1):
    """拆分EPUB文件，只保留前1/10内容"""
    input_file = Path(input_path)
    stem = input_file.stem

    if output_path is None:
        output_path = input_file.parent / f"{stem}_test.epub"

    print(f"读取EPUB: {input_path}")
    book = epub.read_epub(input_path)

    items = list(book.get_items())
    doc_items = [item for item in items if item.get_type() == ebooklib.ITEM_DOCUMENT]

    print(f"总内容项: {len(doc_items)}")

    keep_count = max(1, int(len(doc_items) * ratio))
    print(f"保留内容项: {keep_count} ({ratio*100:.0f}%)")

    new_book = epub.EpubBook()

    metadata = book.get_metadata('DC', 'title')
    if metadata:
        new_book.set_title(metadata[0][0])

    metadata = book.get_metadata('DC', 'language')
    if metadata:
        new_book.set_language(metadata[0][0])

    new_items = []
    new_spine = []
    new_toc = []

    for i, item in enumerate(doc_items[:keep_count]):
        new_items.append(item)
        new_book.add_item(item)
        new_spine.append(item)

        try:
            content = item.get_content().decode('utf-8', errors='ignore')
            soup = BeautifulSoup(content, 'html.parser')
            title = soup.find(['h1', 'h2', 'title'])
            if title:
                title_text = title.get_text(strip=True)[:50]
            else:
                title_text = f"Chapter {i+1}"
        except:
            title_text = f"Chapter {i+1}"

        new_toc.append(new_book.toc.append(
            epub.Link(item.get_name(), title_text, f"chapter_{i+1}")
        ))

    new_book.spine = new_spine
    new_book.toc = new_toc

    new_book.add_item(epub.EpubNcx())
    new_book.add_item(epub.EpubNav())

    print(f"保存EPUB: {output_path}")
    epub.write_epub(output_path, new_book, {})

    print(f"✅ 完成! 拆分后的文件: {output_path}")
    return output_path


if __name__ == "__main__":
    input_dir = r"E:\ebooks\input"
    input_file = os.path.join(input_dir, "Company Of One _ Why Staying Small Is the Next Big Thing for -- Paul Jarvis, (Business writer).epub")

    output_file = os.path.join(input_dir, "test_10percent.epub")

    split_epub(input_file, output_file, ratio=0.1)
