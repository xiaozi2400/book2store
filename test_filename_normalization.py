"""测试文件名规范化功能 (_fix_filenames)"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from automation.directory_scanner import DirectoryScanner


class TestFilenameNormalization(unittest.TestCase):
    """测试 _fix_filenames 方法的文件名规范化逻辑"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.input_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_test_file(self, filename: str) -> Path:
        """创建测试用空 .epub 文件"""
        file_path = self.input_dir / filename
        file_path.touch()
        return file_path

    def _run_fix_filenames(self):
        """创建 scanner 并运行 _fix_filenames"""
        with patch('automation.directory_scanner.DatabaseManager'):
            scanner = DirectoryScanner()
            scanner.input_dir = self.input_dir
            scanner._fix_filenames()

    def _get_files(self):
        """获取当前目录下的所有 .epub 文件名"""
        return sorted([p.name for p in self.input_dir.glob("*.epub")])

    # ---- 测试用例 ----

    def test_double_dash(self):
        """含 --，取前面部分"""
        self._create_test_file("Book-Title--Some-Extra.epub")
        self._run_fix_filenames()
        self.assertEqual(self._get_files(), ["Book-Title.epub"])

    def test_long_name_no_dash(self):
        """超长（无 --），截断至60字符"""
        long_name = "A very long book title with many words in it and keeps going more than sixty characters.epub"
        self._create_test_file(long_name)
        self._run_fix_filenames()
        files = self._get_files()
        self.assertEqual(len(files), 1)
        stem = files[0].replace(".epub", "")
        self.assertLessEqual(len(stem), 60)
        self.assertFalse(stem.startswith(" ") and stem.endswith(" "))

    def test_double_dash_and_long(self):
        """含 -- 且前面超60字符，取 -- 前部分再截断"""
        long_name = "This is a really long book title that goes well beyond 60--and extra.epub"
        self._create_test_file(long_name)
        self._run_fix_filenames()
        self.assertEqual(
            self._get_files(),
            ["This is a really long book title that goes well beyond 60.epub"]
        )

    def test_double_dash_with_spaces(self):
        """-- 前后有空格"""
        self._create_test_file("Title  --  Extra.epub")
        self._run_fix_filenames()
        self.assertEqual(self._get_files(), ["Title.epub"])

    def test_normal_name(self):
        """正常文件名（不变）"""
        self._create_test_file("Normal Book.epub")
        self._run_fix_filenames()
        self.assertEqual(self._get_files(), ["Normal Book.epub"])

    def test_trailing_spaces(self):
        """仅尾随空格"""
        self._create_test_file("Trailing Space .epub")
        self._run_fix_filenames()
        self.assertEqual(self._get_files(), ["Trailing Space.epub"])

    def test_multiple_files(self):
        """同时处理多个文件"""
        self._create_test_file("Book1--Extra.epub")
        self._create_test_file("Book2.epub")
        self._create_test_file("Book3  --  Extra.epub")
        self._run_fix_filenames()
        self.assertEqual(
            self._get_files(),
            sorted(["Book1.epub", "Book2.epub", "Book3.epub"])
        )


if __name__ == "__main__":
    unittest.main()