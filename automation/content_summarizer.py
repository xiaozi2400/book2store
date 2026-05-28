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
_registered_font_name = None

def _register_chinese_fonts():
    """注册中文字体"""
    global _font_registered, _registered_font_name
    
    if _font_registered:
        return
    
    import glob
    
    font_candidates = [
        ("SimHei", "C:/Windows/Fonts/simhei.ttf"),
        ("MicrosoftYaHei", "C:/Windows/Fonts/msyh.ttc"),
        ("SimSun", "C:/Windows/Fonts/simsun.ttc"),
        ("STKaiti", "C:/Windows/Fonts/STKAITI.TTF"),
    ]
    
    for font_name, font_path in font_candidates:
        try:
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                _font_registered = True
                _registered_font_name = font_name
                return
        except Exception:
            continue
    
    font_patterns = [
        "C:/Windows/Fonts/*.ttf",
        "C:/Windows/Fonts/*.ttc",
    ]
    
    for pattern in font_patterns:
        for font_path in glob.glob(pattern):
            try:
                font_name = os.path.splitext(os.path.basename(font_path))[0]
                if any(keyword in font_name.lower() for keyword in ['kai', 'song', 'hei', 'ming', 'ti', 'yahei']):
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                    _font_registered = True
                    _registered_font_name = font_name
                    return
            except Exception:
                continue

def _get_chinese_font():
    """获取已注册的中文字体名称"""
    global _registered_font_name
    if _registered_font_name:
        return _registered_font_name
    if _font_registered:
        return "SimHei"
    return "Helvetica"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .ai_client import AIClient
from .database import DatabaseManager
from .config import config
from .utils import logger, ensure_dir
from .suitability_evaluator import SuitabilityEvaluator
from .template_generator import TemplateGenerator, detect_and_generate_prompt


