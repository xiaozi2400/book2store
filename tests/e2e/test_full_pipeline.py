"""E2E测试：完整流水线测试 (跳过发布)"""
import sys
import shutil
import subprocess
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from automation.database import get_session, close_session
from automation.models import Book, BookOutput, ProcessingLog
from automation.config import config


# 测试书籍标识
BOOK_NAME = "little-prince"
INPUT_EPUB = Path("data") / f"{BOOK_NAME}.epub"


@pytest.fixture(scope="module")
def reset_database():
    """清理数据库中与测试书籍相关的所有记录（强制重新翻译）"""
    session = get_session()
    try:
        # 1. 查找测试书籍（精确匹配文件名）
        book = session.query(Book).filter(Book.filename == f"{BOOK_NAME}.epub").first()
        if book:
            book_id = book.id

            # 2. 清理关联记录：BookOutput
            session.query(BookOutput).filter(BookOutput.book_id == book_id).delete()

            # 3. 清理关联记录：ProcessingLog
            session.query(ProcessingLog).filter(ProcessingLog.book_id == book_id).delete()

            # 4. 清理关联记录：TokenUsage
            from automation.models import TokenUsage
            session.query(TokenUsage).filter(TokenUsage.book_id == book_id).delete()

            # 5. 清理关联记录：ShareLink
            from automation.models import ShareLink
            session.query(ShareLink).filter(ShareLink.book_id == book_id).delete()

            # 6. 删除 Book 记录（TranslationCache 无外键关联 book，
            #    且 Book/BookOutput 已删除后无法触发缓存命中，无需清理）
            session.delete(book)

            session.commit()
    except Exception as e:
        session.rollback()
        print(f"清理数据库记录时出错: {e}")
    finally:
        close_session(session)

    yield


@pytest.fixture(scope="module")
def clean_environment():
    """测试前清理 output 和 metadata 目录"""
    output_dir = Path(config.output_dir)

    # 清理输出目录
    book_output_dir = output_dir / BOOK_NAME
    if book_output_dir.exists():
        shutil.rmtree(book_output_dir)

    # 清理 metadata 目录
    metadata_dir = output_dir / f"{BOOK_NAME}_metadata"
    if metadata_dir.exists():
        shutil.rmtree(metadata_dir)

    yield

    # 测试后不清理，保留产物供检查


@pytest.fixture(scope="module")
def clean_processed_dir():
    """清理"已处理"目录下的测试文件"""
    input_dir = Path(config.input_dir)
    processed_dir = input_dir / "已处理"

    if processed_dir.exists():
        # 清理 processed 目录下的测试文件
        processed_epub = processed_dir / f"{BOOK_NAME}.epub"
        if processed_epub.exists():
            processed_epub.unlink()
            print(f"\n已清理: {processed_epub}")

    yield


@pytest.fixture(scope="module")
def ensure_input_exists():
    """确保测试用的 epub 文件存在"""
    if not INPUT_EPUB.exists():
        pytest.skip(f"测试文件不存在: {INPUT_EPUB}")
    return INPUT_EPUB


@pytest.fixture(scope="module")
def setup_input_file(ensure_input_exists):
    """将测试 epub 复制到 input_dir"""
    input_dir = Path(config.input_dir)
    input_dir.mkdir(parents=True, exist_ok=True)
    dest_path = input_dir / f"{BOOK_NAME}.epub"
    shutil.copy2(ensure_input_exists, dest_path)
    yield dest_path
    # 测试后清理 input_dir 中的测试文件
    if dest_path.exists():
        dest_path.unlink()


