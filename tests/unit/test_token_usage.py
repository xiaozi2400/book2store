"""测试 TokenUsage 模型和 DatabaseManager Token 统计方法"""

from datetime import datetime

import pytest


class TestTokenUsageModel:
    """测试 TokenUsage 模型"""

    def test_create_token_usage_record(self, in_memory_db):
        """创建 TokenUsage 记录并验证字段"""
        from automation.models import TokenUsage

        record = TokenUsage(
            book_id="test-book-001",
            step="translation",
            model="deepseek-chat",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            cost=0.002,
        )
        in_memory_db.add(record)
        in_memory_db.commit()

        saved = in_memory_db.query(TokenUsage).first()
        assert saved is not None
        assert saved.book_id == "test-book-001"
        assert saved.step == "translation"
        assert saved.model == "deepseek-chat"
        assert saved.input_tokens == 1000
        assert saved.output_tokens == 500
        assert saved.total_tokens == 1500
        assert saved.cost == 0.002
        assert isinstance(saved.created_at, datetime)

    def test_token_usage_defaults(self, in_memory_db):
        """测试 TokenUsage 默认值"""
        from automation.models import TokenUsage

        record = TokenUsage(book_id="test-book-002", step="summary")
        in_memory_db.add(record)
        in_memory_db.commit()

        saved = in_memory_db.query(TokenUsage).filter_by(book_id="test-book-002").first()
        assert saved.model == "deepseek-chat"
        assert saved.input_tokens == 0
        assert saved.output_tokens == 0
        assert saved.total_tokens == 0
        assert saved.cost == 0.0

    def test_token_usage_book_relationship(self, in_memory_db, sample_book):
        """测试 TokenUsage 与 Book 的关系"""
        from automation.models import TokenUsage

        record = TokenUsage(book_id=sample_book.id, step="xianyu", input_tokens=100, output_tokens=50)
        in_memory_db.add(record)
        in_memory_db.commit()

        assert record.book.id == sample_book.id
        assert record.book.title == "测试书籍"
        assert record in sample_book.token_usages

    def test_multiple_steps_for_same_book(self, in_memory_db, sample_book):
        """测试同一本书的多条 Token 记录"""
        from automation.models import TokenUsage

        steps = ["translation", "summary", "xianyu", "xiaohongshu"]
        for i, step in enumerate(steps):
            record = TokenUsage(
                book_id=sample_book.id, step=step, input_tokens=100 * (i + 1), output_tokens=50 * (i + 1)
            )
            in_memory_db.add(record)
        in_memory_db.commit()

        records = in_memory_db.query(TokenUsage).filter_by(book_id=sample_book.id).all()
        assert len(records) == 4
        assert [r.step for r in records] == steps


class TestDatabaseManagerTokenMethods:
    """测试 DatabaseManager 的 Token 统计方法"""

    def test_record_token_usage(self, monkeypatch):
        """测试 record_token_usage 写入数据库"""
        from automation.database import DatabaseManager

        monkeypatch.setattr("automation.database.get_database_url", lambda: "sqlite:///:memory:")

        db = DatabaseManager()
        db.record_token_usage(book_id="test-book-001", step="translation", input_tokens=1000, output_tokens=500)

        records = db.get_token_usage("test-book-001")
        assert len(records) == 1
        assert records[0].step == "translation"
        assert records[0].input_tokens == 1000
        assert records[0].output_tokens == 500
        assert records[0].total_tokens == 1500
        assert records[0].cost > 0

    def test_get_token_usage_all(self, monkeypatch):
        """测试 get_token_usage 无 book_id 返回全部"""
        from automation.database import DatabaseManager

        monkeypatch.setattr("automation.database.get_database_url", lambda: "sqlite:///:memory:")

        db = DatabaseManager()
        db.record_token_usage(book_id="book-1", step="translation", input_tokens=100, output_tokens=50)
        db.record_token_usage(book_id="book-2", step="summary", input_tokens=200, output_tokens=100)

        all_records = db.get_token_usage()
        assert len(all_records) == 2

    def test_get_token_summary(self, monkeypatch):
        """测试 get_token_summary 汇总"""
        from automation.database import DatabaseManager

        monkeypatch.setattr("automation.database.get_database_url", lambda: "sqlite:///:memory:")

        db = DatabaseManager()
        db.record_token_usage(book_id="test-book-001", step="translation", input_tokens=1000, output_tokens=500)
        db.record_token_usage(book_id="test-book-001", step="summary", input_tokens=200, output_tokens=100)
        db.record_token_usage(book_id="test-book-001", step="xianyu", input_tokens=50, output_tokens=25)
        db.record_token_usage(book_id="test-book-001", step="xiaohongshu", input_tokens=80, output_tokens=40)

        summary = db.get_token_summary("test-book-001")
        assert summary is not None
        assert "translation" in summary
        assert "summary" in summary
        assert "xianyu" in summary
        assert "xiaohongshu" in summary
        assert summary["translation"]["input_tokens"] == 1000
        assert summary["translation"]["output_tokens"] == 500
        assert summary["translation"]["total_tokens"] == 1500

        total_input = sum(s["input_tokens"] for s in summary.values())
        total_output = sum(s["output_tokens"] for s in summary.values())
        assert total_input == 1330
        assert total_output == 665

    def test_get_token_summary_no_records(self, monkeypatch):
        """测试无记录时返回 None"""
        from automation.database import DatabaseManager

        monkeypatch.setattr("automation.database.get_database_url", lambda: "sqlite:///:memory:")

        db = DatabaseManager()
        result = db.get_token_summary("non-existent")
        assert result is None

    def test_cost_calculation(self, monkeypatch):
        """测试费用计算是否正确 (DeepSeek 定价: ¥1/百万输入, ¥2/百万输出)"""
        from automation.database import DatabaseManager

        monkeypatch.setattr("automation.database.get_database_url", lambda: "sqlite:///:memory:")

        db = DatabaseManager()
        db.record_token_usage(book_id="test-cost", step="translation", input_tokens=1_000_000, output_tokens=500_000)

        records = db.get_token_usage("test-cost")
        assert len(records) == 1
        # 输入 = ¥1, 输出 = 0.5 * ¥2 = ¥1, 总计 = ¥2
        assert records[0].cost == pytest.approx(2.0, rel=1e-3)
