"""
测试：文件转移至"已处理"文件夹的逻辑

直接从 automation.utils.move_processed_epubs 导入并测试。
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from automation.utils import move_processed_epubs


class TestFileMoving:
    """测试文件移动逻辑"""

    def test_move_epub_files(self):
        """场景1：移动 EPUB 文件 — 3 个 epub 应全部移至已处理/"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            for name in ["book1.epub", "book2.epub", "book3.epub"]:
                (tmpdir_path / name).write_text("fake epub content")

            moved = move_processed_epubs(tmpdir)

            assert moved == 3, f"期望移动3个文件，实际移动{moved}个"
            processed_dir = Path(tmpdir) / "已处理"
            assert processed_dir.exists(), "已处理/ 目录应存在"
            for name in ["book1.epub", "book2.epub", "book3.epub"]:
                assert (processed_dir / name).exists(), f"{name} 应在已处理/ 中"
            assert len(list(Path(tmpdir).glob("*.epub"))) == 0

    def test_does_not_move_non_epub(self):
        """场景2：不移动非 EPUB — .pdf 和 .txt 应保留在原目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "doc.pdf").write_text("pdf content")
            (tmpdir_path / "notes.txt").write_text("txt content")
            (tmpdir_path / "book.epub").write_text("epub content")

            moved = move_processed_epubs(tmpdir)

            assert moved == 1
            assert (tmpdir_path / "doc.pdf").exists(), ".pdf 文件不应被移动"
            assert (tmpdir_path / "notes.txt").exists(), ".txt 文件不应被移动"
            processed_dir = tmpdir_path / "已处理"
            assert (processed_dir / "book.epub").exists()

    def test_auto_creates_processed_dir(self):
        """场景3：目录不存在时自动创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "test.epub").write_text("content")
            move_processed_epubs(tmpdir)
            processed_dir = tmpdir_path / "已处理"
            assert processed_dir.is_dir()
            assert (processed_dir / "test.epub").exists()

            shutil.rmtree(processed_dir)
            (tmpdir_path / "another.epub").write_text("content2")
            move_processed_epubs(tmpdir)
            assert processed_dir.is_dir(), "已处理/ 目录应被重新创建"
            assert (processed_dir / "another.epub").exists()

    def test_repeat_run_no_error(self):
        """场景4：重复运行不报错 — 第二次无文件可移动"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "book.epub").write_text("content")
            first_moved = move_processed_epubs(tmpdir)
            assert first_moved == 1

            second_moved = move_processed_epubs(tmpdir)
            assert second_moved == 0, f"第二次应移动0个文件，实际移动{second_moved}"

    def test_name_conflict_adds_timestamp(self):
        """场景5：同名已存在时追加时间戳而非覆盖"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            # 创建同名文件
            (tmpdir_path / "book.epub").write_text("original")
            # 先移动一次
            move_processed_epubs(tmpdir)
            # 再创建一个同名文件
            (tmpdir_path / "book.epub").write_text("second")
            # 第二次移动
            moved = move_processed_epubs(tmpdir)
            assert moved == 1
            processed_dir = tmpdir_path / "已处理"
            # 应该有两个文件：book.epub 和 book_时间戳.epub
            files = list(processed_dir.glob("*.epub"))
            assert len(files) == 2, f"应有两个文件，实际有 {len(files)}: {files}"
