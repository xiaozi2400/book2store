import os
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

class EPUBGenerator:
    """EPUB 生成器"""
    
    def __init__(self, original_book):
        """初始化生成器"""
        self.original_book = original_book
    
    def generate_bilingual_epub(self, translated_paragraphs, output_path):
        """生成中英对照 EPUB"""
        try:
            # 创建新的 EPUB 书籍
            book = epub.EpubBook()
            
            # 复制元数据
            if self.original_book:
                book.set_identifier(self.original_book.get_identifier())
                book.set_title(self.original_book.get_title())
                book.set_language(self.original_book.get_language())
                
                # 复制作者
                for author in self.original_book.get_authors():
                    book.add_author(author)
            
            # 处理内容项
            spine = []
            toc = []
            
            for item in self.original_book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    # 处理 HTML 内容
                    content = item.get_content().decode('utf-8', errors='ignore')
                    soup = BeautifulSoup(content, 'lxml')
                    
                    # 替换段落内容
                    paragraphs = soup.find_all('p')
                    for i, p in enumerate(paragraphs):
                        if i < len(translated_paragraphs):
                            original_text = translated_paragraphs[i]['original']
                            translated_text = translated_paragraphs[i]['translated']
                            
                            # 创建新的段落结构：原文 + 空行 + 译文
                            new_p = soup.new_tag('p')
                            new_p.string = original_text
                            
                            br = soup.new_tag('br')
                            br2 = soup.new_tag('br')
                            
                            translated_p = soup.new_tag('p')
                            translated_p.string = translated_text
                            
                            # 替换原段落
                            p.replace_with(new_p)
                            new_p.insert_after(br)
                            br.insert_after(br2)
                            br2.insert_after(translated_p)
                    
                    # 创建新的内容项
                    new_content = str(soup)
                    new_item = epub.EpubHtml(
                        title=item.get_name(),
                        file_name=item.get_name(),
                        content=new_content
                    )
                    book.add_item(new_item)
                    spine.append(new_item)
                    toc.append(new_item)
                else:
                    # 复制其他类型的内容项
                    book.add_item(item)
            
            # 设置 spine 和 toc
            book.spine = spine
            book.toc = toc
            
            # 添加导航
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())
            
            # 生成 EPUB
            epub.write_epub(output_path, book, {})
            print(f"中英对照 EPUB 生成成功: {output_path}")
            return True
        except Exception as e:
            print(f"生成中英对照 EPUB 时出错: {e}")
            return False
    
    def generate_chinese_epub(self, translated_paragraphs, output_path):
        """生成纯中文 EPUB"""
        try:
            # 创建新的 EPUB 书籍
            book = epub.EpubBook()
            
            # 复制元数据
            if self.original_book:
                book.set_identifier(self.original_book.get_identifier())
                book.set_title(self.original_book.get_title())
                book.set_language('zh')  # 设置为中文
                
                # 复制作者
                for author in self.original_book.get_authors():
                    book.add_author(author)
            
            # 处理内容项
            spine = []
            toc = []
            
            for item in self.original_book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    # 处理 HTML 内容
                    content = item.get_content().decode('utf-8', errors='ignore')
                    soup = BeautifulSoup(content, 'lxml')
                    
                    # 替换段落内容
                    paragraphs = soup.find_all('p')
                    for i, p in enumerate(paragraphs):
                        if i < len(translated_paragraphs):
                            translated_text = translated_paragraphs[i]['translated']
                            # 在段落前添加两字空格
                            new_text = "　　" + translated_text
                            p.string = new_text
                    
                    # 创建新的内容项
                    new_content = str(soup)
                    new_item = epub.EpubHtml(
                        title=item.get_name(),
                        file_name=item.get_name(),
                        content=new_content
                    )
                    book.add_item(new_item)
                    spine.append(new_item)
                    toc.append(new_item)
                else:
                    # 复制其他类型的内容项
                    book.add_item(item)
            
            # 设置 spine 和 toc
            book.spine = spine
            book.toc = toc
            
            # 添加导航
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())
            
            # 生成 EPUB
            epub.write_epub(output_path, book, {})
            print(f"纯中文 EPUB 生成成功: {output_path}")
            return True
        except Exception as e:
            print(f"生成纯中文 EPUB 时出错: {e}")
            return False
