import os
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import re

def normalize_text(text):
    """标准化文本：去除多余空格，保留换行"""
    if not text:
        return ""
    # 替换多个连续空格为单个空格
    text = ' '.join(text.split())
    return text.strip()

class EPUBParser:
    """EPUB 解析器"""
    
    def __init__(self, epub_path):
        """初始化解析器"""
        self.epub_path = epub_path
        self.book = None
        self.content_items = []
        # 添加 path 属性，以便 EPUBGenerator 可以访问原始 EPUB 文件的路径
        self.path = epub_path
    
    def parse(self):
        """解析 EPUB 文件"""
        try:
            self.book = epub.read_epub(self.epub_path)
            self._extract_content_items()
            return True
        except Exception as e:
            print(f"解析 EPUB 文件时出错: {e}")
            return False
    
    def _extract_content_items(self):
        """提取 EPUB 中的内容项"""
        for item in self.book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                self.content_items.append(item)
    
    def get_paragraphs(self, item):
        """从内容项中提取段落"""
        try:
            content = item.get_content().decode('utf-8', errors='ignore')
            soup = BeautifulSoup(content, 'lxml')
            paragraphs = []
            extracted_texts = set()
            
            # 只提取优先级标签，避免嵌套重复
            priority_tags = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'div', 'dt', 'dd']
            
            for tag_name in priority_tags:
                for tag in soup.find_all(tag_name):
                    text = tag.get_text(strip=True)
                    text = normalize_text(text)
                    # 过滤掉太短的文本
                    if text and len(text) > 1 and text not in extracted_texts:
                        extracted_texts.add(text)
                        paragraphs.append({
                            'text': text,
                            'html': str(tag),
                            'tag': tag_name,
                            'normalized_text': text
                        })
            
            return paragraphs
        except Exception as e:
            print(f"提取段落时出错: {e}")
            return []
    
    def get_content_items(self):
        """获取所有内容项"""
        return self.content_items
    
    def get_book(self):
        """获取解析后的书籍对象"""
        return self.book
