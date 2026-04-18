"""
内容精简器 - 生成书籍核心内容精简版PDF
"""
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors

_font_registered = False

def _register_chinese_fonts():
    """注册中文字体"""
    global _font_registered
    if _font_registered:
        return
    
    import glob
    
    font_patterns = [
        "C:/Windows/Fonts/*.ttf",
        "C:/Windows/Fonts/*.ttc",
    ]
    
    for pattern in font_patterns:
        for font_path in glob.glob(pattern):
            try:
                font_name = os.path.splitext(os.path.basename(font_path))[0]
                if any(keyword in font_name.lower() for keyword in ['kai', 'song', 'hei', 'ming', 'ti']):
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                    _font_registered = True
                    return
            except Exception:
                continue

_font_registered = False

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .ai_client import AIClient
from .database import DatabaseManager
from .config import config
from .utils import logger, ensure_dir


class ContentSummarizer:
    """内容精简器"""

    def __init__(self):
        self.ai = AIClient()
        self.db = DatabaseManager()
        self.output_dir = Path(config.output_dir)

    def summarize(self, book_id: str, epub_path: str) -> bool:
        """生成书籍精简版"""
        logger.info(f"开始生成精简版: {book_id}")

        try:
            self.db.update_book_status(book_id, "summarizing")
            self.db.add_log(book_id, "summarizing", "start", "开始生成精简版")

            output_dir = ensure_dir(self.output_dir / book_id)
            output_path = output_dir / "核心精简.pdf"

            if output_path.exists():
                logger.info(f"精简版已存在，跳过生成: {output_path}")
                self.db.update_book_output(book_id, summary_pdf=str(output_path))
                self.db.add_log(book_id, "summarizing", "success", f"精简版已存在: {output_path}")
                return True

            book = self.db.get_book_by_filename("")
            book = self.db.get_all_books()[0] if not book else None
            if book:
                book.title = book.title or "Unknown"

            book_info = {
                'title': '书籍',
                'author': 'Unknown',
                'summary': ''
            }

            chapters = self._extract_chapters(epub_path)

            summary_content = self._generate_summary(book_info, chapters)

            self._create_pdf(summary_content, str(output_path))

            self.db.update_book_output(book_id, summary_pdf=str(output_path))

            self.db.add_log(book_id, "summarizing", "success", f"精简版生成完成: {output_path}")

            logger.info(f"精简版生成成功: {output_path}")
            return True

        except Exception as e:
            logger.error(f"生成精简版失败: {book_id}, 错误: {e}")
            self.db.update_book_status(book_id, "failed", str(e))
            self.db.add_log(book_id, "summarizing", "error", str(e))
            return False

    def _extract_chapters(self, epub_path: str) -> list:
        """提取章节内容 - 优先读取已翻译的中文内容"""
        output_dir = Path(epub_path).parent
        base_name = Path(epub_path).stem
        
        chinese_txt = output_dir / f"中文内容-{base_name}.txt"
        
        if chinese_txt.exists():
            logger.info(f"读取已翻译的中文内容: {chinese_txt}")
            return self._extract_from_translated_txt(str(chinese_txt))
        
        return self._extract_from_epub(epub_path)
    
    def _extract_from_translated_txt(self, txt_path: str) -> list:
        """从已翻译的中文txt提取章节"""
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            chapters = []
            lines = content.split("\n\n")
            
            current_chapter = {"title": "前言", "content": ""}
            for para in lines:
                para = para.strip()
                if not para:
                    continue
                
                if len(para) < 100 and (para.endswith("章") or para.endswith("节") or "第" in para):
                    if current_chapter["content"]:
                        chapters.append(current_chapter)
                    current_chapter = {"title": para, "content": ""}
                else:
                    current_chapter["content"] += para + "\n"
                    
                    if len(current_chapter["content"]) > 3000:
                        chapters.append(current_chapter)
                        current_chapter = {"title": f"第{len(chapters)+1}章", "content": ""}
            
            if current_chapter["content"]:
                chapters.append(current_chapter)
            
            logger.info(f"从翻译文本提取到 {len(chapters)} 个章节")
            return chapters[:10]
            
        except Exception as e:
            logger.warning(f"读取翻译文本失败: {e}")
            return []
    
    def _extract_from_epub(self, epub_path: str) -> list:
        """从EPUB提取章节内容"""
        import ebooklib
        from ebooklib import epub

        chapters = []
        try:
            book = epub.read_epub(epub_path)

            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(item.get_content(), 'html.parser')

                    text = soup.get_text()
                    if len(text) > 500:
                        title = self._extract_title(soup)
                        chapters.append({
                            'title': title or f"第{len(chapters)+1}章",
                            'content': text[:5000]
                        })

        except Exception as e:
            logger.warning(f"提取章节失败: {e}")

        return chapters[:10]

    def _extract_title(self, soup) -> Optional[str]:
        """提取标题"""
        for tag in soup.find_all(['h1', 'h2', 'h3', 'title']):
            text = tag.get_text().strip()
            if text and len(text) < 100:
                return text
        return None

    def _generate_summary(self, book_info: Dict, chapters: list) -> Dict[str, Any]:
        """使用AI生成摘要"""
        combined_content = "\n\n".join([
            f"{ch['title']}:\n{ch['content'][:2000]}"
            for ch in chapters[:5]
        ])

        try:
            result = self.ai.generate_summary(book_info, combined_content)

            if 'error' in result:
                logger.warning(f"AI生成失败，使用默认模板: {result.get('error')}")
                return self._get_default_summary(book_info, chapters)

            return {
                'title': book_info.get('title', 'Unknown'),
                'author': book_info.get('author', 'Unknown'),
                'core_insight': result.get('core_insight', ''),
                'chapter_summaries': result.get('chapter_summaries', []),
                'quotes': result.get('quotes', []),
                'target_audience': result.get('target_audience', '')
            }

        except Exception as e:
            logger.error(f"AI生成失败: {e}")
            return self._get_default_summary(book_info, chapters)

    def _get_default_summary(self, book_info: Dict, chapters: list) -> Dict[str, Any]:
        """获取默认摘要"""
        return {
            'title': book_info.get('title', 'Unknown'),
            'author': book_info.get('author', 'Unknown'),
            'core_insight': f"《{book_info.get('title')}》是一本有价值的书籍。",
            'chapter_summaries': [
                {'chapter': ch['title'], 'summary': ch['content'][:200]}
                for ch in chapters[:5]
            ],
            'quotes': ['本书包含丰富的知识和见解。'],
            'target_awesome': '适合对相关主题感兴趣的读者。'
        }

    def _create_pdf(self, content: Dict[str, Any], output_path: str):
        """生成PDF - 使用Calibre转换，确保中文显示正常"""
        import subprocess
        import tempfile
        import shutil
        
        try:
            base_name = content.get('title', 'book').replace('/', '_').replace('\\', '_')
            with tempfile.TemporaryDirectory() as tmpdir:
                epub_path = os.path.join(tmpdir, f"{base_name}.epub")
                
                self._create_mini_epub(content, epub_path)
                
                import json
                from pathlib import Path
                
                pdf_config_path = Path(__file__).parent.parent / "pdf_config.json"
                if pdf_config_path.exists():
                    with open(pdf_config_path, "r", encoding="utf-8") as f:
                        pdf_config = json.load(f)
                else:
                    pdf_config = {}
                
                page_cfg = pdf_config.get("page", {})
                font_cfg = pdf_config.get("font", {})
                
                cmd = [
                    "ebook-convert",
                    epub_path,
                    output_path,
                    "--paper-size", page_cfg.get("paper_size", "letter"),
                    "--margin-top", str(page_cfg.get("margin_top", 50)),
                    "--margin-bottom", str(page_cfg.get("margin_bottom", 50)),
                    "--margin-left", str(page_cfg.get("margin_left", 12)),
                    "--margin-right", str(page_cfg.get("margin_right", 12)),
                    "--pdf-default-font-size", str(font_cfg.get("default_size", 18)),
                    "--pdf-serif-family", font_cfg.get("serif", "SimSun"),
                    "--pdf-sans-family", font_cfg.get("sans", "SimSun"),
                    "--pdf-mono-family", font_cfg.get("mono", "SimSun"),
                    "--pdf-page-numbers",
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                
                if result.returncode != 0:
                    logger.warning(f"ebook-convert失败: {result.stderr}")
                    self._create_pdf_fallback(content, output_path)
        except Exception as e:
            logger.warning(f"PDF生成异常: {e}, 使用备用方法")
            self._create_pdf_fallback(content, output_path)
    
    def _create_mini_epub(self, content: Dict[str, Any], output_path: str):
        """创建精简版EPUB - 简化结构"""
        import zipfile
        
        title = content.get('title', 'Unknown')
        author = content.get('author', 'Unknown')
        
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as epub:
            epub.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
            
            html_content = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
<meta charset="utf-8"/>
<title>{title}</title>
<style>
body {{ font-family: SimSun, 'Times New Roman', serif; margin: 1em; }}
h1 {{ text-align: center; font-size: 1.5em; }}
h2 {{ margin-top: 1.5em; color: #333; }}
h3 {{ margin-top: 1em; color: #555; }}
p {{ text-indent: 2em; line-height: 1.6; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p style="text-align:center">作者: {author}</p>

<h2>核心观点</h2>
<p>{content.get('core_insight', '')}</p>

<h2>章节摘要</h2>
'''
            for ch in content.get('chapter_summaries', [])[:5]:
                html_content += f'<h3>{ch.get("chapter", "")}</h3>\n<p>{ch.get("summary", "")}</p>\n'
            
            html_content += '<h2>金句摘录</h2>\n'
            for quote in content.get('quotes', [])[:10]:
                html_content += f'<p>💡 {quote}</p>\n'
            
            target = content.get('target_audience', '')
            if target:
                html_content += f'<h2>适合谁读</h2><p>{target}</p>\n'
            
            html_content += '</body></html>'
            
            epub.writestr('OEBPS/Styles/style.css', 'body { font-family: SimSun, serif; }', compress_type=zipfile.ZIP_DEFLATED)
            epub.writestr('OEBPS/Text/content.xhtml', html_content, compress_type=zipfile.ZIP_DEFLATED)
            
            toc_content = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
<head><meta name="dtb:uid" content="book-mini-001"/></head>
<docTitle><text>{title}</text></docTitle>
<navMap>
<navPoint id="navPoint-1" playOrder="1"><navLabel><text>封面</text></navLabel><content src="Text/content.xhtml#cover"/></navPoint>
</navMap>
</ncx>
'''
            epub.writestr('OEBPS/toc.ncx', toc_content, compress_type=zipfile.ZIP_DEFLATED)
            
            container_content = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles>
<rootfile full-path="OEBPS/package.opf" media-type="application/oebps-package+xml"/>
</rootfiles>
</container>
'''
            epub.writestr('META-INF/container.xml', container_content, compress_type=zipfile.ZIP_DEFLATED)
            
            package_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="bookid">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:title>{title}</dc:title>
<dc:creator>{author}</dc:creator>
<dc:language>zh-CN</dc:language>
<dc:identifier id="bookid">book-mini-001</dc:identifier>
</metadata>
<manifest>
<item id="content" href="Text/content.xhtml" media-type="application/xhtml+xml"/>
<item id="toc" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
<item id="style" href="Styles/style.css" media-type="text/css"/>
</manifest>
<spine toc="toc">
<itemref idref="content"/>
</spine>
</package>
'''
            epub.writestr('OEBPS/package.opf', package_content, compress_type=zipfile.ZIP_DEFLATED)
    
    def _create_pdf_fallback(self, content: Dict[str, Any], output_path: str):
        """备用PDF生成方法 - 简化版"""
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50
        )
        
        styles = getSampleStyleSheet()
        story = []
        
        title = content.get('title', 'Unknown')
        author = content.get('author', 'Unknown')
        
        story.append(Paragraph(f"{title}", styles['Title']))
        story.append(Paragraph(f"作者: {author}", styles['Normal']))
        story.append(Spacer(1, 0.3 * inch))
        
        story.append(Paragraph("核心观点", styles['Heading1']))
        story.append(Paragraph(content.get('core_insight', ''), styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))
        
        if content.get('chapter_summaries'):
            story.append(Paragraph("章节摘要", styles['Heading1']))
            for ch in content.get('chapter_summaries', [])[:5]:
                story.append(Paragraph(f"<b>{ch.get('chapter', '')}</b>", styles['Heading2']))
                story.append(Paragraph(ch.get('summary', ''), styles['Normal']))
                story.append(Spacer(1, 0.1 * inch))
        
        if content.get('quotes'):
            story.append(Paragraph("金句摘录", styles['Heading1']))
            for quote in content.get('quotes', [])[:10]:
                story.append(Paragraph(f"💡 {quote}", styles['Normal']))
        
        target = content.get('target_audience', '')
        if target:
            story.append(Paragraph("适合谁读", styles['Heading1']))
            story.append(Paragraph(target, styles['Normal']))
        
        doc.build(story)


def generate_summary(book_id: str, epub_path: str) -> bool:
    """生成书籍精简版"""
    summarizer = ContentSummarizer()
    return summarizer.summarize(book_id, epub_path)


if __name__ == "__main__":
    print("内容精简器测试")