class ContentSummarizer:
    """内容精简器"""

    def __init__(self):
        self.ai = AIClient()
        self.db = DatabaseManager()
        self.output_dir = Path(config.output_dir)
        self.evaluator = SuitabilityEvaluator()
        self.template_gen = TemplateGenerator()

    def _extract_cover_from_epub(self, epub_path: str) -> Optional[str]:
        """从EPUB中提取封面图片"""
        import zipfile
        import tempfile
        from xml.etree import ElementTree
        
        try:
            cover_data = None
            cover_name = None
            
            with zipfile.ZipFile(epub_path, 'r') as z:
                all_files = z.namelist()
                
                # 第一步: 查找OPF文件
                opf_path = None
                for f in all_files:
                    if f.lower().endswith('.opf'):
                        opf_path = f
                        break
                
                if opf_path:
                    # 从OPF中查找封面
                    try:
                        opf_content = z.read(opf_path)
                        root = ElementTree.fromstring(opf_content)
                        
                        # 查找元数据中的封面信息
                        ns = {'opf': 'http://www.idpf.org/2007/opf'}
                        
                        # 查找meta标签中的封面
                        for meta in root.findall('.//opf:meta', ns):
                            name = meta.get('name')
                            content = meta.get('content')
                            if name and name.lower() == 'cover':
                                cover_name = content
                                logger.info(f"从元数据找到封面: {cover_name}")
                                break
                        
                        # 构造封面在manifest中查找对应的文件
                        if cover_name:
                            # 尝试多个可能的路径
                            possible_paths = [
                                cover_name,
                                f'OEBPS/{cover_name}',
                                f'OEBPS/images/{cover_name}',
                                f'OEBPS/image/{cover_name}',
                            ]
                            for path in possible_paths:
                                if path in all_files:
                                    cover_data = z.read(path)
                                    logger.info(f"找到封面文件: {path}")
                                    break
                    except Exception as e:
                        logger.warning(f"解析OPF封面信息失败: {e}")
                
                # 如果从OPF没找到，用备用方法找最大的图片（通常是封面）
                if not cover_data:
                    logger.info("从元数据未找到封面，尝试使用最大的图片")
                    
                    # 收集所有图片，选择最大的
                    images = []
                    for f in all_files:
                        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                            try:
                                info = z.getinfo(f)
                                images.append((-info.file_size, f))
                            except Exception:
                                pass
                    
                    if images:
                        images.sort()  # 按文件大小降序排序
                        largest_size, largest_path = images[0]
                        cover_data = z.read(largest_path)
                        logger.info(f"使用最大的图片作为封面: {largest_path} ({-largest_size} 字节)")
                
                if cover_data:
                    # 保存封面到临时文件
                    ext = 'jpg'
                    if cover_name:
                        if '.' in cover_name:
                            ext = cover_name.split('.')[-1].lower()
                    
                    with tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False) as f:
                        f.write(cover_data)
                        return f.name
                    
            return None
        except Exception as e:
            logger.warning(f"提取EPUB封面失败: {e}")
            import traceback
            logger.warning(traceback.format_exc())
            return None

    def summarize(self, book_id: str, epub_path: str) -> bool:
        """生成书籍精简版"""
        logger.info(f"开始生成精简版: {book_id}")

        try:
            self.db.update_book_status(book_id, "summarizing")
            self.db.add_log(book_id, "summarizing", "start", "开始生成精简版")

            output_dir = ensure_dir(self.output_dir / Path(epub_path).stem)
            base_name = Path(epub_path).stem
            output_path = output_dir / "精简版.pdf"

            if output_path.exists():
                logger.info(f"精简版已存在，将重新生成: {output_path}")
                output_path.unlink()

            book = self.db.get_book_by_id(book_id)
            if not book:
                all_books = self.db.get_all_books()
                book = all_books[0] if all_books else None

            if book:
                book.title = book.title or "Unknown"
                book.author = book.author or "Unknown"

            book_info = {
                'title': book.title if book else '书籍',
                'author': book.author if book else 'Unknown',
                'summary': book.summary if book and hasattr(book, 'summary') else ''
            }

            chinese_title = self._extract_chinese_title(book_id, epub_path)
            if chinese_title:
                book_info['title'] = chinese_title

            if output_path.exists():
                logger.info(f"精简版已存在，将重新生成: {output_path}")
                output_path.unlink()

            suitability_result = self._check_suitability(book_info)
            self.db.add_log(book_id, "suitability", suitability_result.label, 
                          f"适合度: {suitability_result.score}分 - {suitability_result.recommendation}")

            if not suitability_result.passed:
                logger.info(f"书籍不适合生成精简版: {suitability_result.recommendation}")
                self.db.update_book_status(book_id, "skipped", suitability_result.recommendation)
                self.db.add_log(book_id, "summarizing", "skipped", 
                              f"不适合生成精简版: {suitability_result.label}")
                return False

            logger.info(f"书籍适合度评估通过: {suitability_result.label}({suitability_result.score}分)")

            chapters = self._extract_chapters(book_id, epub_path)

            summary_content = self._generate_summary(book_id, book_info, chapters, suitability_result)

            if summary_content is None:
                logger.warning("精简版生成失败，跳过PDF创建")
                self.db.add_log(book_id, "summarizing", "skipped", "AI生成失败，跳过精简版")
                return False

            # 提取封面 - 保存到输出目录，避免临时文件问题
            cover_path = None
            extracted_cover_path = self._extract_cover_from_epub(epub_path)
            if extracted_cover_path:
                # 复制到输出目录
                import shutil
                ext = os.path.splitext(extracted_cover_path)[1]
                cover_path = output_dir / f"cover{ext}"
                shutil.copy2(extracted_cover_path, cover_path)
                logger.info(f"成功提取封面并保存: {cover_path}")

                meta_dir = output_dir.parent / f"{output_dir.name}_metadata"
                os.makedirs(meta_dir, exist_ok=True)
                shutil.copy2(extracted_cover_path, meta_dir / f"cover{ext}")
                logger.info(f"封面已复制到 metadata 目录: {meta_dir / f'cover{ext}'}")
                
                # 删除临时文件
                try:
                    os.unlink(extracted_cover_path)
                except:
                    pass
            else:
                logger.warning("未能提取到封面")

            self._create_pdf(summary_content, str(output_path), str(cover_path) if cover_path else None)

            self.db.update_book_output(book_id, summary_pdf=str(output_path))

            self.db.add_log(book_id, "summarizing", "success", f"精简版生成完成: {output_path}")

            logger.info(f"精简版生成成功: {output_path}")
            return True

        except Exception as e:
            logger.error(f"生成精简版失败: {book_id}, 错误: {e}")
            self.db.update_book_status(book_id, "failed", str(e))
            self.db.add_log(book_id, "summarizing", "error", str(e))
            return False

    def _check_suitability(self, book_info: Dict[str, Any]):
        """检查书籍是否适合生成精简版"""
        return self.evaluator.evaluate(book_info)

    def _extract_chinese_title(self, book_id: str, epub_path: str = None) -> Optional[str]:
        """从中文版本EPUB中提取中文书名"""
        if epub_path:
            output_dir = Path(config.output_dir) / Path(epub_path).stem / "EPUB"
            chinese_epub_path = output_dir / f"{Path(epub_path).stem}-中文版本.epub"
        else:
            return None

        if not chinese_epub_path.exists():
            return None

        try:
            import ebooklib
            from ebooklib import epub

            book = epub.read_epub(str(chinese_epub_path))
            metadata = book.get_metadata()
            if metadata and metadata[0] and metadata[0].get('title'):
                return metadata[0]['title'][0]
        except Exception as e:
            logger.warning(f"从EPUB提取中文书名失败: {e}")

        return None

    def _extract_chapters(self, book_id: str, epub_path: str) -> list:
        """提取章节内容 - 从中文版本EPUB提取"""
        if epub_path:
            output_dir = Path(config.output_dir) / Path(epub_path).stem / "EPUB"
            chinese_epub_path = output_dir / f"{Path(epub_path).stem}-中文版本.epub"
        else:
            return []

        if chinese_epub_path.exists():
            logger.info(f"从中文EPUB提取章节: {chinese_epub_path}")
            return self._extract_from_chinese_epub(str(chinese_epub_path))

        return self._extract_from_epub(epub_path)

    def _extract_from_chinese_epub(self, epub_path: str) -> list:
        """从中文EPUB提取章节内容"""
        try:
            import ebooklib
            from ebooklib import epub
            from bs4 import BeautifulSoup

            book = epub.read_epub(epub_path)
            chapters = []
            current_chapter = {"title": "前言", "content": ""}

            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    content = item.get_content().decode('utf-8')
                    soup = BeautifulSoup(content, 'html.parser')
                    text = soup.get_text(separator='\n', strip=True)

                    if text:
                        current_chapter["content"] += text + "\n"

            if current_chapter["content"].strip():
                chapters.append(current_chapter)

            return chapters
        except Exception as e:
            logger.warning(f"从EPUB提取章节失败: {e}")
            return []
    
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

    def _generate_summary(self, book_id: str, book_info: Dict, chapters: list, suitability_result=None) -> Optional[Dict[str, Any]]:
        """使用AI生成摘要"""
        combined_content = "\n\n".join([
            f"{ch['title']}:\n{ch['content'][:5000]}"
            for ch in chapters[:8]
        ])

        logger.info(f"提取章节数量: {len(chapters)}, 总内容长度: {len(combined_content)}")

        if len(combined_content) < 100:
            logger.warning(f"章节内容过少: {combined_content}")

        book_type = self.template_gen.detect_book_type(book_info, {
            "details": suitability_result.details if suitability_result else {}
        } if suitability_result else None)

        logger.info(f"检测到书籍类型: {book_type}")

        template_result = self.template_gen.detect_and_generate_prompt(book_info, {
            "details": suitability_result.details if suitability_result else {}
        } if suitability_result else None)

        try:
            prompt = self._build_summary_prompt(book_info, combined_content, template_result.prompt_for_ai)

            prompt_len = len(prompt)
            logger.info(f"精简版生成提示词: 长度={prompt_len}, 前500字符: {prompt[:500]}")

            logger.info("开始调用AI...")
            result = self.ai.chat(prompt, max_tokens=8000)
            logger.info(f"AI调用完成, 返回长度: {len(result) if result else 0}")

            logger.info(f"精简版AI响应（前500字符）: {str(result)[:500] if result else '空'}")

            if not result or 'error' in str(result).lower():
                warn_msg = f"AI生成失败，返回结果为空或包含错误: result长度={len(result) if result else 0}，使用默认摘要"
                logger.warning(warn_msg)
                self.db.add_log(book_id, "summarizing", "warning", warn_msg)
                return self._get_default_summary(book_info, chapters)

            parsed_result = self._parse_summary_result(result)
            
            final_content = parsed_result.get('content', result)
            logger.info(f"解析后内容长度: {len(final_content) if final_content else 0}")

            return {
                'title': book_info.get('title', 'Unknown'),
                'author': book_info.get('author', 'Unknown'),
                'book_type': book_type,
                'content': final_content
            }

        except Exception as e:
            error_msg = f"精简版生成失败: {str(e)}"
            logger.error(error_msg)
            self.db.add_log(book_id, "summarizing", "failed", error_msg)
            self.db.update_book_status(book_id, "failed", error_msg)
            return None

    def _build_summary_prompt(self, book_info: Dict, content: str, template_prompt: str) -> str:
        """构建摘要生成提示词 - 替换所有占位符"""
        summarizer_cfg = config.summarizer_config()
        
        try:
            return template_prompt.format(
                title=book_info.get('title', '未知书籍'),
                author=book_info.get('author', '未知作者'),
                core_insight_length=summarizer_cfg.get('core_insight_length', '300-500'),
                chapter_summary_length=summarizer_cfg.get('chapter_summary_length', '150-200'),
                max_quotes=summarizer_cfg.get('max_quotes', 15),
                content=content
            )
        except KeyError as e:
            logger.warning(f"提示词占位符替换失败，使用默认值: {e}")
            # 如果有占位符找不到，使用简单替换
            return template_prompt.replace("{content}", content)

    def _parse_summary_result(self, result: str) -> Dict[str, Any]:
        """解析AI返回的结果"""
        try:
            import json
            import re

            stripped = result.strip()
            if stripped.startswith('#') or stripped.startswith('##') or stripped.startswith('- '):
                return {'content': result}

            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass

            return {'content': result}
        except Exception:
            return {'content': result}

    def _get_default_summary(self, book_info: Dict, chapters: list) -> Dict[str, Any]:
        """获取默认摘要 - 新格式支持 Markdown"""
        chapter_texts = "\n\n".join([
            f"## {ch['title']}\n\n{ch['content'][:500]}"
            for ch in chapters[:5]
        ])
        
        default_content = f"""## 核心观点

本书包含丰富的知识和见解，值得深入阅读。

{chapter_texts}

## 总结

本书是关于{book_info.get('title', '该主题')}的专业书籍，适合对相关领域感兴趣的读者学习参考。
"""
        
        return {
            'title': book_info.get('title', 'Unknown'),
            'author': book_info.get('author', 'Unknown'),
            'content': default_content
        }

    def _create_pdf(self, content: Dict[str, Any], output_path: str, cover_path: Optional[str] = None):
        """生成PDF - 优先使用WeasyPrint，失败则回退到Playwright"""
        try:
            self._create_pdf_weasyprint(content, output_path, cover_path)
            logger.info(f"WeasyPrint PDF生成成功: {output_path}")
        except Exception as e:
            logger.warning(f"WeasyPrint生成失败，回退到Playwright: {e}")
            try:
                self._create_pdf_playwright(content, output_path, cover_path)
                logger.info(f"Playwright PDF生成成功: {output_path}")
            except Exception as e2:
                logger.warning(f"Playwright也失败，回退到ReportLab: {e2}")
                self._create_pdf_reportlab(content, output_path, cover_path)
    
    def _create_pdf_weasyprint(self, content: Dict[str, Any], output_path: str, cover_path: Optional[str] = None):
        """使用WeasyPrint生成PDF"""
        import markdown
        import os
        import re
        try:
            msys64_path = r"C:\msys64\mingw64\bin"
            if os.path.exists(msys64_path):
                os.environ['WEASYPRINT_DLL_DIRECTORIES'] = msys64_path
            from weasyprint import HTML
        except OSError as e:
            if "libgobject" in str(e) or "cannot load library" in str(e):
                raise Exception("WeasyPrint缺少GTK3运行时库，自动跳过")
            raise

        markdown_content = content.get('content', '')

        md = markdown.Markdown(extensions=['tables', 'fenced_code', 'nl2br'])
        html_body = md.convert(markdown_content)

        title = content.get('title', '书籍精简版')
        author = content.get('author', 'Unknown')

        subtitle_match = re.search(r'<h2[^>]*>([^<]+)</h2>', html_body)
        if subtitle_match:
            subtitle = subtitle_match.group(1)
            body_html = re.sub(r'<h2[^>]*>[^<]+</h2>\s*', '', html_body, count=1)
        else:
            subtitle = None
            body_html = html_body

        full_html = self._build_weasyprint_html(title, subtitle, body_html, cover_path)

        HTML(string=full_html).write_pdf(output_path)
    
    def _build_weasyprint_html(self, title: str, subtitle: str, body_html: str, cover_path: Optional[str] = None) -> str:
        """构建WeasyPrint使用的HTML文档"""
        import base64
        
        cover_html = ''
        if cover_path and os.path.exists(cover_path):
            # 使用base64编码嵌入图片，避免路径问题
            try:
                with open(cover_path, 'rb') as f:
                    cover_data = base64.b64encode(f.read()).decode('utf-8')
                
                ext = os.path.splitext(cover_path)[1].lower()
                mime_type = {
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.bmp': 'image/bmp'
                }.get(ext, 'image/jpeg')
                
                cover_html = f'''
<div style="text-align: center; page-break-after: always;">
    <img src="data:{mime_type};base64,{cover_data}" style="max-width: 100%; max-height: 90vh; display: block; margin: auto;">
</div>'''
                logger.info(f"成功嵌入封面图片")
            except Exception as e:
                    logger.warning(f"嵌入封面失败: {e}")
                    cover_html = ''
        
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"/>
<title>{title}</title>
<style>
* {{ box-sizing: border-box; }}
body {{
    font-family: "Microsoft YaHei", "PingFang SC", "SimSun", sans-serif;
    font-size: 14px;
    line-height: 1.8;
    color: #333;
    margin: 0;
    padding: 20px;
}}
.cover-title {{
    font-size: 32px;
    font-weight: bold;
    text-align: center;
    padding-top: 150px;
    page-break-after: always;
}}
.subtitle {{
    font-size: 22px;
    font-weight: bold;
    text-align: center;
    margin: 80px 0 50px 0;
    color: #555;
    page-break-after: avoid;
}}
h2 {{
    font-size: 20px;
    font-weight: bold;
    margin: 30px 0 15px 0;
    padding: 10px 0;
    border-bottom: 2px solid #333;
    page-break-after: avoid;
}}
h3 {{
    font-size: 16px;
    font-weight: bold;
    margin: 25px 0 10px 0;
    color: #444;
    page-break-after: avoid;
}}
h4 {{
    font-size: 14px;
    font-weight: bold;
    margin: 20px 0 8px 0;
    color: #555;
}}
p {{
    margin: 0 0 15px 0;
    text-indent: 2em;
}}
ul, ol {{
    margin: 10px 0;
    padding-left: 2em;
}}
li {{
    margin: 8px 0;
}}
blockquote {{
    margin: 20px 0;
    padding: 15px 20px;
    border-left: 4px solid #666;
    background: #f8f8f8;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
    page-break-inside: avoid;
}}
th, td {{
    border: 1px solid #ddd;
    padding: 10px;
    text-align: left;
}}
th {{
    background: #f5f5f5;
}}
code {{
    font-family: Consolas, monospace;
    background: #f0f0f0;
    padding: 2px 6px;
}}
pre {{
    background: #f5f5f5;
    padding: 15px;
    page-break-inside: avoid;
    margin: 15px 0;
}}
</style>
</head>
<body>
{cover_html}
{body_html}
</body>
</html>
'''
    
    def _create_pdf_playwright(self, content: Dict[str, Any], output_path: str, cover_path: Optional[str] = None):
        """使用Playwright+Chrome生成PDF"""
        import markdown
        import re
        from playwright.sync_api import sync_playwright

        markdown_content = content.get('content', '')

        md = markdown.Markdown(extensions=['tables', 'fenced_code', 'nl2br'])
        html_body = md.convert(markdown_content)

        title = content.get('title', '书籍精简版')

        subtitle_match = re.search(r'<h2[^>]*>([^<]+)</h2>', html_body)
        if subtitle_match:
            subtitle = subtitle_match.group(1)
            body_html = re.sub(r'<h2[^>]*>[^<]+</h2>\s*', '', html_body, count=1)
        else:
            subtitle = None
            body_html = html_body

        full_html = self._build_playwright_html(title, subtitle, body_html, cover_path)

        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',
                headless=True
            )
            page = browser.new_page()
            page.set_content(full_html, wait_until='networkidle')

            page.pdf(
                path=output_path,
                format='A4',
                margin={
                    'top': '20mm',
                    'bottom': '20mm',
                    'left': '20mm',
                    'right': '20mm'
                },
                print_background=True
            )

            browser.close()
    
    def _build_playwright_html(self, title: str, subtitle: str, body_html: str, cover_path: Optional[str] = None) -> str:
        """构建Playwright使用的HTML文档"""
        import base64
        
        cover_html = ''
        if cover_path and os.path.exists(cover_path):
            # 使用base64编码嵌入图片
            try:
                with open(cover_path, 'rb') as f:
                    cover_data = base64.b64encode(f.read()).decode('utf-8')
                
                ext = os.path.splitext(cover_path)[1].lower()
                mime_type = {
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.bmp': 'image/bmp'
                }.get(ext, 'image/jpeg')
                
                cover_html = f'''
