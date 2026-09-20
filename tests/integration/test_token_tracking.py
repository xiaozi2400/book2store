"""测试 TokenUsage 记录 - 验证各阶段运行后数据库中的 Token 消耗记录"""

import pytest

from automation.database import DatabaseManager
from automation.models import Book, TokenUsage


class TestTokenTracking:
    """测试 Token 消耗追踪"""

    @pytest.fixture
    def book(self, in_memory_db):
        """创建测试书籍"""
        book = Book(
            id="test-token-book-001",
            filename="test-token.epub",
            title="Token测试书籍",
            author="测试作者",
            status="pending",
            summary_text="这是测试 Token 追踪的书籍摘要。",
        )
        in_memory_db.add(book)
        in_memory_db.commit()
        return book

    def test_record_token_usage_creates_record(self, book, in_memory_db):
        """验证 record_token_usage 创建记录"""
        book_id = book.id

        db = DatabaseManager()
        db.create_book_output(book_id)

        db.record_token_usage(
            book_id=book_id,
            step="translation",
            input_tokens=1000,
            output_tokens=500,
        )

        # 查询 TokenUsage 记录
        records = in_memory_db.query(TokenUsage).filter(TokenUsage.book_id == book_id).all()

        assert len(records) == 1, f"期望 1 条 TokenUsage 记录，实际 {len(records)}"

        record = records[0]
        assert record.step == "translation"
        assert record.input_tokens == 1000
        assert record.output_tokens == 500
        assert record.total_tokens == 1500

    def test_record_token_usage_calculates_cost(self, book, in_memory_db):
        """验证 Token 费用计算"""
        book_id = book.id

        db = DatabaseManager()
        db.create_book_output(book_id)

        db.record_token_usage(
            book_id=book_id,
            step="translation",
            input_tokens=1_000_000,  # 100万输入
            output_tokens=500_000,  # 50万输出
        )

        record = in_memory_db.query(TokenUsage).filter(TokenUsage.book_id == book_id).first()

        # 输入: 1元/百万, 输出: 2元/百万
        # 1_000_000 * 1 / 1_000_000 = 1.0
        # 500_000 * 2 / 1_000_000 = 1.0
        # 总计: 2.0
        assert record.cost == 2.0, f"期望费用 2.0，实际 {record.cost}"

    def test_multiple_stages_recorded_separately(self, book, in_memory_db):
        """验证多个阶段分别记录"""
        book_id = book.id

        db = DatabaseManager()
        db.create_book_output(book_id)

        steps = [
            ("translation", 1000, 500),
            ("summarizing", 200, 100),
            ("copywriting_xianyu", 300, 150),
            ("copywriting_xiaohongshu", 250, 120),
        ]

        for step, input_t, output_t in steps:
            db.record_token_usage(
                book_id=book_id,
                step=step,
                input_tokens=input_t,
                output_tokens=output_t,
            )

        # 查询所有记录
        records = in_memory_db.query(TokenUsage).filter(TokenUsage.book_id == book_id).all()

        assert len(records) == len(steps), f"期望 {len(steps)} 条记录，实际 {len(records)}"

        # 验证各阶段记录存在
        for step, expected_input, expected_output in steps:
            record = (
                in_memory_db.query(TokenUsage)
                .filter(
                    TokenUsage.book_id == book_id,
                    TokenUsage.step == step,
                )
                .first()
            )
            assert record is not None, f"缺少 {step} 记录"
            assert record.input_tokens == expected_input
            assert record.output_tokens == expected_output

    def test_token_usage_positive_integers(self, book, in_memory_db):
        """验证 Token 数量为正整数"""
        book_id = book.id

        db = DatabaseManager()
        db.create_book_output(book_id)

        db.record_token_usage(
            book_id=book_id,
            step="translation",
            input_tokens=100,
            output_tokens=50,
        )

        record = in_memory_db.query(TokenUsage).filter(TokenUsage.book_id == book_id).first()

        assert record.input_tokens > 0, "输入 token 应为正数"
        assert record.output_tokens > 0, "输出 token 应为正数"
        assert record.total_tokens > 0, "总 token 应为正数"
        assert isinstance(record.input_tokens, int), "输入 token 应为整数"
        assert isinstance(record.output_tokens, int), "输出 token 应为整数"
        assert isinstance(record.total_tokens, int), "总 token 应为整数"

    def test_get_token_summary_aggregates_correctly(self, book, in_memory_db):
        """验证 get_token_summary 正确聚合"""
        book_id = book.id

        db = DatabaseManager()
        db.create_book_output(book_id)

        # 记录多条同一阶段的 Token
        db.record_token_usage(book_id=book_id, step="translation", input_tokens=1000, output_tokens=500)
        db.record_token_usage(book_id=book_id, step="translation", input_tokens=2000, output_tokens=1000)

        summary = db.get_token_summary(book_id)

        assert summary is not None, "应该有 token summary"
        assert "translation" in summary

        trans_summary = summary["translation"]
        assert trans_summary["input_tokens"] == 3000, f"期望 3000，实际 {trans_summary['input_tokens']}"
        assert trans_summary["output_tokens"] == 1500, f"期望 1500，实际 {trans_summary['output_tokens']}"
        assert trans_summary["total_tokens"] == 4500, f"期望 4500，实际 {trans_summary['total_tokens']}"

    def test_get_token_usage_by_book_id(self, book, in_memory_db):
        """验证按 book_id 查询 TokenUsage"""
        book_id = book.id

        # 创建另一个书籍
        other_book = Book(
            id="other-book-002",
            filename="other.epub",
            title="其他书籍",
            author="其他作者",
            status="pending",
        )
        in_memory_db.add(other_book)
        in_memory_db.commit()

        db = DatabaseManager()

        # 为两个书籍分别记录 Token
        db.record_token_usage(book_id=book_id, step="translation", input_tokens=1000, output_tokens=500)
        db.record_token_usage(book_id=other_book.id, step="translation", input_tokens=2000, output_tokens=1000)

        # 按 book_id 查询
        book_records = db.get_token_usage(book_id)
        other_records = db.get_token_usage(other_book.id)

        assert len(book_records) == 1, f"期望 1 条记录，实际 {len(book_records)}"
        assert len(other_records) == 1, f"期望 1 条记录，实际 {len(other_records)}"
        assert book_records[0].book_id == book_id
        assert other_records[0].book_id == other_book.id

    def test_token_usage_model_field(self, book, in_memory_db):
        """验证 TokenUsage 的 model 字段"""
        book_id = book.id

        db = DatabaseManager()
        db.create_book_output(book_id)

        db.record_token_usage(
            book_id=book_id,
            step="translation",
            input_tokens=100,
            output_tokens=50,
            model="deepseek-chat",
        )

        record = in_memory_db.query(TokenUsage).filter(TokenUsage.book_id == book_id).first()

        assert record.model == "deepseek-chat"

    def test_token_usage_timestamps(self, book, in_memory_db):
        """验证 TokenUsage 有时间戳"""
        book_id = book.id

        db = DatabaseManager()
        db.create_book_output(book_id)

        db.record_token_usage(
            book_id=book_id,
            step="translation",
            input_tokens=100,
            output_tokens=50,
        )

        record = in_memory_db.query(TokenUsage).filter(TokenUsage.book_id == book_id).first()

        assert record.created_at is not None, "应该有创建时间"
