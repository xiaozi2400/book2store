"""
数据库连接管理
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, Book, BookOutput

logger = logging.getLogger(__name__)

# DeepSeek 定价（元/百万token）
INPUT_PRICE_PER_MILLION = 1.0
OUTPUT_PRICE_PER_MILLION = 2.0

_db_engine = None
_SessionLocal = None


def get_data_dir() -> Path:
    """获取数据目录"""
    data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)
    return data_dir


def get_database_url() -> str:
    """获取数据库连接URL"""
    db_path = get_data_dir() / "books.db"
    return f"sqlite:///{db_path}"


def init_database():
    """初始化数据库"""
    global _db_engine, _SessionLocal

    if _db_engine is None:
        database_url = get_database_url()
        _db_engine = create_engine(database_url, echo=False, connect_args={"check_same_thread": False})
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_db_engine)

    Base.metadata.create_all(bind=_db_engine)
    _migrate_database(_db_engine)
    return _db_engine


def _migrate_database(engine):
    """数据库迁移：新增字段等"""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("books")]
    if "summary_text" not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE books ADD COLUMN summary_text TEXT"))
            conn.commit()

    output_columns = [col["name"] for col in inspector.get_columns("book_outputs")]
    if "main_image_count" not in output_columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE book_outputs ADD COLUMN main_image_count INTEGER DEFAULT 0"))
            conn.commit()

    # quality_report 字段迁移
    output_columns2 = [col["name"] for col in inspector.get_columns("book_outputs")]
    if "quality_report" not in output_columns2:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE book_outputs ADD COLUMN quality_report TEXT"))
            conn.commit()


def get_session() -> Session:
    """获取数据库会话"""
    if _SessionLocal is None:
        init_database()
    return _SessionLocal()


def close_session(session: Session):
    """关闭数据库会话"""
    if session:
        session.close()


class DatabaseManager:
    """数据库管理器"""

    def __init__(self):
        init_database()

    def create_book(self, filename: str, title: str = None, author: str = None) -> Book:
        """创建书籍记录"""
        session = get_session()
        try:
            book = Book(filename=filename, title=title or filename, author=author, status="pending")
            session.add(book)
            session.commit()
            session.refresh(book)
            return book
        finally:
            close_session(session)

    def get_book_by_filename(self, filename: str) -> Book:
        """根据文件名获取书籍"""
        session = get_session()
        try:
            return session.query(Book).filter(Book.filename == filename).first()
        finally:
            close_session(session)

    def get_book_by_id(self, book_id: str) -> Book:
        """根据ID获取书籍"""
        session = get_session()
        try:
            return session.query(Book).filter(Book.id == book_id).first()
        finally:
            close_session(session)

    def get_all_books(self, status: str = None) -> list:
        """获取所有书籍"""
        from .models import Book

        session = get_session()
        try:
            query = session.query(Book)
            if status:
                query = query.filter(Book.status == status)
            return query.order_by(Book.created_at.desc()).all()
        finally:
            close_session(session)

    def update_book_status(self, book_id: str, status: str, error_message: str = None):
        """更新书籍状态"""
        from .models import Book

        session = get_session()
        try:
            book = session.query(Book).filter(Book.id == book_id).first()
            if book:
                book.status = status
                if error_message:
                    book.error_message = error_message
                session.commit()
        finally:
            close_session(session)

    def update_book_summary(self, book_id: str, summary_text: str) -> Book:
        """更新书籍摘要文本并返回 Book 对象"""
        session = get_session()
        try:
            book = session.query(Book).filter(Book.id == book_id).first()
            if book:
                book.summary_text = summary_text
                session.commit()
                session.refresh(book)
            return book
        finally:
            close_session(session)

    def create_book_output(self, book_id: str) -> BookOutput:
        """创建书籍输出记录"""
        session = get_session()
        try:
            output = BookOutput(book_id=book_id)
            session.add(output)
            session.commit()
            session.refresh(output)
            return output
        finally:
            close_session(session)

    def get_book_output(self, book_id: str) -> BookOutput:
        """获取书籍输出记录"""
        session = get_session()
        try:
            return session.query(BookOutput).filter(BookOutput.book_id == book_id).first()
        finally:
            close_session(session)

    def update_book_output(self, book_id: str, **kwargs):
        """更新书籍输出"""
        from .models import BookOutput

        session = get_session()
        try:
            output = (
                session.query(BookOutput)
                .filter((BookOutput.book_id == book_id) | (BookOutput.book_id.startswith(book_id)))
                .first()
            )

            if not output:
                # 自动创建记录
                output = BookOutput(book_id=book_id)
                session.add(output)
                session.commit()
                session.refresh(output)

            for key, value in kwargs.items():
                if hasattr(output, key):
                    setattr(output, key, value)
            session.commit()
        finally:
            close_session(session)

    def update_book_quality_report(self, book_id: str, report_json: str):
        """更新书籍的质量检查报告"""
        from .models import BookOutput

        session = get_session()
        try:
            output = session.query(BookOutput).filter(BookOutput.book_id == book_id).first()
            if output:
                output.quality_report = report_json
                session.commit()
                logger.info(f"质量报告已更新到数据库: {book_id}")
        except Exception as e:
            logger.error(f"更新质量报告失败: {e}")
            session.rollback()
        finally:
            close_session(session)

    def get_book_quality_report(self, book_id: str) -> str | None:
        """获取书籍的质量检查报告（JSON 字符串）"""
        from .models import BookOutput

        session = get_session()
        try:
            output = session.query(BookOutput).filter(BookOutput.book_id == book_id).first()
            if output:
                return output.quality_report
            return None
        except Exception as e:
            logger.error(f"获取质量报告失败: {e}")
            return None
        finally:
            close_session(session)

    def add_log(self, book_id: str, stage: str, status: str, message: str = None):
        """添加处理日志"""
        from .models import ProcessingLog

        session = get_session()
        try:
            log = ProcessingLog(book_id=book_id, stage=stage, status=status, message=message)
            session.add(log)
            session.commit()
        finally:
            close_session(session)

    def get_logs(self, book_id: str) -> list:
        """获取书籍的处理日志"""
        from .models import ProcessingLog

        session = get_session()
        try:
            return (
                session.query(ProcessingLog)
                .filter(ProcessingLog.book_id == book_id)
                .order_by(ProcessingLog.created_at)
                .all()
            )
        finally:
            close_session(session)

    def get_stats(self) -> dict:
        """获取统计信息"""
        from .models import Book

        session = get_session()
        try:
            total = session.query(Book).count()
            pending = session.query(Book).filter(Book.status == "pending").count()
            processing = (
                session.query(Book)
                .filter(
                    Book.status.in_(["scanning", "parsing", "translating", "summarizing", "extracting", "copywriting"])
                )
                .count()
            )
            completed = session.query(Book).filter(Book.status == "completed").count()
            published = session.query(Book).filter(Book.status == "published").count()
            failed = session.query(Book).filter(Book.status == "failed").count()

            return {
                "total": total,
                "pending": pending,
                "processing": processing,
                "completed": completed,
                "published": published,
                "failed": failed,
            }
        finally:
            close_session(session)

    def record_token_usage(self, book_id, step, input_tokens, output_tokens, model="deepseek-chat"):
        """记录Token消耗"""
        from .models import TokenUsage

        total_tokens = input_tokens + output_tokens
        cost = input_tokens / 1_000_000 * INPUT_PRICE_PER_MILLION + output_tokens / 1_000_000 * OUTPUT_PRICE_PER_MILLION
        session = get_session()
        try:
            record = TokenUsage(
                book_id=book_id,
                step=step,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost=round(cost, 6),
            )
            session.add(record)
            session.commit()
            logger.info(
                f"TokenUsage - book_id={book_id} step={step} "
                f"input={input_tokens} output={output_tokens} "
                f"total={total_tokens} cost=¥{cost:.4f}"
            )
            return record
        finally:
            close_session(session)

    def get_token_usage(self, book_id=None):
        """查询Token消耗记录"""
        from .models import TokenUsage

        session = get_session()
        try:
            query = session.query(TokenUsage)
            if book_id:
                query = query.filter(TokenUsage.book_id == book_id)
            return query.order_by(TokenUsage.created_at).all()
        finally:
            close_session(session)

    def get_token_summary(self, book_id):
        """获取指定书籍的Token消耗汇总"""
        records = self.get_token_usage(book_id)
        if not records:
            return None

        steps = {}
        for r in records:
            step = r.step
            if step not in steps:
                steps[step] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost": 0.0}
            steps[step]["input_tokens"] += r.input_tokens
            steps[step]["output_tokens"] += r.output_tokens
            steps[step]["total_tokens"] += r.total_tokens
            steps[step]["cost"] += r.cost

        return steps

    def get_books_by_publish_status(self, status: str) -> list:
        """获取指定发布状态的书籍（join BookOutput）

        返回 Book 对象列表，按 updated_at DESC 排序（最近失败/成功的在前）
        """
        from .models import Book, BookOutput

        session = get_session()
        try:
            return (
                session.query(Book)
                .join(BookOutput, Book.id == BookOutput.book_id)
                .filter(BookOutput.publish_status == status)
                .order_by(Book.updated_at.desc())
                .all()
            )
        finally:
            close_session(session)

    def backfill_failed_publish_status(self) -> int:
        """回填历史发布失败状态

        把 processing_logs 里 publishing 阶段失败、但 publish_status 仍为
        pending 的书标记为 failed。幂等：重复运行返回 0。
        """
        from .models import BookOutput, ProcessingLog

        session = get_session()
        try:
            failed_book_ids_subq = (
                session.query(ProcessingLog.book_id)
                .filter(
                    ProcessingLog.stage == "publishing",
                    ProcessingLog.status == "error",
                )
                .distinct()
                .subquery()
            )

            targets = (
                session.query(BookOutput)
                .join(failed_book_ids_subq, BookOutput.book_id == failed_book_ids_subq.c.book_id)
                .filter(BookOutput.publish_status.in_(["pending", None]))
                .all()
            )

            for output in targets:
                last_err = (
                    session.query(ProcessingLog)
                    .filter(
                        ProcessingLog.book_id == output.book_id,
                        ProcessingLog.stage == "publishing",
                        ProcessingLog.status == "error",
                    )
                    .order_by(ProcessingLog.created_at.desc())
                    .first()
                )

                output.publish_status = "failed"
                if last_err:
                    output.publish_error = (last_err.message or "")[:1000]
                # Book.status 保持不变（历史状态不动，避免误判）

            session.commit()
            return len(targets)
        finally:
            close_session(session)

    def count_unbackfilled_failed(self) -> int:
        """统计未回填的失败书数量（用于启动时提示）"""
        from .models import BookOutput, ProcessingLog

        session = get_session()
        try:
            failed_book_ids_subq = (
                session.query(ProcessingLog.book_id)
                .filter(
                    ProcessingLog.stage == "publishing",
                    ProcessingLog.status == "error",
                )
                .distinct()
                .subquery()
            )

            return (
                session.query(BookOutput)
                .join(failed_book_ids_subq, BookOutput.book_id == failed_book_ids_subq.c.book_id)
                .filter(BookOutput.publish_status.in_(["pending", None]))
                .count()
            )
        finally:
            close_session(session)