class TestFullPipeline:
    """完整流水线 E2E 测试"""

    def test_pipeline_execution(self, reset_database, clean_environment, clean_processed_dir, setup_input_file):
        """执行完整流水线（跳过发布）"""
        # 切换到项目根目录执行命令
        project_root = Path(__file__).parent.parent.parent

        cmd = [
            sys.executable, "-m", "automation.main",
            "auto",
            "--skip-publish",
            "--skip-cache"
        ]

        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=600  # 10分钟超时
        )

        print("\n=== STDOUT ===")
        print(result.stdout)
        if result.stderr:
            print("\n=== STDERR ===")
            print(result.stderr)

        assert result.returncode == 0, f"命令执行失败: {result.stderr}"

    def test_xianyu_main_images(self):
        """验证闲鱼主图：检查 metadata 目录下是否有主图 HTML/JPG"""
        metadata_dir = Path(config.output_dir) / f"{BOOK_NAME}_metadata"

        # 检查是否有主图 JPG 文件
        main_images = list(metadata_dir.glob("main_image_*.jpg"))
        assert len(main_images) > 0, f"未找到闲鱼主图文件: {metadata_dir}/main_image_*.jpg"

        # 检查是否有临时 HTML（主图生成过程中的中间产物）
        temp_html = metadata_dir / "_main_image_temp.html"
        # temp_html 不强制要求存在（可能已被清理）

        print(f"\n闲鱼主图: {[f.name for f in main_images]}")

    def test_xianyu_copywriting(self):
        """验证闲鱼文案：检查 metadata 目录下是否有 xianyu_listing.txt"""
        metadata_dir = Path(config.output_dir) / f"{BOOK_NAME}_metadata"
        xianyu_file = metadata_dir / "xianyu_listing.txt"

        assert xianyu_file.exists(), f"未找到闲鱼文案: {xianyu_file}"
        assert xianyu_file.stat().st_size > 0, "闲鱼文案文件为空"

        # 验证内容包含必要字段
        content = xianyu_file.read_text(encoding="utf-8")
        assert len(content) > 50, "闲鱼文案内容过短"

        print(f"\n闲鱼文案: {xianyu_file.name} ({len(content)} 字符)")

    def test_xiaohongshu_copywriting(self):
        """验证小红书文案：检查 metadata 目录下是否有 xiaohongshu_note.txt"""
        metadata_dir = Path(config.output_dir) / f"{BOOK_NAME}_metadata"
        xhs_file = metadata_dir / "xiaohongshu_note.txt"

        assert xhs_file.exists(), f"未找到小红书文案: {xhs_file}"
        assert xhs_file.stat().st_size > 0, "小红书文案文件为空"

        print(f"\n小红书文案: {xhs_file.name} ({xhs_file.stat().st_size} 字节)")

    def test_chinese_pdf(self):
        """验证中文 PDF：检查 output/little-prince/中文-little-prince/ 下是否有 PDF"""
        book_output_dir = Path(config.output_dir) / BOOK_NAME
        chinese_dir = book_output_dir / f"中文-{BOOK_NAME}"

        pdf_files = list(chinese_dir.glob("*.pdf")) if chinese_dir.exists() else []
        assert len(pdf_files) > 0, f"未找到中文 PDF: {chinese_dir}/*.pdf"

        pdf_path = pdf_files[0]
        assert pdf_path.stat().st_size > 1000, f"中文 PDF 文件过小: {pdf_path.stat().st_size}"

        print(f"\n中文 PDF: {pdf_path.name} ({pdf_path.stat().st_size} 字节)")

    def test_bilingual_epub(self):
        """验证双语 EPUB：检查 output/little-prince/双语-little-prince/ 下是否有 .epub"""
        book_output_dir = Path(config.output_dir) / BOOK_NAME
        bilingual_dir = book_output_dir / f"双语-{BOOK_NAME}"

        epub_files = list(bilingual_dir.glob("*.epub")) if bilingual_dir.exists() else []
        assert len(epub_files) > 0, f"未找到双语 EPUB: {bilingual_dir}/*.epub"

        epub_path = epub_files[0]
        assert epub_path.stat().st_size > 1000, f"双语 EPUB 文件过小: {epub_path.stat().st_size}"

        print(f"\n双语 EPUB: {epub_path.name} ({epub_path.stat().st_size} 字节)")

    def test_english_pdf(self):
        """验证英文 PDF：检查 output/little-prince/英文-little-prince/ 下是否有 PDF"""
        book_output_dir = Path(config.output_dir) / BOOK_NAME
        english_dir = book_output_dir / f"英文-{BOOK_NAME}"

        pdf_files = list(english_dir.glob("*.pdf")) if english_dir.exists() else []
        assert len(pdf_files) > 0, f"未找到英文 PDF: {english_dir}/*.pdf"

        pdf_path = pdf_files[0]
        assert pdf_path.stat().st_size > 1000, f"英文 PDF 文件过小: {pdf_path.stat().st_size}"

        print(f"\n英文 PDF: {pdf_path.name} ({pdf_path.stat().st_size} 字节)")

    def test_summary_pdf(self):
        """验证精简版 PDF：检查 output/little-prince/ 下是否有 精简版.pdf"""
        book_output_dir = Path(config.output_dir) / BOOK_NAME
        summary_pdf = book_output_dir / "精简版.pdf"

        assert summary_pdf.exists(), f"未找到精简版 PDF: {summary_pdf}"
        assert summary_pdf.stat().st_size > 1000, f"精简版 PDF 文件过小: {summary_pdf.stat().st_size}"

        print(f"\n精简版 PDF: {summary_pdf.name} ({summary_pdf.stat().st_size} 字节)")
