"""
测试 AI 客户端文案生成功能
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAIClientCopywriting:
    """测试 ai_client 文案生成相关方法"""

    def test_generate_xiaohongshu_note_no_db_attribute(self):
        """
        验证 generate_xiaohongshu_note 不依赖 self.db

        期望：调用时不会抛出 AttributeError: 'AIClient' object has no attribute 'db'
        """
        from automation.ai_client import AIClient

        client = AIClient()
        assert hasattr(client, 'db') is False, "AIClient 不应该有 db 属性"

        book_info = {
            'id': 'test-book-id',
            'title': '测试书籍',
            'author': '测试作者',
            'summary': '这是一个测试摘要'
        }

        result = client.generate_xiaohongshu_note(book_info)
        assert result is not None


class TestXianyuPublisherMetaDir:
    """测试 xianyu_publisher meta_dir 顺序"""

    def test_publish_method_meta_dir_defined_before_use(self):
        """
        验证 publish() 方法中 meta_dir 在使用前已定义

        期望：代码中 meta_dir 的赋值在使用之前
        """
        import ast
        from pathlib import Path

        xianyu_path = Path(__file__).parent.parent / "automation" / "xianyu_publisher.py"
        with open(xianyu_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "publish":
                func_source = ast.get_source_segment(source, node)
                if func_source is None:
                    lines = source.split('\n')
                    func_source = '\n'.join(lines[node.lineno - 1:node.end_lineno])

                meta_dir_assign_lines = []
                meta_dir_use_lines = []

                for i, line in enumerate(func_source.split('\n'), 1):
                    if 'meta_dir' in line and ('=' in line and 'self._get_meta_dir' in line):
                        meta_dir_assign_lines.append(i)
                    if 'meta_dir' in line and '=' not in line:
                        meta_dir_use_lines.append(i)

                if meta_dir_assign_lines and meta_dir_use_lines:
                    assert min(meta_dir_assign_lines) < min(meta_dir_use_lines), \
                        f"meta_dir 赋值行 {meta_dir_assign_lines} 应该在首次使用行 {meta_dir_use_lines} 之前"


class TestMetadataWriter:
    """测试 metadata_writer"""

    def test_write_copywriting_no_cover_copy(self):
        """
        验证 write_copywriting 不复制封面到书籍目录

        期望：shutil.copy2 只在 meta_dir 下操作，不在书籍目录下操作
        """
        import ast
        from pathlib import Path

        mw_path = Path(__file__).parent.parent / "automation" / "metadata_writer.py"
        with open(mw_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "write_copywriting":
                func_source = ast.get_source_segment(source, node)
                if func_source is None:
                    lines = source.split('\n')
                    func_source = '\n'.join(lines[node.lineno - 1:node.end_lineno])

                lines = func_source.split('\n')
                for line in lines:
                    if 'shutil.copy2' in line:
                        assert 'meta_dir' in line, \
                            f"封面复制应该只在 meta_dir 下: {line.strip()}"


class TestContentSummarizerCover:
    """测试 content_summarizer 封面复制"""

    def test_summarize_no_cover_in_book_dir(self):
        """
        验证生成精简版时封面只复制到 metadata 目录，不复制到书籍目录

        期望：output_dir / cover.jpg 相关的复制逻辑被删除
        """
        import ast
        from pathlib import Path

        cs_path = Path(__file__).parent.parent / "automation" / "content_summarizer.py"
        with open(cs_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "summarize":
                func_source = ast.get_source_segment(source, node)
                if func_source is None:
                    lines = source.split('\n')
                    func_source = '\n'.join(lines[node.lineno - 1:node.end_lineno])

                lines = func_source.split('\n')
                cover_to_output_dir = False
                for line in lines:
                    if 'cover' in line.lower() and 'output_dir' in line and '/' in line:
                        if 'meta_dir' not in line and '.stem' not in line:
                            cover_to_output_dir = True

                assert not cover_to_output_dir, \
                    "书籍目录下不应复制封面，只应在 metadata 目录下复制"