<div style="text-align: center; page-break-after: always;">
    <img src="data:{mime_type};base64,{cover_data}" style="max-width: 100%; max-height: 90vh; display: block; margin: auto;">
</div>'''
                logger.info(f"成功嵌入封面图片(Playwright)")
            except Exception as e:
                    logger.warning(f"嵌入封面失败(Playwright): {e}")
                    cover_html = ''
        
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"/>
<title>{title}</title>
<style>
* {{ box-sizing: border-box; }}
body {{
    font-family: "Microsoft YaHei", "PingFang SC", "SimSun", sans-serif;
    font-size: 14px;
    line-height: 1.8;
    color: #333;
    margin: 0;
    padding: 20px;
}}
.cover-title {{
    font-size: 32px;
    font-weight: bold;
    text-align: center;
    padding-top: 150px;
    page-break-after: always;
}}
.subtitle {{
    font-size: 22px;
    font-weight: bold;
    text-align: center;
    margin: 80px 0 50px 0;
    color: #555;
    page-break-after: avoid;
}}
h2 {{
    font-size: 20px;
    font-weight: bold;
    margin: 30px 0 15px 0;
    padding: 10px 0;
    border-bottom: 2px solid #333;
    page-break-after: avoid;
}}
h3 {{
    font-size: 16px;
    font-weight: bold;
    margin: 25px 0 10px 0;
    color: #444;
    page-break-after: avoid;
}}
h4 {{
    font-size: 14px;
    font-weight: bold;
    margin: 20px 0 8px 0;
    color: #555;
}}
p {{
    margin: 0 0 15px 0;
    text-indent: 2em;
}}
ul, ol {{
    margin: 10px 0;
    padding-left: 2em;
}}
li {{
    margin: 8px 0;
}}
blockquote {{
    margin: 20px 0;
    padding: 15px 20px;
    border-left: 4px solid #666;
    background: #f8f8f8;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
    page-break-inside: avoid;
}}
th, td {{
    border: 1px solid #ddd;
    padding: 10px;
    text-align: left;
}}
th {{
    background: #f5f5f5;
}}
code {{
    font-family: Consolas, monospace;
    background: #f0f0f0;
    padding: 2px 6px;
}}
pre {{
    background: #f5f5f5;
    padding: 15px;
    overflow-x: auto;
    page-break-inside: avoid;
    margin: 15px 0;
}}
</style>
</head>
<body>
{cover_html}
{body_html}
</body>
</html>
'''
    
    def _create_pdf_reportlab(self, content: Dict[str, Any], output_path: str, cover_path: Optional[str] = None):
        """使用reportlab直接生成PDF - 原生支持中文"""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib import colors
        import glob
        import re
        
        _register_chinese_fonts()
        
        title = content.get('title', '书籍精简版')
        author = content.get('author', 'Unknown')
        markdown_content = content.get('content', '')
        
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=2*cm,
            rightMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        styles = getSampleStyleSheet()
        
        chinese_font = _get_chinese_font()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            alignment=1,
            spaceAfter=20,
            fontName=chinese_font
        )
        author_style = ParagraphStyle(
            'Author',
            parent=styles['Normal'],
            fontSize=12,
            alignment=1,
            textColor=colors.grey,
            spaceAfter=30,
            fontName=chinese_font
        )
        h2_style = ParagraphStyle(
            'H2',
            parent=styles['Heading2'],
            fontSize=18,
            spaceBefore=20,
            spaceAfter=10,
            borderPadding=5,
            borderColor=colors.black,
            borderWidth=0,
            fontName=chinese_font
        )
        normal_style = ParagraphStyle(
            'Normal',
            parent=styles['Normal'],
            fontSize=11,
            lineHeight=1.8,
            firstLineIndent=21,
            spaceAfter=10,
            fontName=chinese_font
        )
        quote_style = ParagraphStyle(
            'Quote',
            parent=styles['Italic'],
            fontSize=11,
            leftIndent=20,
            rightIndent=20,
            spaceBefore=10,
            spaceAfter=10,
            borderPadding=10,
            borderColor=colors.grey,
            borderWidth=1,
            fontName=chinese_font
        )
        
        story = []
        
        story.append(Paragraph(title, title_style))
        story.append(Paragraph(f"作者: {author}", author_style))
        
        lines = self._parse_markdown_lines(markdown_content)
        
        for line in lines:
            if not line.strip():
                continue
            
            if line.startswith('## '):
                text = line[3:].strip()
                story.append(Paragraph(text, h2_style))
            elif line.startswith('### '):
                text = line[4:].strip()
                story.append(Paragraph(text, styles['Heading3']))
            elif line.startswith('> '):
                text = line[2:].strip()
                story.append(Paragraph(text, quote_style))
            elif line.startswith('| ') and '|' in line[1:]:
                pass
            elif line.startswith('- ') or line.startswith('* '):
                story.append(Paragraph(line, normal_style))
            elif re.match(r'^\d+\.\s', line):
                story.append(Paragraph(line, normal_style))
            elif line.startswith('---'):
                story.append(Spacer(1, 0.3*cm))
            else:
                story.append(Paragraph(line, normal_style))
        
        doc.build(story)
    
    def _parse_markdown_lines(self, markdown_content: str) -> list:
        """解析Markdown内容为行列表"""
        import re
        lines = []
        in_code_block = False
        
        for line in markdown_content.split('\n'):
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                continue
            
            if in_code_block:
                continue
            
            line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)
            line = re.sub(r'\*([^*]+)\*', r'\1', line)
            line = re.sub(r'`([^`]+)`', r'\1', line)
            
            lines.append(line)
        
        return lines
    
    def _create_pdf_xhtml2pdf(self, content: Dict[str, Any], output_path: str):
        """使用xhtml2pdf直接生成PDF"""
        import markdown
        from xhtml2pdf import pisa
        from io import StringIO
        
        markdown_content = content.get('content', '')
        
        md = markdown.Markdown(extensions=['tables', 'fenced_code', 'nl2br'])
        html_body = md.convert(markdown_content)
        
        title = content.get('title', '书籍精简版')
        author = content.get('author', 'Unknown')
        
        full_html = self._build_xhtml2pdf_html(title, author, html_body)
        
        with open(output_path, 'wb') as pdf_file:
            pisa_status = pisa.CreatePDF(
                src=full_html,
                dest=pdf_file
            )
            if pisa_status.err:
                raise Exception(f"xhtml2pdf错误: {pisa_status.err}")
    
    def _build_xhtml2pdf_html(self, title: str, author: str, body_html: str) -> str:
        """构建xhtml2pdf使用的HTML文档"""
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"/>
<title>{title}</title>
<style>
* {{
    box-sizing: border-box;
}}

