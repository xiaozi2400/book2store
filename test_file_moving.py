"""
测试：文件转移至"已处理"文件夹的逻辑

直接从 auto() 末尾复制的移动逻辑，独立测试。
"""
import os
import shutil
import tempfile
from pathlib import Path


def move_epub_files(input_dir: str):
    """将 input 目录中的 epub 文件移到 '已处理' 文件夹（与 auto() 末尾逻辑一致）"""
    processed_dir = Path(input_dir) / "已处理"
    processed_dir.mkdir(exist_ok=True)

    moved_count = 0
    for epub_file in Path(input_dir).glob("*.epub"):
        shutil.move(str(epub_file), str(processed_dir / epub_file.name))
        moved_count += 1

    return moved_count


class TestFileMoving:
    """测试文件移动逻辑"""

    def test_move_epub_files(self):
        """场景1：移动 EPUB 文件 — 3 个 epub 应全部移至已处理/"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            # 创建 3 个 epub 文件
            for name in ["book1.epub", "book2.epub", "book3.epub"]:
                (tmpdir_path / name).write_text("fake epub content")

            moved = move_epub_files(tmpdir)

            assert moved == 3, f"期望移动3个文件，实际移动{moved}个"
            processed_dir = Path(tmpdir) / "已处理"
            assert processed_dir.exists(), "已处理/ 目录应存在"
            for name in ["book1.epub", "book2.epub", "book3.epub"]:
                assert (processed_dir / name).exists(), f"{name} 应在已处理/ 中"
            # 原始 input 目录不应再有 epub
            assert len(list(Path(tmpdir).glob("*.epub"))) == 0

    def test_does_not_move_non_epub(self):
        """场景2：不移动非 EPUB — .pdf 和 .txt 应保留在原目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "doc.pdf").write_text("pdf content")
            (tmpdir_path / "notes.txt").write_text("txt content")
            (tmpdir_path / "book.epub").write_text("epub content")

            moved = move_epub_files(tmpdir)

            assert moved == 1
            # 非 epub 文件应保留在原目录
            assert (tmpdir_path / "doc.pdf").exists(), ".pdf 文件不应被移动"
            assert (tmpdir_path / "notes.txt").exists(), ".txt 文件不应被移动"
            processed_dir = tmpdir_path / "已处理"
            assert (processed_dir / "book.epub").exists()

    def test_auto_creates_processed_dir(self):
        """场景3：目录不存在时自动创建 — 删除已处理/ 后运行，目录自动创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "test.epub").write_text("content")
            # 首次运行，自动创建
            move_epub_files(tmpdir)
            processed_dir = tmpdir_path / "已处理"
            assert processed_dir.is_dir()
            assert (processed_dir / "test.epub").exists()

            # 删除已处理目录和文件，重新跑
            shutil.rmtree(processed_dir)
            (tmpdir_path / "another.epub").write_text("content2")
            move_epub_files(tmpdir)
            assert processed_dir.is_dir(), "已处理/ 目录应被重新创建"
            assert (processed_dir / "another.epub").exists()

    def test_repeat_run_no_error(self):
        """场景4：重复运行不报错 — 第二次无文件可移动"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "book.epub").write_text("content")
            # 第一次运行
            first_moved = move_epub_files(tmpdir)
            assert first_moved == 1

            # 第二次运行（无 epub 文件可移动）
            second_moved = move_epub_files(tmpdir)
            assert second_moved == 0, f"第二次应移动0个文件，实际移动{second_moved}"