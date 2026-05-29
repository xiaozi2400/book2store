"""测试配置 - 使用内存数据库"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from automation.models import Base, Book


@pytest.fixture(autouse=True)
def reset_db_engine():
    """每个测试前重置 DatabaseManager 全局缓存，使用独立内存数据库"""
    import automation.database as db_module
    url = "sqlite:///:memory:"
    db_module._db_engine = create_engine(url, echo=False)
    db_module._SessionLocal = sessionmaker(bind=db_module._db_engine)
    Base.metadata.create_all(db_module._db_engine)


@pytest.fixture
def in_memory_db():
    """创建内存数据库引擎和会话"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_book(in_memory_db):
    """创建测试用书籍记录"""
    book = Book(
        id="test-book-001",
        filename="test.epub",
        title="测试书籍",
        author="测试作者",
        status="pending"
    )
    in_memory_db.add(book)
    in_memory_db.commit()
    return book