body {{
    font-family: "SimHei", "Microsoft YaHei", "SimSun", "STKaiti", serif;
    font-size: 12pt;
    line-height: 1.8;
    color: #333;
    margin: 0;
    padding: 20px;
}}

h1 {{
    font-size: 24pt;
    font-weight: bold;
    text-align: center;
    margin: 0 0 10px 0;
    padding: 20px 0;
    page-break-after: always;
}}

.author {{
    text-align: center;
    font-size: 11pt;
    color: #666;
    margin: 0 0 30px 0;
}}

h2 {{
    font-size: 18pt;
    font-weight: bold;
    margin: 30px 0 15px 0;
    padding: 10px 0;
    border-bottom: 2px solid #333;
    page-break-after: avoid;
}}

h3 {{
    font-size: 14pt;
    font-weight: bold;
    margin: 25px 0 10px 0;
    color: #444;
    page-break-after: avoid;
}}

h4 {{
    font-size: 12pt;
    font-weight: bold;
    margin: 20px 0 8px 0;
    color: #555;
}}

p {{
    margin: 0 0 15px 0;
    text-indent: 2em;
    line-height: 1.8;
}}

ul, ol {{
    margin: 10px 0;
    padding-left: 2em;
}}

li {{
    margin: 8px 0;
    line-height: 1.8;
}}

