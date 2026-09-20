"""测试配置 - 使用内存数据库"""

import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from automation.database import get_session
from automation.models import Base, Book

# 确保 ebook_translator 在 sys.path 中（translation_cache.py 依赖 translator 模块）
_ebook_translator_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ebook_translator")
if _ebook_translator_path not in sys.path:
    sys.path.insert(0, _ebook_translator_path)


@pytest.fixture(autouse=True)
def reset_db_engine():
    """每个测试前重置 DatabaseManager 全局缓存，使用独立内存数据库"""
    import automation.database as db_module

    url = "sqlite:///:memory:"
    db_module._db_engine = create_engine(url, echo=False)
    db_module._SessionLocal = sessionmaker(bind=db_module._db_engine)
    Base.metadata.create_all(db_module._db_engine)


@pytest.fixture
def in_memory_db(reset_db_engine):
    """使用 reset_db_engine 设置的全局 engine 的 session

    这样 DatabaseManager 的所有操作和测试查询都使用同一个 engine/session。
    """
    session = get_session()
    yield session
    # 不在这里关闭 session，因为 DatabaseManager 方法内部会关闭自己的 session，
    # 而且多个测试共用 reset_db_engine 的全局 engine。
    # 重复 close() 在 SQLAlchemy 中是安全的。


@pytest.fixture
def sample_book(in_memory_db):
    """创建测试用书籍记录"""
    book = Book(id="test-book-001", filename="test.epub", title="测试书籍", author="测试作者", status="pending")
    in_memory_db.add(book)
    in_memory_db.commit()
    return book
