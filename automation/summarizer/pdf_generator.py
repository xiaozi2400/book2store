"""
PDF生成模块 - 多种方式生成精简版PDF
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from automation.exceptions import PDFConvertError
from automation.summarizer.fonts import get_chinese_font, register_chinese_fonts
from automation.utils import logger


class SummaryPDFGenerator:
    """精简版PDF生成器 - 支持多种生成方式"""

    def create(self, content: Dict[str, Any], output_path: str, cover_path: Optional[str] = None):
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

    # ==================== WeasyPrint ====================

    def _create_pdf_weasyprint(self, content: Dict[str, Any], output_path: str, cover_path: Optional[str] = None):
        """使用WeasyPrint生成PDF"""
        import markdown

        try:
            msys64_path = r"C:\msys64\mingw64\bin"
            if os.path.exists(msys64_path):
                os.environ["WEASYPRINT_DLL_DIRECTORIES"] = msys64_path
            from weasyprint import HTML
        except OSError as e:
            if "libgobject" in str(e) or "cannot load library" in str(e):
                raise PDFConvertError("WeasyPrint缺少GTK3运行时库，自动跳过")
            raise

        markdown_content = content.get("content", "")

        md = markdown.Markdown(extensions=["tables", "fenced_code", "nl2br"])
        html_body = md.convert(markdown_content)

        _title = content.get("title", "书籍精简版")
        _author = content.get("author", "Unknown")

        subtitle_match = re.search(r"<h2[^>]*>([^<]+)</h2>", html_body)
        if subtitle_match:
            subtitle = subtitle_match.group(1)
            body_html = re.sub(r"<h2[^>]*>[^<]+</h2>\s*", "", html_body, count=1)
        else:
            subtitle = None
            body_html = html_body

        full_html = self._build_weasyprint_html(_title, subtitle, body_html, cover_path)

        HTML(string=full_html).write_pdf(output_path)

    def _build_weasyprint_html(
        self, title: str, subtitle: str, body_html: str, cover_path: Optional[str] = None
    ) -> str:
        """构建WeasyPrint使用的HTML文档"""
        cover_html = self._build_cover_html(cover_path)

        return f"""<!DOCTYPE html>
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
"""

    # ==================== Playwright ====================

    def _create_pdf_playwright(self, content: Dict[str, Any], output_path: str, cover_path: Optional[str] = None):
        """使用Playwright+Chrome生成PDF"""
        import markdown
        from playwright.sync_api import sync_playwright

        markdown_content = content.get("content", "")

        md = markdown.Markdown(extensions=["tables", "fenced_code", "nl2br"])
        html_body = md.convert(markdown_content)

        title = content.get("title", "书籍精简版")

        subtitle_match = re.search(r"<h2[^>]*>([^<]+)</h2>", html_body)
        if subtitle_match:
            subtitle = subtitle_match.group(1)
            body_html = re.sub(r"<h2[^>]*>[^<]+</h2>\s*", "", html_body, count=1)
        else:
            subtitle = None
            body_html = html_body

        full_html = self._build_playwright_html(title, subtitle, body_html, cover_path)

        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True
            )
            page = browser.new_page()
            page.set_content(full_html, wait_until="networkidle")

            page.pdf(
                path=output_path,
                format="A4",
                margin={"top": "20mm", "bottom": "20mm", "left": "20mm", "right": "20mm"},
                print_background=True,
            )

            browser.close()

    def _build_playwright_html(
        self, title: str, subtitle: str, body_html: str, cover_path: Optional[str] = None
    ) -> str:
        """构建Playwright使用的HTML文档"""
        cover_html = self._build_cover_html(cover_path)

        return f"""<!DOCTYPE html>
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
"""

    # ==================== ReportLab ====================

    def _create_pdf_reportlab(self, content: Dict[str, Any], output_path: str, cover_path: Optional[str] = None):
        """使用reportlab直接生成PDF - 原生支持中文"""
        import re

        from reportlab.lib.units import cm

        register_chinese_fonts()

        title = content.get("title", "书籍精简版")
        author = content.get("author", "Unknown")
        markdown_content = content.get("content", "")

        doc = SimpleDocTemplate(
            output_path, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm
        )

        styles = getSampleStyleSheet()

        chinese_font = get_chinese_font()

        title_style = ParagraphStyle(
            "CustomTitle", parent=styles["Heading1"], fontSize=24, alignment=1, spaceAfter=20, fontName=chinese_font
        )
        author_style = ParagraphStyle(
            "Author",
            parent=styles["Normal"],
            fontSize=12,
            alignment=1,
            textColor=colors.grey,
            spaceAfter=30,
            fontName=chinese_font,
        )
        h2_style = ParagraphStyle(
            "H2",
            parent=styles["Heading2"],
            fontSize=18,
            spaceBefore=20,
            spaceAfter=10,
            borderPadding=5,
            borderColor=colors.black,
            borderWidth=0,
            fontName=chinese_font,
        )
        normal_style = ParagraphStyle(
            "Normal",
            parent=styles["Normal"],
            fontSize=11,
            lineHeight=1.8,
            firstLineIndent=21,
            spaceAfter=10,
            fontName=chinese_font,
        )
        quote_style = ParagraphStyle(
            "Quote",
            parent=styles["Italic"],
            fontSize=11,
            leftIndent=20,
            rightIndent=20,
            spaceBefore=10,
            spaceAfter=10,
            borderPadding=10,
            borderColor=colors.grey,
            borderWidth=1,
            fontName=chinese_font,
        )

        story = []

        story.append(Paragraph(title, title_style))
        story.append(Paragraph(f"作者: {author}", author_style))

        lines = self._parse_markdown_lines(markdown_content)

        for line in lines:
            if not line.strip():
                continue

            if line.startswith("## "):
                text = line[3:].strip()
                story.append(Paragraph(text, h2_style))
            elif line.startswith("### "):
                text = line[4:].strip()
                story.append(Paragraph(text, styles["Heading3"]))
            elif line.startswith("> "):
                text = line[2:].strip()
                story.append(Paragraph(text, quote_style))
            elif line.startswith("| ") and "|" in line[1:]:
                pass
            elif line.startswith("- ") or line.startswith("* "):
                story.append(Paragraph(line, normal_style))
            elif re.match(r"^\d+\.\s", line):
                story.append(Paragraph(line, normal_style))
            elif line.startswith("---"):
                story.append(Spacer(1, 0.3 * cm))
            else:
                story.append(Paragraph(line, normal_style))

        doc.build(story)

    def _parse_markdown_lines(self, markdown_content: str) -> list:
        """解析Markdown内容为行列表"""
        lines = []
        in_code_block = False

        for line in markdown_content.split("\n"):
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue

            if in_code_block:
                continue

            line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
            line = re.sub(r"\*([^*]+)\*", r"\1", line)
            line = re.sub(r"`([^`]+)`", r"\1", line)

            lines.append(line)

        return lines

    # ==================== Calibre 回退 ====================

    def _create_pdf_calibre(self, content: Dict[str, Any], output_path: str):
        """回退方法：使用Calibre转换PDF"""
        try:
            base_name = content.get("title", "book").replace("/", "_").replace("\\", "_")
            with tempfile.TemporaryDirectory() as tmpdir:
                epub_path = os.path.join(tmpdir, f"{base_name}.epub")

                self._create_mini_epub(content, epub_path)

                pdf_config_path = Path(__file__).parent.parent.parent / "pdf_config.json"
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
                    "--paper-size",
                    page_cfg.get("paper_size", "letter"),
                    "--margin-top",
                    str(page_cfg.get("margin_top", 50)),
                    "--margin-bottom",
                    str(page_cfg.get("margin_bottom", 50)),
                    "--margin-left",
                    str(page_cfg.get("margin_left", 12)),
                    "--margin-right",
                    str(page_cfg.get("margin_right", 12)),
                    "--pdf-default-font-size",
                    str(font_cfg.get("default_size", 18)),
                    "--pdf-serif-family",
                    font_cfg.get("serif", "SimSun"),
                    "--pdf-sans-family",
                    font_cfg.get("sans", "SimSun"),
                    "--pdf-mono-family",
                    font_cfg.get("mono", "SimSun"),
                    "--pdf-page-numbers",
                    "--input-encoding",
                    "utf-8",
                ]

                result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=180)

                if result.returncode != 0:
                    logger.warning(f"ebook-convert失败: {result.stderr}")
                    self._create_pdf_fallback(content, output_path)
        except Exception as e:
            logger.warning(f"Calibre PDF生成异常: {e}, 使用备用方法")
            self._create_pdf_fallback(content, output_path)

    # ==================== EPUB创建（供Calibre使用）====================

    def _create_mini_epub(self, content: Dict[str, Any], output_path: str):
        """创建精简版EPUB - 支持自由格式Markdown内容"""
        title = content.get("title", "Unknown")
        author = content.get("author", "Unknown")

        if content.get("html_body"):
            html_body = content.get("html_body", "")
        else:
            markdown_content = content.get("content", "")
            html_body = self._markdown_to_html(markdown_content)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as epub:
            epub.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

            html_content = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
<meta charset="utf-8"/>
<title>{title}</title>
<style>
body {{ font-family: SimSun, 'Times New Roman', serif; margin: 1em; }}
h1 {{ text-align: center; font-size: 1.5em; margin-top: 2em; margin-bottom: 1.5em; page-break-after: avoid; }}
h2 {{ margin-top: 2em; margin-bottom: 1.5em; color: #333; border-bottom: 1px solid #ddd; padding-bottom: 0.3em;
    page-break-after: avoid; page-break-before: auto; }}
h3 {{ margin-top: 1.5em; margin-bottom: 1em; color: #555; page-break-after: avoid; }}
h4 {{ margin-top: 1em; margin-bottom: 0.8em; color: #666; page-break-after: avoid; }}
p {{ text-indent: 2.5em; line-height: 2.2; margin: 0 0 2.5em 0; text-align: justify; }}
ul, ol {{ margin: 0.5em 0; padding-left: 2em; page-break-inside: avoid; }}
li {{ margin: 0 0 1.2em 0; line-height: 1.8; page-break-inside: avoid; }}
blockquote {{ margin: 2em 0; padding: 0.5em 2em; border-left: 4px solid #999;
    background: #f5f9fc; color: #333; page-break-inside: avoid; }}
table {{ border-collapse: collapse; width: 100%; margin: 1.5em 0; page-break-inside: avoid;
    table-layout: auto; word-wrap: break-word; }}
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
"""

            epub_css = """body {
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
}"""

            epub.writestr("OEBPS/Styles/style.css", epub_css, compress_type=zipfile.ZIP_DEFLATED)
            epub.writestr("OEBPS/Text/content.xhtml", html_content, compress_type=zipfile.ZIP_DEFLATED)

            markdown_content = content.get("content", "")
            toc_items = self._extract_toc_from_markdown(markdown_content)
            toc_content = self._build_toc_ncx(title, toc_items)
            epub.writestr("OEBPS/toc.ncx", toc_content, compress_type=zipfile.ZIP_DEFLATED)

            container_content = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles>
