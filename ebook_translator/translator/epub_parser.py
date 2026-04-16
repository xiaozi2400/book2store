import os
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

class EPUBParser:
    """EPUB 解析器"""
    
    def __init__(self, epub_path):
        """初始化解析器"""
        self.epub_path = epub_path
        self.book = None
        self.content_items = []
    
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
            
            # 查找所有段落
            for p in soup.find_all('p'):
                text = p.get_text(strip=True)
                if text:
                    paragraphs.append({
                        'text': text,
                        'html': str(p)
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
