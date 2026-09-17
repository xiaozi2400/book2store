"""
测试 AI 客户端文案生成功能的历史 bug 修复

本文件中的 TestXianyuPublisherMetaDir / TestMetadataWriter / TestContentSummarizerCover
使用 AST 静态分析验证源码中不存在问题代码，属于代码存在性检查而非行为测试。
"""
import pytest
import ast
from pathlib import Path


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
    """验证 xianyu_publisher.py publish() 中 meta_dir 在使用前已定义"""

    def test_publish_method_meta_dir_defined_before_use(self):
        """
        AST 检查：meta_dir 赋值行号 < 使用行号
        """
        xianyu_path = Path(__file__).parent.parent.parent / "automation" / "publishing" / "xianyu_publisher.py"
        source = xianyu_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "publish":
                lines = source.split('\n')
                func_lines = lines[node.lineno - 1:node.end_lineno]
                func_source = '\n'.join(func_lines)

                meta_dir_assign_lines = []
                meta_dir_use_lines = []

                for i, line in enumerate(func_lines, node.lineno):
                    stripped = line.strip()
                    if 'meta_dir' in stripped and '=' in stripped and 'self._get_meta_dir' in stripped:
                        meta_dir_assign_lines.append(i)
                    if 'meta_dir' in stripped and '=' not in stripped:
                        meta_dir_use_lines.append(i)

                if meta_dir_assign_lines and meta_dir_use_lines:
                    assert min(meta_dir_assign_lines) < min(meta_dir_use_lines), \
                        f"meta_dir 赋值行 {meta_dir_assign_lines} 应该在首次使用行 {meta_dir_use_lines} 之前"


class TestMetadataWriter:
    """验证 metadata_writer.py 中 shutil.copy2 只在 meta_dir 下操作"""

    def test_write_copywriting_no_cover_copy(self):
        """
        AST 检查：shutil.copy2 调用行必须包含 'meta_dir'
        """
        mw_path = Path(__file__).parent.parent.parent / "automation" / "metadata_writer.py"
        source = mw_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "write_copywriting":
                lines = source.split('\n')
                func_lines = lines[node.lineno - 1:node.end_lineno]
                for line in func_lines:
                    if 'shutil.copy2' in line:
                        assert 'meta_dir' in line, \
                            f"封面复制应该只在 meta_dir 下: {line.strip()}"


class TestContentSummarizerCover:
    """验证 content_summarizer.py 中封面不复制到书籍 output_dir 根目录"""

    def test_summarize_no_cover_in_book_dir(self):
        """
        AST 检查：cover 相关且含 output_dir 且含 '/' 的行，必须也含 meta_dir 或 .stem
        """
        cs_path = Path(__file__).parent.parent.parent / "automation" / "summarizer" / "content_summarizer.py"
        source = cs_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "summarize":
                lines = source.split('\n')
                func_lines = lines[node.lineno - 1:node.end_lineno]
                for line in func_lines:
                    if 'cover' in line.lower() and 'output_dir' in line and '/' in line:
                        if 'meta_dir' not in line and '.stem' not in line:
                            raise AssertionError(
                                f"书籍目录下不应复制封面，只应在 metadata 目录下复制: {line.strip()}"
                            )