<rootfile full-path="OEBPS/package.opf" media-type="application/oebps-package+xml"/>
</rootfiles>
</container>
"""
            epub.writestr("META-INF/container.xml", container_content, compress_type=zipfile.ZIP_DEFLATED)

            package_content = f"""<?xml version="1.0" encoding="UTF-8"?>
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
"""
            epub.writestr("OEBPS/package.opf", package_content, compress_type=zipfile.ZIP_DEFLATED)

    # ==================== 工具方法 ====================

    def _build_cover_html(self, cover_path: Optional[str]) -> str:
        """构建封面HTML（base64嵌入）"""
        if not cover_path or not os.path.exists(cover_path):
            return ""

        try:
            with open(cover_path, "rb") as f:
                cover_data = base64.b64encode(f.read()).decode("utf-8")

            ext = os.path.splitext(cover_path)[1].lower()
            mime_type = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".bmp": "image/bmp",
            }.get(ext, "image/jpeg")

            return f"""
<div style="text-align: center; page-break-after: always;">
    <img src="data:{mime_type};base64,{cover_data}" style="max-width: 100%; max-height: 90vh; display: block; margin: auto;" />
</div>"""  # noqa: E501
        except Exception as e:
            logger.warning(f"嵌入封面失败: {e}")
            return ""

    def _markdown_to_html(self, md: str) -> str:
        """简单的Markdown转HTML"""
        if not md:
            return "<p>（无内容）</p>"

        def convert_mermaid_to_text(mermaid_code):
            """将Mermaid流程图转换为可读文字"""
            nodes = re.findall(r"(\w+)\[([^\]]+)\]", mermaid_code)
            node_map = dict(nodes)
            connections = re.findall(r"(\w+)\s*-->\|?([^|\]]+)\|?>?\s*(\w+)", mermaid_code)
            lines = ["【流程图】"]
            step = 1
            for from_node, label, to_node in connections:
                from_text = node_map.get(from_node, "?")
                to_text = node_map.get(to_node, "?")
                label = label.strip() if label.strip() else "执行"
                lines.append(f"{step}. {from_text} → {to_text} ({label})")
                step += 1
            if "-->|" in mermaid_code or "循环" in mermaid_code.lower():
                lines.append("→ 循环回到开始")
            return "\n".join(lines)

        md = re.sub(r"```mermaid\n?(graph \w+[\s\S]*?)```", lambda m: convert_mermaid_to_text(m.group(0)), md)

        html_lines = []
        lines = md.split("\n")

        in_code_block = False
        in_table = False
        in_list = False
        table_row_count = 0

        for line in lines:
            line = line.rstrip()
            line = re.sub(r"<[^>]+>", "", line)

            if line.startswith("```"):
                if in_code_block:
                    html_lines.append("</pre>")
                    in_code_block = False
                else:
                    html_lines.append("<pre>")
                    in_code_block = True
                continue

            if in_code_block:
                html_lines.append(self._escape_html(line))
                continue

            table_line = line.strip()
            if table_line.startswith("|") and "|" in table_line[1:]:
                cells = [c.strip() for c in table_line.split("|")[1:-1]]

                is_separator = all(
                    set(c.replace("-", "").replace(":", "").replace(" ", "")) <= {"", ":"} for c in cells if c
                )

                if is_separator:
                    continue

                if not in_table:
                    in_table = True
                    html_lines.append("<table>")

                is_header = table_row_count == 0
                table_row_count += 1
                tag = "th" if is_header else "td"
                processed_cells = []
                for c in cells:
                    if c:
                        c = re.sub(r"<br\s*/?>", " ", c, flags=re.IGNORECASE)
                        c = re.sub(r"<font[^>]*>", "", c)
                        c = c.replace("</font>", "")
                        c = re.sub(r"<[^>]+>", "", c)
                        c = c.strip()
                        if c:
                            c = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", c)
                            c = re.sub(r"\*(.+?)\*", r"<em>\1</em>", c)
                            processed_cells.append(f"<{tag}>{c}</{tag}>")
                row = "".join(processed_cells)
                html_lines.append(f"<tr>{row}</tr>")
                continue
            elif in_table:
                in_table = False
                html_lines.append("</table>")
                table_row_count = 0

            if line.startswith("### "):
                text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line[4:])
                html_lines.append(f"<h4>{text}</h4>")
            elif line.startswith("## "):
                text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line[3:])
                html_lines.append(f"<h2>{text}</h2>")
            elif line.startswith("# "):
                text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line[2:])
                html_lines.append(f"<h3>{text}</h3>")
            elif line.strip().startswith("- ") or line.strip().startswith("* "):
                if not in_list:
                    html_lines.append("<ul>")
                    in_list = True
                text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line.strip()[2:])
                text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
                html_lines.append(f"<li>{text}</li>")
            elif re.match(r"^\d+\.\s", line.strip()):
                if not in_list:
                    html_lines.append("<ol>")
                    in_list = True
                text = re.sub(r"^\d+\.\s", "", line.strip())
                text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
                text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
                html_lines.append(f"<li>{text}</li>")
            elif in_list:
                in_list = False
                html_lines.append("</ul>")
                line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
                line = re.sub(r"\*(.+?)\*", r"<em>\1</em>", line)
                html_lines.append(f"<p>{line}</p>" if line.strip() else "<br/>")
            elif line.startswith(">"):
                text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line[1:].strip())
                text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
                html_lines.append(f"<blockquote>{text}</blockquote>")
            elif line.strip() in ["---", "***", "___"]:
                continue
            elif line.strip():
                line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
                line = re.sub(r"\*(.+?)\*", r"<em>\1</em>", line)
                line = re.sub(r"`(.+?)`", r"<code>\1</code>", line)
                html_lines.append(f"<p>{line}</p>")
            else:
                html_lines.append("<br/>")

        if in_list:
            html_lines.append("</ul>" if not any("<ol>" in line for line in html_lines) else "</ol>")

        return "\n".join(html_lines)

    def _escape_html(self, text: str) -> str:
        """转义HTML特殊字符"""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    def _extract_toc_from_markdown(self, md: str) -> list:
        """从Markdown中提取目录"""
        toc = []
        for line in md.split("\n"):
            if line.startswith("## "):
                toc.append(("h2", line[3:].strip()))
            elif line.startswith("### "):
                toc.append(("h3", line[4:].strip()))
            elif line.startswith("# "):
                toc.append(("h1", line[2:].strip()))
        return toc

    def _build_toc_ncx(self, title: str, toc_items: list) -> str:
        """构建TOC NCX文件"""
        nav_points = ""
        for i, (level, text) in enumerate(toc_items[:20], 1):
            nav_points += f"""<navPoint id="navPoint-{i}" playOrder="{i}">
