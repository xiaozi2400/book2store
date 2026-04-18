"""
数据库模型定义
"""
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Book(Base):
    """书籍基础信息表"""
    __tablename__ = "books"

    id = Column(String, primary_key=True, default=generate_uuid)
    filename = Column(String, nullable=False, index=True)
    title = Column(String)
    author = Column(String)
    isbn = Column(String)
    language = Column(String)
    page_count = Column(Integer)
    file_size = Column(Integer)
    status = Column(String, default="pending", index=True)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    outputs = relationship("BookOutput", back_populates="book", uselist=False)
    logs = relationship("ProcessingLog", back_populates="book")

    def __repr__(self):
        return f"<Book(id={self.id}, title={self.title}, status={self.status})>"


class BookOutput(Base):
    """书籍输出文件表"""
    __tablename__ = "book_outputs"

    id = Column(String, primary_key=True, default=generate_uuid)
    book_id = Column(String, ForeignKey("books.id"), index=True)

    bilingual_epub = Column(String)
    chinese_epub = Column(String)
    bilingual_pdf = Column(String)
    chinese_pdf = Column(String)
    english_pdf = Column(String)
    summary_pdf = Column(String)

    cover_image = Column(String)
    toc_preview_image = Column(String)
    other_images = Column(JSON)

    xianyu_title = Column(String)
    xianyu_description = Column(Text)
    xianyu_tags = Column(String)
    xiaohongshu_note = Column(Text)

    pan_link_sku1 = Column(String)
    pan_link_sku2 = Column(String)
    pan_code = Column(String)

    xianyu_product_id = Column(String)
    xianyu_listing_url = Column(String)
    publish_status = Column(String, default="pending")
    publish_error = Column(Text)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    book = relationship("Book", back_populates="outputs")

    def __repr__(self):
        return f"<BookOutput(id={self.id}, book_id={self.book_id})>"


class ProcessingLog(Base):
    """处理日志表"""
    __tablename__ = "processing_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    book_id = Column(String, ForeignKey("books.id"), index=True)
    stage = Column(String, nullable=False)
    status = Column(String, nullable=False)
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    book = relationship("Book", back_populates="logs")

    def __repr__(self):
        return f"<ProcessingLog(id={self.id}, book_id={self.book_id}, stage={self.stage})>"


class SystemConfig(Base):
    """系统配置表"""
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, unique=True, nullable=False, index=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<SystemConfig(key={self.key})>"


class ShareLink(Base):
    """网盘分享链接表"""
    __tablename__ = "share_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    book_id = Column(String, ForeignKey("books.id"), index=True)
    filename = Column(String, nullable=False)
    share_url = Column(String, nullable=False)
    extract_code = Column(String)
    matched = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<ShareLink(id={self.id}, filename={self.filename})>"