blockquote {{
    margin: 20px 0;
    padding: 15px 20px;
    border-left: 4px solid #666;
    background: #f8f8f8;
}}

blockquote p {{
    margin: 0;
    text-indent: 0;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
    page-break-inside: avoid;
}}

th, td {{
    border: 1px solid #ddd;
    padding: 10px;
    text-align: left;
}}

th {{
    background: #f5f5f5;
    font-weight: bold;
}}

code {{
    font-family: "Consolas", "SimHei", monospace;
    background: #f0f0f0;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 10pt;
}}

pre {{
    background: #f5f5f5;
    padding: 15px;
    overflow-x: auto;
    border-radius: 5px;
    page-break-inside: avoid;
    margin: 15px 0;
}}

pre code {{
    background: none;
    padding: 0;
}}

hr {{
    border: none;
    border-top: 1px solid #ddd;
    margin: 30px 0;
}}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="author">作者: {author}</p>
{body_html}
</body>
</html>
'''
    
    def _create_pdf_calibre(self, content: Dict[str, Any], output_path: str):
        """回退方法：使用Calibre转换PDF"""
        import subprocess
        import tempfile
        import shutil
        import json
        from pathlib import Path
        
        try:
            base_name = content.get('title', 'book').replace('/', '_').replace('\\', '_')
            with tempfile.TemporaryDirectory() as tmpdir:
                epub_path = os.path.join(tmpdir, f"{base_name}.epub")
                
                self._create_mini_epub(content, epub_path)
                
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
                    "--input-encoding", "utf-8",
                ]
                
                result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='replace', timeout=180)
                
                if result.returncode != 0:
                    logger.warning(f"ebook-convert失败: {result.stderr}")
                    self._create_pdf_fallback(content, output_path)
        except Exception as e:
            logger.warning(f"Calibre PDF生成异常: {e}, 使用备用方法")
            self._create_pdf_fallback(content, output_path)
    
    def _create_mini_epub(self, content: Dict[str, Any], output_path: str):
        """创建精简版EPUB - 支持自由格式Markdown内容"""
        import zipfile
        import re
        
        title = content.get('title', 'Unknown')
        author = content.get('author', 'Unknown')
        
        if content.get('html_body'):
            html_body = content['html_body']
        else:
            markdown_content = content.get('content', '')
            html_body = self._markdown_to_html(markdown_content)
        
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
h1 {{ text-align: center; font-size: 1.5em; margin-top: 2em; margin-bottom: 1.5em; page-break-after: avoid; }}
h2 {{ margin-top: 2em; margin-bottom: 1.5em; color: #333; border-bottom: 1px solid #ddd; padding-bottom: 0.3em; page-break-after: avoid; page-break-before: auto; }}
h3 {{ margin-top: 1.5em; margin-bottom: 1em; color: #555; page-break-after: avoid; }}
h4 {{ margin-top: 1em; margin-bottom: 0.8em; color: #666; page-break-after: avoid; }}
p {{ text-indent: 2.5em; line-height: 2.2; margin: 0 0 2.5em 0; text-align: justify; }}
ul, ol {{ margin: 0.5em 0; padding-left: 2em; page-break-inside: avoid; }}
li {{ margin: 0 0 1.2em 0; line-height: 1.8; page-break-inside: avoid; }}
blockquote {{ margin: 2em 0; padding: 0.5em 2em; border-left: 4px solid #999; background: #f5f9fc; color: #333; page-break-inside: avoid; }}
table {{ border-collapse: collapse; width: 100%; margin: 1.5em 0; page-break-inside: avoid; table-layout: auto; word-wrap: break-word; }}
th, td {{ border: 1px solid #ddd; padding: 0.8em; text-align: left; word-wrap: break-word; }}
th {{ background: #f5f5f5; }}
code {{ background: #f0f0f0; padding: 0.2em 0.4em; border-radius: 3px; font-family: monospace; }}
pre {{ background: #f5f5f5; padding: 1em; overflow-x: auto; border-radius: 5px; page-break-inside: avoid; }}
.quote {{ font-style: italic; color: #666; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p style="text-align:center">作者: {author}</p>
{html_body}
</body>
</html>
'''
            
            epub_css = '''body {{ 
    font-family: "SimHei", "Microsoft YaHei", "SimSun", "STKaiti", serif; 
    font-size: 16px; 
    line-height: 1.8; 
    text-align: justify;
    margin: 0;
    padding: 0;
}
h1 { 
    font-size: 28px; 
    font-weight: bold; 
    text-align: center; 
    margin: 30px 0 20px 0; 
    page-break-after: always; 
    page-break-inside: avoid;
}
.author { 
    text-align: center; 
    font-size: 14px; 
    color: #666; 
    margin: 0 0 40px 0; 
}
h2 { 
    font-size: 22px; 
    font-weight: bold; 
    margin: 40px 0 20px 0; 
    padding: 10px 0; 
    border-bottom: 2px solid #333; 
    page-break-after: avoid; 
    page-break-inside: avoid;
}
h3 { 
    font-size: 18px; 
    font-weight: bold; 
    margin: 30px 0 15px 0; 
    color: #444; 
    page-break-after: avoid; 
    page-break-inside: avoid;
}
h4 { 
    font-size: 16px; 
    font-weight: bold; 
    margin: 25px 0 12px 0; 
    color: #555; 
    page-break-after: avoid; 
}
p { 
    margin: 0 0 20px 0; 
    text-indent: 2em; 
    line-height: 1.8;
}
ul, ol { 
    margin: 15px 0; 
    padding-left: 2.5em; 
    page-break-inside: avoid; 
}
li { 
    margin: 10px 0; 
    line-height: 1.8; 
    page-break-inside: avoid; 
}
blockquote { 
    margin: 25px 0; 
    padding: 15px 20px; 
    border-left: 4px solid #666; 
    background: #f8f8f8; 
    page-break-inside: avoid; 
}
blockquote p {
    margin: 0;
    text-indent: 0;
}
table { 
    border-collapse: collapse; 
    width: 100%; 
    margin: 25px 0; 
    page-break-inside: avoid; 
    table-layout: auto; 
    word-wrap: break-word;
}
th, td { 
    border: 1px solid #ddd; 
    padding: 12px; 
    text-align: left; 
    word-wrap: break-word;
}
th { 
    background: #f5f5f5; 
    font-weight: bold;
}
code { 
    background: #f0f0f0; 
    padding: 2px 6px; 
    border-radius: 3px; 
    font-family: Consolas, monospace;
}
pre { 
    background: #f5f5f5; 
    padding: 15px; 
    overflow-x: auto; 
    border-radius: 5px; 
    page-break-inside: avoid; 
    margin: 20px 0;
}
pre code { 
    background: none; 
    padding: 0; 
}
hr {
    border: none;
    border-top: 1px solid #ddd;
    margin: 30px 0;
}
.page-break {
    page-break-after: always;
}'''
            
            epub.writestr('OEBPS/Styles/style.css', epub_css, compress_type=zipfile.ZIP_DEFLATED)
            epub.writestr('OEBPS/Text/content.xhtml', html_content, compress_type=zipfile.ZIP_DEFLATED)
            
            markdown_content = content.get('content', '')
            toc_items = self._extract_toc_from_markdown(markdown_content)
            toc_content = self._build_toc_ncx(title, toc_items)
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

    def _markdown_to_html(self, md: str) -> str:
        """简单的Markdown转HTML"""
        import re
        
        if not md:
            return '<p>（无内容）</p>'

        def convert_mermaid_to_text(mermaid_code):
            """将Mermaid流程图转换为可读文字"""
            nodes = re.findall(r'(\w+)\[([^\]]+)\]', mermaid_code)
            node_map = dict(nodes)
            connections = re.findall(r'(\w+)\s*-->\|?([^|\]]+)\|?>?\s*(\w+)', mermaid_code)
            lines = ['【流程图】']
            step = 1
            for from_node, label, to_node in connections:
                from_text = node_map.get(from_node, '?')
                to_text = node_map.get(to_node, '?')
                label = label.strip() if label.strip() else '执行'
                lines.append(f"{step}. {from_text} → {to_text} ({label})")
                step += 1
            if '-->|' in mermaid_code or '循环' in mermaid_code.lower():
                lines.append(f"→ 循环回到开始")
            return '\n'.join(lines)

        md = re.sub(r'```mermaid\n?(graph \w+[\s\S]*?)```', lambda m: convert_mermaid_to_text(m.group(0)), md)
        
        html_lines = []
        lines = md.split('\n')
        
        in_code_block = False
        in_table = False
        in_list = False
        table_row_count = 0
        
        for line in lines:
            line = line.rstrip()
            line = re.sub(r'<[^>]+>', '', line)
            
            if line.startswith('```'):
                if in_code_block:
                    html_lines.append('</pre>')
                    in_code_block = False
                else:
                    html_lines.append('<pre>')
                    in_code_block = True
                continue
            
            if in_code_block:
                html_lines.append(self._escape_html(line))
                continue
            
            table_line = line.strip()
            if table_line.startswith('|') and '|' in table_line[1:]:
                cells = [c.strip() for c in table_line.split('|')[1:-1]]
                
                is_separator = all(
                    set(c.replace('-', '').replace(':', '').replace(' ', '')) <= {'', ':'}
                    for c in cells if c
                )
                
                if is_separator:
                    continue
                
                if not in_table:
                    in_table = True
                    html_lines.append('<table>')
                
                is_header = table_row_count == 0
                table_row_count += 1
                tag = 'th' if is_header else 'td'
                processed_cells = []
                for c in cells:
                    if c:
                        c = re.sub(r'<br\s*/?>', ' ', c, flags=re.IGNORECASE)
                        c = re.sub(r'<font[^>]*>', '', c)
                        c = c.replace('</font>', '')
                        c = re.sub(r'<[^>]+>', '', c)
                        c = c.strip()
                        if c:
                            c = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', c)
                            c = re.sub(r'\*(.+?)\*', r'<em>\1</em>', c)
                            processed_cells.append(f'<{tag}>{c}</{tag}>')
                row = ''.join(processed_cells)
                html_lines.append(f'<tr>{row}</tr>')
                continue
            elif in_table:
                in_table = False
                html_lines.append('</table>')
                table_row_count = 0
            
            if line.startswith('### '):
                text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line[4:])
                html_lines.append(f'<h4>{text}</h4>')
            elif line.startswith('## '):
                text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line[3:])
                html_lines.append(f'<h2>{text}</h2>')
            elif line.startswith('# '):
                text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line[2:])
                html_lines.append(f'<h3>{text}</h3>')
            elif line.strip().startswith('- ') or line.strip().startswith('* '):
                if not in_list:
                    html_lines.append('<ul>')
                    in_list = True
                text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line.strip()[2:])
                text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
                html_lines.append(f'<li>{text}</li>')
            elif re.match(r'^\d+\.\s', line.strip()):
                if not in_list:
                    html_lines.append('<ol>')
                    in_list = True
                text = re.sub(r'^\d+\.\s', '', line.strip())
                text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
                text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
                html_lines.append(f'<li>{text}</li>')
            elif in_list:
                in_list = False
                html_lines.append('</ul>')
                line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
                line = re.sub(r'\*(.+?)\*', r'<em>\1</em>', line)
                html_lines.append(f'<p>{line}</p>' if line.strip() else '<br/>')
            elif line.startswith('>'):
                text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line[1:].strip())
                text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
                html_lines.append(f'<blockquote>{text}</blockquote>')
            elif line.strip() in ['---', '***', '___']:
                continue
            elif line.strip():
                line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
                line = re.sub(r'\*(.+?)\*', r'<em>\1</em>', line)
                line = re.sub(r'`(.+?)`', r'<code>\1</code>', line)
                html_lines.append(f'<p>{line}</p>')
            else:
                html_lines.append('<br/>')
        
        if in_list:
            html_lines.append('</ul>' if not any('<ol>' in l for l in html_lines) else '</ol>')
        
        return '\n'.join(html_lines)

    def _escape_html(self, text: str) -> str:
        """转义HTML特殊字符"""
        return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))

    def _extract_toc_from_markdown(self, md: str) -> list:
        """从Markdown中提取目录"""
        import re
        toc = []
        for line in md.split('\n'):
            if line.startswith('## '):
                toc.append(('h2', line[3:].strip()))
            elif line.startswith('### '):
                toc.append(('h3', line[4:].strip()))
            elif line.startswith('# '):
                toc.append(('h1', line[2:].strip()))
        return toc

    def _build_toc_ncx(self, title: str, toc_items: list) -> str:
        """构建TOC NCX文件"""
        nav_points = ''
        for i, (level, text) in enumerate(toc_items[:20], 1):
            nav_points += f'''<navPoint id="navPoint-{i}" playOrder="{i}">
<navLabel><text>{self._escape_html(text)}</text></navLabel>
<content src="Text/content.xhtml#section-{i}"/>
</navPoint>
'''
        
        return f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
