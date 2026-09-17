import os
import sys
import tempfile
import zipfile
import shutil
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from bs4 import XMLParsedAsHTMLWarning
import warnings

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

TEST_INPUT_DIR = r"E:\ebooks\test-input"

REAL_EPUB = os.path.join(TEST_INPUT_DIR, "The AI Workshop_ The Complete Beginner's Guide to AI_ Your -- Foster, Milo.epub")


def get_doc_items_count(epub_path):
    book = epub.read_epub(epub_path)
    return sum(1 for item in book.get_items() if item.get_type() == ebooklib.ITEM_DOCUMENT)


def create_minimal_epub(tmp_path, num_docs):
    """创建一个只有指定数量文档项的最小 EPUB，用于边缘测试"""
    os.makedirs(tmp_path, exist_ok=True)
    epub_path = os.path.join(tmp_path, f"test_{num_docs}docs.epub")

    book = epub.EpubBook()
    book.set_identifier(f"test-{num_docs}")
    book.set_title(f"Test Book {num_docs} Docs")
    book.set_language("en")
    book.add_author("Test Author")

    for i in range(num_docs):
        chapter = epub.EpubHtml(title=f"Chapter {i+1}", file_name=f"chapter_{i+1}.xhtml", lang="en")
        chapter.content = f"<html><body><h1>Chapter {i+1}</h1><p>This is chapter {i+1} content.</p></body></html>"
        book.add_item(chapter)
        book.spine.append(chapter)

    if num_docs > 0:
        book.toc = tuple(book.items)

    nav = epub.EpubNav(title="Table of Contents", file_name="nav.xhtml")
    book.add_item(nav)
    book.spine.insert(0, nav)

    style = epub.EpubItem(uid="style_nav", file_name="style.css", media_type="text/css")
    style.content = "body { font-family: serif; }"
    book.add_item(style)

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(epub_path, book)
    return epub_path


class TestEPUBSplitterReal:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.tmp_dir = str(tmp_path)
        self.real_epub = REAL_EPUB

    def test_split_into_10_parts(self):
        from ebook_splitter.epub_splitter import EPUBSplitter
        splitter = EPUBSplitter(self.real_epub)
        parts = splitter.split(self.tmp_dir, num_parts=10)
        assert len(parts) == 10
        for p in parts:
            assert os.path.exists(p)
            assert p.endswith('.epub')

    def test_each_part_is_valid_epub(self):
        from ebook_splitter.epub_splitter import EPUBSplitter
        splitter = EPUBSplitter(self.real_epub)
        parts = splitter.split(self.tmp_dir, num_parts=10)
        for p in parts:
            book = epub.read_epub(p)
            assert book is not None
            doc_count = sum(1 for item in book.get_items() if item.get_type() == ebooklib.ITEM_DOCUMENT)
            assert doc_count > 0

    def test_all_parts_sum_to_original(self):
        from ebook_splitter.epub_splitter import EPUBSplitter
        splitter = EPUBSplitter(self.real_epub)
        parts = splitter.split(self.tmp_dir, num_parts=10)

        total_docs = 0
        for p in parts:
            book = epub.read_epub(p)
            doc_count = sum(1 for item in book.get_items() if item.get_type() == ebooklib.ITEM_DOCUMENT)
            total_docs += doc_count

        original_count = get_doc_items_count(self.real_epub)
        assert total_docs == original_count

    def test_part_content_not_empty(self):
        from ebook_splitter.epub_splitter import EPUBSplitter
        splitter = EPUBSplitter(self.real_epub)
        parts = splitter.split(self.tmp_dir, num_parts=10)
        for p in parts:
            book = epub.read_epub(p)
            html_items = [item for item in book.get_items() if item.get_type() == ebooklib.ITEM_DOCUMENT]
            assert len(html_items) > 0
            content = html_items[0].get_content().decode('utf-8', errors='ignore')
            assert len(content) > 0

    def test_parts_have_correct_metadata(self):
        from ebook_splitter.epub_splitter import EPUBSplitter
        original_book = epub.read_epub(self.real_epub)
        orig_title = original_book.get_metadata("DC", "title")[0][0] if original_book.get_metadata("DC", "title") else ""
        orig_author = original_book.get_metadata("DC", "creator")[0][0] if original_book.get_metadata("DC", "creator") else ""

        splitter = EPUBSplitter(self.real_epub)
        parts = splitter.split(self.tmp_dir, num_parts=10)

        for p in parts:
            book = epub.read_epub(p)
            title = book.get_metadata("DC", "title")[0][0] if book.get_metadata("DC", "title") else ""
            author = book.get_metadata("DC", "creator")[0][0] if book.get_metadata("DC", "creator") else ""
            assert orig_author in author or author == orig_author
            assert "part" in title.lower() or orig_title[:20] in title

    def test_parts_have_unique_filenames(self):
        from ebook_splitter.epub_splitter import EPUBSplitter
        splitter = EPUBSplitter(self.real_epub)
        parts = splitter.split(self.tmp_dir, num_parts=10)
        basenames = [os.path.basename(p) for p in parts]
        assert len(basenames) == len(set(basenames))
        assert all("part" in bn.lower() for bn in basenames)

    def test_balance_distribution(self):
        from ebook_splitter.epub_splitter import EPUBSplitter
        splitter = EPUBSplitter(self.real_epub)
        parts = splitter.split(self.tmp_dir, num_parts=10)

        doc_counts = []
        for p in parts:
            book = epub.read_epub(p)
            doc_count = sum(1 for item in book.get_items() if item.get_type() == ebooklib.ITEM_DOCUMENT)
            doc_counts.append(doc_count)

        max_count = max(doc_counts)
        min_count = min(doc_counts)
        assert max_count - min_count <= 1

    def test_preserves_resources(self):
        from ebook_splitter.epub_splitter import EPUBSplitter
        splitter = EPUBSplitter(self.real_epub)
        parts = splitter.split(self.tmp_dir, num_parts=10)

        for p in parts:
            with zipfile.ZipFile(p, 'r') as zf:
                names = zf.namelist()
                assert any(n.endswith('.css') for n in names)


class TestEPUBSplitterEdgeCases:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.tmp_dir = str(tmp_path)

    def test_edge_case_small_epub(self):
        from ebook_splitter.epub_splitter import EPUBSplitter
        epub_path = create_minimal_epub(self.tmp_dir, 5)
        splitter = EPUBSplitter(epub_path)
        parts = splitter.split(self.tmp_dir, num_parts=10)
        assert len(parts) >= 1
        for p in parts:
            if os.path.getsize(p) > 0:
                book = epub.read_epub(p)
                assert book is not None

    def test_edge_case_single_item(self):
        from ebook_splitter.epub_splitter import EPUBSplitter
        epub_path = create_minimal_epub(self.tmp_dir, 1)
        splitter = EPUBSplitter(epub_path)
        parts = splitter.split(self.tmp_dir, num_parts=10)
        assert len(parts) >= 1
        for p in parts:
            if os.path.getsize(p) > 0:
                book = epub.read_epub(p)
                assert book is not None