<navLabel><text>{self._escape_html(text)}</text></navLabel>
<content src="Text/content.xhtml#section-{i}"/>
</navPoint>
"""

        return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
<head><meta name="dtb:uid" content="book-mini-001"/></head>
<docTitle><text>{self._escape_html(title)}</text></docTitle>
<navMap>
{nav_points}
</navMap>
</ncx>
"""

    # ==================== 备用方法 ====================

    def _create_pdf_fallback(self, content: Dict[str, Any], output_path: str):
        """备用PDF生成方法 - 支持Markdown内容和中文"""
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

        author = content.get("author", "Unknown")
        markdown_content = content.get("content", "")

        title_match = re.search(r"^#\s+(.+)$", markdown_content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
            markdown_content = re.sub(r"^#\s+.+$", "", markdown_content, count=1, flags=re.MULTILINE).strip()
        else:
            title = content.get("title", "Unknown")

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
                if os.path.exists(font_path):
                    from reportlab.pdfbase import pdfmetrics
                    from reportlab.pdfbase.ttfonts import TTFont

                    pdfmetrics.registerFont(TTFont(name, font_path))
                    font_name = name
                    logger.info(f"注册中文字体: {name}")
                    break
            except Exception as e:
                logger.warning(f"注册字体 {name} 失败: {e}")

        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import Paragraph, Spacer

        doc = SimpleDocTemplate(
            output_path, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm
        )

        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Title"],
            fontName=font_name,
            fontSize=22,
            leading=28,
            spaceAfter=12,
            alignment=TA_CENTER,
            textColor="#333333",
        )

        author_style = ParagraphStyle(
            "AuthorStyle",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=12,
            leading=16,
            alignment=TA_CENTER,
            textColor="#666666",
            spaceAfter=20,
        )

        normal_style = ParagraphStyle(
            "ChineseNormal",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=10.5,
            leading=17,
            firstLineIndent=21,
            alignment=TA_JUSTIFY,
            spaceBefore=5,
            spaceAfter=5,
        )

        heading1_style = ParagraphStyle(
            "ChineseH1",
            parent=styles["Heading1"],
            fontName=font_name,
            fontSize=16,
            leading=22,
            spaceBefore=20,
            spaceAfter=16,
            textColor="#2c3e50",
            borderWidth=0,
            borderPadding=0,
        )

        heading2_style = ParagraphStyle(
            "ChineseH2",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=14,
            leading=20,
            spaceBefore=16,
            spaceAfter=10,
            textColor="#34495e",
        )

        heading3_style = ParagraphStyle(
            "ChineseH3",
            parent=styles["Heading3"],
            fontName=font_name,
            fontSize=12,
            leading=18,
            spaceBefore=12,
            spaceAfter=8,
            textColor="#555555",
        )

        quote_style = ParagraphStyle(
            "ChineseQuote",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=10.5,
            leading=16,
            leftIndent=20,
            rightIndent=20,
            spaceBefore=10,
            spaceAfter=10,
            textColor="#555555",
            backColor="#f5f5f5",
            borderPadding=8,
        )

        list_style = ParagraphStyle(
            "ChineseList",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=10.5,
            leading=17,
            leftIndent=20,
            firstLineIndent=-10,
            spaceBefore=3,
            spaceAfter=3,
        )

        custom_styles = {
            "Normal": normal_style,
            "Heading1": heading1_style,
            "Heading2": heading2_style,
            "Heading3": heading3_style,
            "Quote": quote_style,
            "List": list_style,
        }

        def add_page_numbers(canvas, doc):
            """添加页码"""
            from reportlab.lib.pagesizes import A4 as PagesizeA4

            page_num = canvas.getPageNumber()
            text = f"第 {page_num} 页"
            canvas.drawRightString(PagesizeA4[0] - 2 * cm, 1.5 * cm, text)

        story.append(Paragraph(title, title_style))
        story.append(Paragraph(f"作者: {author}", author_style))
        story.append(Spacer(1, 0.5 * cm))

        self._add_markdown_to_story(story, markdown_content, custom_styles, font_name)

        doc.build(story, onFirstPage=add_page_numbers, onLaterPages=add_page_numbers)

    def _add_markdown_to_story(self, story: list, md: str, styles, font_name: str = "SimSun"):
        """将Markdown内容添加到PDF story"""

        if not md:
            return

        def calculate_col_widths(table_data, page_width=14 * cm):
            """动态计算表格列宽"""
            if not table_data or not table_data[0]:
                return None
            num_cols = len(table_data[0])
            margins = 1.6 * cm
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
                col_widths.append(max(width, 2 * cm))
            return col_widths

        def convert_mermaid_to_text(mermaid_code):
            """将Mermaid流程图转换为可读文字"""
            nodes = re.findall(r"(\w+)\[([^\]]+)\]", mermaid_code)
            node_map = dict(nodes)
            connections = re.findall(r"(\w+)\s*-->\|?([^|\]]+)\|?>?\s*(\w+)", mermaid_code)
            lines = ["【流程图】"]
            step = 1
            for from_node, label, to_node in connections:
                from_text = node_map.get(from_node, "?")
                to_text = node_map.get(to_node, "?")
                label = label.strip() if label.strip() else "执行"
                lines.append(f"{step}. {from_text} → {to_text} ({label})")
                step += 1
            if "-->|" in mermaid_code or "循环" in mermaid_code.lower():
                lines.append("→ 循环回到开始")
            return "\n".join(lines)

        md = re.sub(r"```mermaid\n?(graph \w+[\s\S]*?)```", lambda m: convert_mermaid_to_text(m.group(0)), md)

        def clean_html(text):
            text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
            text = re.sub(r"<font[^>]*>", "", text)
            text = text.replace("</font>", "")
            text = re.sub(r"<[^>]+>", "", text)
            text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
            text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
            text = re.sub(r"`(.+?)`", r'<font name="Courier">\1</font>', text)
            return text.strip()

        def create_table_style():
            return TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3498db")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("LEADING", (0, 0), (-1, -1), 14),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                    ("TOPPADDING", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
                    ("TOPPADDING", (0, 1), (-1, -1), 8),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8f9fa")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            )

        lines = md.split("\n")
        in_list = False
        in_table = False
        table_data = []

        for line in lines:
            line = line.rstrip()

            if re.match(r"^-{3,}$", line.strip()):
                continue

            if not line.strip():
                if in_list:
                    in_list = False
                    story.append(Spacer(1, 0.1 * cm))
                if in_table:
                    in_table = False
                    if table_data:
                        col_widths = calculate_col_widths(table_data)
                        t = Table(table_data, colWidths=col_widths, repeatRows=1)
                        t.setStyle(create_table_style())
                        story.append(t)
                        story.append(Spacer(1, 0.3 * cm))
                        table_data = []
                continue

            if line.strip().startswith("|") and "|" in line.strip()[1:]:
                cells = [c.strip() for c in line.strip().split("|")[1:-1]]
                is_separator = all(
                    set(c.replace("-", "").replace(":", "").replace(" ", "")) <= {"", ":"} for c in cells if c
                )
                if is_separator:
                    continue
                if not in_table:
                    in_table = True
                    table_data = []
                cleaned_cells = [Paragraph(clean_html(c), styles["Normal"]) for c in cells if c]
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
                    story.append(Spacer(1, 0.3 * cm))
                    table_data = []

            if line.startswith("### "):
                story.append(Paragraph(clean_html(line[4:]), styles["Heading3"]))
            elif line.startswith("## "):
                story.append(Paragraph(clean_html(line[3:]), styles["Heading1"]))
            elif line.startswith("# "):
                story.append(Paragraph(clean_html(line[2:]), styles["Heading2"]))
            elif line.strip().startswith("- ") or line.strip().startswith("* "):
                if not in_list:
                    story.append(Spacer(1, 0.1 * cm))
                    in_list = True
                text = clean_html(line.strip()[2:])
                list_style = styles.get("List", styles["Normal"])
                story.append(Paragraph(f"• {text}", list_style))
            elif re.match(r"^\d+\.\s", line.strip()):
                if not in_list:
                    story.append(Spacer(1, 0.1 * cm))
                    in_list = True
                text = clean_html(re.sub(r"^\d+\.\s", "", line.strip()))
                list_style = styles.get("List", styles["Normal"])
                story.append(Paragraph(f"{text}", list_style))
            elif line.startswith(">"):
                text = clean_html(line[1:].strip())
                quote_style = styles.get("Quote", styles["Normal"])
                story.append(Paragraph(f"<i>{text}</i>", quote_style))
            else:
                text = clean_html(line)
                if text:
                    story.append(Paragraph(text, styles["Normal"]))

        if in_list:
            story.append(Spacer(1, 0.1 * cm))

        if in_table and table_data:
            col_widths = calculate_col_widths(table_data)
            t = Table(table_data, colWidths=col_widths, repeatRows=1)
            t.setStyle(create_table_style())
            story.append(t)
