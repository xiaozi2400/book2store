"""
数据库连接管理
"""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .models import Base

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
        _db_engine = create_engine(
            database_url,
            echo=False,
            connect_args={"check_same_thread": False}
        )
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_db_engine)

    Base.metadata.create_all(bind=_db_engine)
    return _db_engine


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

    def create_book(self, filename: str, title: str = None, author: str = None) -> 'Book':
        """创建书籍记录"""
        from .models import Book

        session = get_session()
        try:
            book = Book(
                filename=filename,
                title=title or filename,
                author=author,
                status="pending"
            )
            session.add(book)
            session.commit()
            session.refresh(book)
            return book
        finally:
            close_session(session)

    def get_book_by_filename(self, filename: str) -> 'Book':
        """根据文件名获取书籍"""
        from .models import Book

        session = get_session()
        try:
            return session.query(Book).filter(Book.filename == filename).first()
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

    def create_book_output(self, book_id: str) -> 'BookOutput':
        """创建书籍输出记录"""
        from .models import BookOutput

        session = get_session()
        try:
            output = BookOutput(book_id=book_id)
            session.add(output)
            session.commit()
            session.refresh(output)
            return output
        finally:
            close_session(session)

    def get_book_output(self, book_id: str) -> 'BookOutput':
        """获取书籍输出记录"""
        from .models import BookOutput

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
            output = session.query(BookOutput).filter(BookOutput.book_id == book_id).first()
            if output:
                for key, value in kwargs.items():
                    if hasattr(output, key):
                        setattr(output, key, value)
                session.commit()
        finally:
            close_session(session)

    def add_log(self, book_id: str, stage: str, status: str, message: str = None):
        """添加处理日志"""
        from .models import ProcessingLog

        session = get_session()
        try:
            log = ProcessingLog(
                book_id=book_id,
                stage=stage,
                status=status,
                message=message
            )
            session.add(log)
            session.commit()
        finally:
            close_session(session)

    def get_logs(self, book_id: str) -> list:
        """获取书籍的处理日志"""
        from .models import ProcessingLog

        session = get_session()
        try:
            return session.query(ProcessingLog).filter(
                ProcessingLog.book_id == book_id
            ).order_by(ProcessingLog.created_at).all()
        finally:
            close_session(session)

    def get_stats(self) -> dict:
        """获取统计信息"""
        from .models import Book

        session = get_session()
        try:
            total = session.query(Book).count()
            pending = session.query(Book).filter(Book.status == "pending").count()
            processing = session.query(Book).filter(Book.status.in_(["scanning", "parsing", "translating", "summarizing", "extracting", "copywriting"])).count()
            completed = session.query(Book).filter(Book.status == "completed").count()
            published = session.query(Book).filter(Book.status == "published").count()
            failed = session.query(Book).filter(Book.status == "failed").count()

            return {
                "total": total,
                "pending": pending,
                "processing": processing,
                "completed": completed,
                "published": published,
                "failed": failed
            }
        finally:
            close_session(session)