<head><meta name="dtb:uid" content="book-mini-001"/></head>
<docTitle><text>{self._escape_html(title)}</text></docTitle>
<navMap>
{nav_points}
</navMap>
</ncx>
'''
    
    def _create_pdf_fallback(self, content: Dict[str, Any], output_path: str):
        """备用PDF生成方法 - 支持Markdown内容和中文"""
        import re
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.units import cm
        
        author = content.get('author', 'Unknown')
        markdown_content = content.get('content', '')
        
        title_match = re.search(r'^#\s+(.+)$', markdown_content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
            markdown_content = re.sub(r'^#\s+.+$', '', markdown_content, count=1, flags=re.MULTILINE).strip()
        else:
            title = content.get('title', 'Unknown')
        
        chinese_fonts = [
            ("SimSun", "simsun.ttc"),
            ("SimHei", "simhei.ttf"),
            ("Microsoft YaHei", "msyh.ttc"),
            ("STSong", "STSONG.TTF"),
        ]
        
        font_name = "Helvetica"
        for name, font_file in chinese_fonts:
            try:
                font_path = f"C:/Windows/Fonts/{font_file}"
                import os
                if os.path.exists(font_path):
                    pdfmetrics.registerFont(TTFont(name, font_path))
                    font_name = name
                    logger.info(f"注册中文字体: {name}")
                    break
            except Exception as e:
                logger.warning(f"注册字体 {name} 失败: {e}")
        
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        styles = getSampleStyleSheet()
        story = []
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontName=font_name,
            fontSize=22,
            leading=28,
            spaceAfter=12,
            alignment=TA_CENTER,
            textColor='#333333'
        )
        
        author_style = ParagraphStyle(
            'AuthorStyle',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=12,
            leading=16,
            alignment=TA_CENTER,
            textColor='#666666',
            spaceAfter=20
        )
        
        normal_style = ParagraphStyle(
            'ChineseNormal',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=10.5,
            leading=17,
            firstLineIndent=21,
            alignment=TA_JUSTIFY,
            spaceBefore=5,
            spaceAfter=5
        )
        
        heading1_style = ParagraphStyle(
            'ChineseH1',
            parent=styles['Heading1'],
            fontName=font_name,
            fontSize=16,
            leading=22,
            spaceBefore=20,
            spaceAfter=16,
            textColor='#2c3e50',
            borderWidth=0,
            borderPadding=0
        )
        
        heading2_style = ParagraphStyle(
            'ChineseH2',
            parent=styles['Heading2'],
            fontName=font_name,
            fontSize=14,
            leading=20,
            spaceBefore=16,
            spaceAfter=10,
            textColor='#34495e'
        )
        
        heading3_style = ParagraphStyle(
            'ChineseH3',
            parent=styles['Heading3'],
            fontName=font_name,
            fontSize=12,
            leading=18,
            spaceBefore=12,
            spaceAfter=8,
            textColor='#555555'
        )
        
        quote_style = ParagraphStyle(
            'ChineseQuote',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=10.5,
            leading=16,
            leftIndent=20,
            rightIndent=20,
            spaceBefore=10,
            spaceAfter=10,
            textColor='#555555',
            backColor='#f5f5f5',
            borderPadding=8
        )

        list_style = ParagraphStyle(
            'ChineseList',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=10.5,
            leading=17,
            leftIndent=20,
            firstLineIndent=-10,
            spaceBefore=3,
            spaceAfter=3
        )

        custom_styles = {
            'Normal': normal_style,
            'Heading1': heading1_style,
            'Heading2': heading2_style,
            'Heading3': heading3_style,
            'Quote': quote_style,
            'List': list_style,
        }
        
        def add_page_numbers(canvas, doc):
            """添加页码"""
            from reportlab.lib.pagesizes import A4
            page_num = canvas.getPageNumber()
            text = f"第 {page_num} 页"
            canvas.drawRightString(A4[0]-2*cm, 1.5*cm, text)

        story.append(Paragraph(title, title_style))
        story.append(Paragraph(f"作者: {author}", author_style))
        story.append(Spacer(1, 0.5 * inch))
        
        self._add_markdown_to_story(story, markdown_content, custom_styles, font_name)
        
        doc.build(story, onFirstPage=add_page_numbers, onLaterPages=add_page_numbers)

    def _add_markdown_to_story(self, story: list, md: str, styles, font_name: str = "SimSun"):
        """将Markdown内容添加到PDF story"""
        import re
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        
        if not md:
            return

        def calculate_col_widths(table_data, page_width=14*cm):
            """动态计算表格列宽"""
            if not table_data or not table_data[0]:
                return None
            num_cols = len(table_data[0])
            margins = 1.6*cm
            usable_width = page_width - margins

            col_max_len = []
            for col_idx in range(num_cols):
                max_len = max(len(str(row[col_idx])) if col_idx < len(row) else 0 for row in table_data)
                col_max_len.append(max(max_len, 8))

            total_chars = sum(col_max_len)
            if total_chars == 0:
                return None

            col_widths = []
            for length in col_max_len:
                width = (length / total_chars) * usable_width
                col_widths.append(max(width, 2*cm))
            return col_widths

        def convert_mermaid_to_text(mermaid_code):
            """将Mermaid流程图转换为可读文字"""
            nodes = re.findall(r'(\w+)\[([^\]]+)\]', mermaid_code)
            node_map = dict(nodes)

            connections = re.findall(r'(\w+)\s*-->\|?([^|\]]+)\|?>?\s*(\w+)', mermaid_code)

            lines = ['【流程图】']
            step = 1

            for from_node, label, to_node in connections:
                from_text = node_map.get(from_node, '?')
                to_text = node_map.get(to_node, '?')
                label = label.strip() if label.strip() else '执行'
                lines.append(f"{step}. {from_text} → {to_text} ({label})")
                step += 1

            if '-->|' in mermaid_code or '循环' in mermaid_code.lower():
                lines.append(f"→ 循环回到开始")

            return '\n'.join(lines)

        md = re.sub(r'```mermaid\n?(graph \w+[\s\S]*?)```', lambda m: convert_mermaid_to_text(m.group(0)), md)

        def clean_html(text):
            text = re.sub(r'<br\s*/?>', ' ', text, flags=re.IGNORECASE)
            text = re.sub(r'<font[^>]*>', '', text)
            text = text.replace('</font>', '')
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
            text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
            text = re.sub(r'`(.+?)`', r'<font name="Courier">\1</font>', text)
            return text.strip()
        
        def create_table_style():
            return TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), font_name),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('LEADING', (0, 0), (-1, -1), 14),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ])
        
        lines = md.split('\n')
        in_list = False
        in_table = False
        table_data = []
        
        for line in lines:
            line = line.rstrip()
            
            if re.match(r'^-{3,}$', line.strip()):
                continue
            
            if not line.strip():
                if in_list:
                    in_list = False
                    story.append(Spacer(1, 0.1 * inch))
                if in_table:
                    in_table = False
                    if table_data:
                        col_widths = calculate_col_widths(table_data)
                        t = Table(table_data, colWidths=col_widths, repeatRows=1)
                        t.setStyle(create_table_style())
                        story.append(t)
                        story.append(Spacer(1, 0.3 * inch))
                        table_data = []
                continue
            
            if line.strip().startswith('|') and '|' in line.strip()[1:]:
                cells = [c.strip() for c in line.strip().split('|')[1:-1]]
                is_separator = all(set(c.replace('-', '').replace(':', '').replace(' ', '')) <= {'', ':'} for c in cells if c)
                if is_separator:
                    continue
                if not in_table:
                    in_table = True
                    table_data = []
                cleaned_cells = [Paragraph(clean_html(c), styles['Normal']) for c in cells if c]
                if cleaned_cells:
                    table_data.append(cleaned_cells)
                continue
            elif in_table:
                in_table = False
                if table_data:
                    col_widths = calculate_col_widths(table_data)
                    t = Table(table_data, colWidths=col_widths, repeatRows=1)
                    t.setStyle(create_table_style())
                    story.append(t)
                    story.append(Spacer(1, 0.3 * inch))
                    table_data = []
            
            if line.startswith('### '):
                story.append(Paragraph(clean_html(line[4:]), styles['Heading3']))
            elif line.startswith('## '):
                story.append(Paragraph(clean_html(line[3:]), styles['Heading1']))
            elif line.startswith('# '):
                story.append(Paragraph(clean_html(line[2:]), styles['Heading2']))
            elif line.strip().startswith('- ') or line.strip().startswith('* '):
                if not in_list:
                    story.append(Spacer(1, 0.1 * inch))
                    in_list = True
                text = clean_html(line.strip()[2:])
                list_style = styles.get('List', styles['Normal'])
                story.append(Paragraph(f'• {text}', list_style))
            elif re.match(r'^\d+\.\s', line.strip()):
                if not in_list:
                    story.append(Spacer(1, 0.1 * inch))
                    in_list = True
                text = clean_html(re.sub(r'^\d+\.\s', '', line.strip()))
                list_style = styles.get('List', styles['Normal'])
                story.append(Paragraph(f'{text}', list_style))
            elif line.startswith('>'):
                text = clean_html(line[1:].strip())
                quote_style = styles.get('Quote', styles['Normal'])
                story.append(Paragraph(f'<i>{text}</i>', quote_style))
            else:
                text = clean_html(line)
                if text:
                    story.append(Paragraph(text, styles['Normal']))
        
        if in_list:
            story.append(Spacer(1, 0.1 * inch))
        
        if in_table and table_data:
            col_widths = calculate_col_widths(table_data)
            t = Table(table_data, colWidths=col_widths, repeatRows=1)
            t.setStyle(create_table_style())
            story.append(t)


def generate_summary(book_id: str, epub_path: str) -> bool:
    """生成书籍精简版"""
    summarizer = ContentSummarizer()
    return summarizer.summarize(book_id, epub_path)


if __name__ == "__main__":
    print("内容精简器测试")
