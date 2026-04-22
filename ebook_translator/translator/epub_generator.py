import os
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import shutil
import tempfile
import zipfile

def normalize_text(text):
    """标准化文本：去除多余空格，统一标点符号"""
    if not text:
        return ""
    # 去除多余空格
    text = ' '.join(text.split()).strip()
    # 统一引号：将智能引号转换为普通引号
    text = text.replace('\u2018', "'").replace('\u2019', "'")  # 左右单引号
    text = text.replace('\u201c', '"').replace('\u201d', '"')  # 左右双引号
    text = text.replace('\u201a', ",").replace('\u201e', ",,")  # 低单双引号
    text = text.replace('\u2032', "'").replace('\u2033', '"')  # 撇号和双撇号
    # 统一破折号
    text = text.replace('\u2014', '--').replace('\u2013', '-')
    # 统一省略号
    text = text.replace('\u2026', '...')
    return text

# 专业电子书翻译 CSS 样式
BILINGUAL_CSS = """
/* 中英对照专业样式 - 专业中文排版 */
body {
    font-family: "SimSun", "STKaiti", serif;
    font-size: 16px;
    line-height: 1.6;
    text-align: justify;
    hyphens: auto;
    -webkit-hyphens: auto;
    -epub-hyphens: auto;
    font-variant-numeric: tabular-nums;
}

/* 段落样式 - 翻译内容与原文换行显示 */
p {
    text-indent: 0;
    margin-top: 0;
    margin-bottom: 0.5em;
    text-align: justify;
}

/* 标题样式 */
h1, h2, h3, h4, h5, h6 {
    font-family: "STKaiti", "KaiTi", "SimKai", sans-serif;
    font-weight: normal;
    text-align: center;
    line-height: 1.5;
    margin-top: 1em;
    margin-bottom: 0.5em;
    page-break-after: avoid;
    -webkit-column-break-after: avoid;
}

h1 { font-size: 1.6em; }
h2 { font-size: 1.4em; }
h3 { font-size: 1.2em; }

/* 翻译内容样式 - 换行显示 */
.translated {
    display: block;
    font-size: 0.9em;
    color: #555;
    text-align: left;
    text-indent: 0;
    margin-top: 0;
    margin-bottom: 0;
    line-height: 1.6;
}

/* 表格样式 */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
    font-size: 0.9em;
}

th, td {
    border: 1px solid #ccc;
    padding: 0.5em;
    text-align: left;
}

th {
    background-color: #f5f5f5;
    font-weight: bold;
}

/* 表格标题居中 */
caption {
    text-align: center;
    padding: 0.5em;
    font-weight: bold;
}

/* 列表样式 */
ul, ol {
    padding-left: 2em;
    margin: 0.5em 0;
}

li {
    margin-bottom: 0.3em;
    line-height: 1.6;
}

/* 代码块样式 */
pre, code {
    font-family: "Courier New", monospace;
    font-size: 0.9em;
    background-color: #f5f5f5;
    padding: 0.2em 0.4em;
    border-radius: 3px;
}

pre {
    padding: 1em;
    overflow-x: auto;
    white-space: pre-wrap;
    word-wrap: break-word;
}

/* 图片样式 */
img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1em auto;
}

/* 引用样式 */
blockquote {
    margin: 1em 2em;
    padding: 0.5em 1em;
    border-left: 3px solid #ccc;
    background-color: #f9f9f9;
    font-style: italic;
}

/* 强调文本 */
strong, b {
    font-weight: bold;
}

em, i {
    font-style: italic;
}

/* 链接样式 */
a {
    color: #0066cc;
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

/* 页眉页脚 */
@page {
    margin: 1cm;
    @bottom-center {
        content: counter(page);
        font-size: 0.8em;
    }
}
"""

CHINESE_CSS = """
/* 纯中文专业样式 - 专业中文排版 */
body {
    font-family: "SimSun", "STKaiti", serif;
    font-size: 14px;
    line-height: 1.6;
    text-align: justify;
    hyphens: auto;
    -webkit-hyphens: auto;
    -epub-hyphens: auto;
    font-variant-numeric: tabular-nums;
}

/* 段落样式 - 首行缩进两个全角字符 */
p {
    text-indent: 2em;
    margin-top: 0;
    margin-bottom: 0.5em;
    text-align: justify;
}

/* 标题样式 */
h1, h2, h3, h4, h5, h6 {
    font-family: "SimHei", "PingFang Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
    font-weight: bold;
    text-align: center;
    line-height: 1.4;
    margin-top: 1em;
    margin-bottom: 0.5em;
    page-break-after: avoid;
    -webkit-column-break-after: avoid;
}

h1 { font-size: 1.6em; }
h2 { font-size: 1.4em; }
h3 { font-size: 1.2em; }

/* 表格样式 */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
    font-size: 0.9em;
}

th, td {
    border: 1px solid #ccc;
    padding: 0.5em;
    text-align: left;
}

th {
    background-color: #f5f5f5;
    font-weight: bold;
}

/* 表格标题居中 */
caption {
    text-align: center;
    padding: 0.5em;
    font-weight: bold;
}

/* 列表样式 */
ul, ol {
    padding-left: 2em;
    margin: 0.5em 0;
}

li {
    margin-bottom: 0.3em;
    line-height: 1.6;
}

/* 代码块样式 */
pre, code {
    font-family: "Courier New", monospace;
    font-size: 0.9em;
    background-color: #f5f5f5;
    padding: 0.2em 0.4em;
    border-radius: 3px;
}

pre {
    padding: 1em;
    overflow-x: auto;
    white-space: pre-wrap;
    word-wrap: break-word;
}

/* 图片样式 */
img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1em auto;
}

/* 引用样式 */
blockquote {
    margin: 1em 2em;
    padding: 0.5em 1em;
    border-left: 3px solid #ccc;
    background-color: #f9f9f9;
    font-style: italic;
}

/* 强调文本 */
strong, b {
    font-weight: bold;
}

em, i {
    font-style: italic;
}

/* 链接样式 */
a {
    color: #0066cc;
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

/* 页眉页脚 */
@page {
    margin: 1cm;
    @bottom-center {
        content: counter(page);
        font-size: 0.8em;
    }
}
"""

class EPUBGenerator:
    """EPUB 生成器 - 支持新ID映射"""

    def __init__(self, original_book, config=None):
        """初始化生成器
        
        Args:
            original_book: 原始EPUB书籍对象
            config: PDF配置字典，用于读取CSS样式设置
        """
        self.original_book = original_book
        self.config = config or {}

    def _create_translation_map(self, translated_paragraphs):
        """创建翻译映射 - 使用trans_id作为键"""
        translation_map = {}

        for para in translated_paragraphs:
            trans_id = para.get('trans_id')
            if trans_id and para.get('translated'):
                translation_map[trans_id] = {
                    'original': para['original'],
                    'translated': para['translated'],
                    'html': para.get('html', ''),
                    'is_duplicate': para.get('is_duplicate', False)
                }

        return translation_map

    def _process_html_content(self, content, translation_map, mode, is_nav=False):
        """统一处理HTML内容 - 使用data-trans-id精确匹配

        Args:
            content: HTML内容
            translation_map: 翻译映射（使用trans_id作为键）
            mode: 翻译模式 ('bilingual' 或 'chinese')
            is_nav: 是否为导航文件，导航文件需要保留链接
        """
        import hashlib
        import os

        soup = BeautifulSoup(content, 'lxml')

        # 统计变量
        total_tags = 0
        matched_tags = 0
        unmatched_samples = []

        # 定义需要处理的标签
        tags_to_process = ['a', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'dt', 'dd', 'div',
                          'figcaption', 'td', 'th', 'caption',
                          'sup', 'sub', 'em', 'i', 'b', 'strong', 'code', 'span']

        processed_count = 0

        # 应用翻译
        for tag_name in tags_to_process:
            for tag in soup.find_all(tag_name):
                # 跳过已处理的标签
                if tag.find(class_='translated'):
                    continue

                # 跳过包含 <a> 子标签的非 <a> 标签
                # 这些标签的翻译会由内部的 <a> 标签处理
                if tag_name != 'a' and tag.find('a'):
                    continue

                # 获取文本
                text = tag.get_text(strip=True)
                normalized_text = normalize_text(text)
                if not normalized_text or len(normalized_text) <= 1:
                    continue

                total_tags += 1

                # 从 translation_map 中查找匹配的翻译
                # 通过标准化后的文本精确匹配
                translation = None
                matched_trans_id = None
                for trans_id, para_data in translation_map.items():
                    if normalize_text(para_data['original']) == normalized_text:
                        translation = para_data['translated']
                        matched_trans_id = trans_id
                        break

                if not translation:
                    if len(unmatched_samples) < 10:
                        unmatched_samples.append(text[:100])
                    continue

                matched_tags += 1

                # 保存原文用于显示
                tag['data-original'] = text

                # 应用翻译
                if tag.name == 'a' and tag.has_attr('href'):
                    # <a> 标签：保留 href
                    if mode == 'bilingual':
                        # 双语：原文 + 翻译
                        tag.clear()
                        tag.append(text)
                        translated_span = soup.new_tag('span')
                        translated_span['class'] = 'translated'
                        translated_span.string = translation
                        tag.append(translated_span)
                    else:
                        # 纯中文：仅翻译
                        tag.clear()
                        tag.string = translation
                else:
                    # 其他标签
                    if mode == 'bilingual':
                        # 双语：原文 + <br/> + 翻译
                        tag.clear()
                        tag.append(text)
                        tag.append(soup.new_tag('br'))
                        translated_span = soup.new_tag('span')
                        translated_span['class'] = 'translated'
                        translated_span.string = translation
                        tag.append(translated_span)
                    else:
                        # 纯中文：仅翻译
                        tag.clear()
                        tag.string = translation

                processed_count += 1

        print(f"[{mode}] 标签统计: 总数={total_tags}, 匹配={matched_tags}, 未匹配={total_tags - matched_tags}")
        if unmatched_samples:
            print(f"[{mode}] 未匹配样本（前5个）:")
            for i, sample in enumerate(unmatched_samples[:5]):
                print(f"  {i+1}. {sample[:80]}...")

        return str(soup).encode('utf-8')

    def generate_bilingual_epub(self, translated_paragraphs, output_path):
        """生成中英对照 EPUB"""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # 提取原始 EPUB
                with zipfile.ZipFile(self.original_book.epub_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)

                # 创建翻译映射
                translation_map = self._create_translation_map(translated_paragraphs)
                print(f"翻译映射包含 {len(translation_map)} 个段落")

                # 处理所有 HTML/XHTML 文件（包括导航文件）
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        if file.endswith('.html') or file.endswith('.xhtml') or 'nav' in file.lower():
                            file_path = os.path.join(root, file)
                            try:
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read()
                                
                                # 判断是否为导航文件
                                is_nav = 'nav' in file.lower()
                                processed_content = self._process_html_content(content, translation_map, 'bilingual', is_nav)
                                
                                with open(file_path, 'wb') as f:
                                    f.write(processed_content)
                            except Exception as e:
                                print(f"处理文件 {file} 时出错: {e}")

                # 添加 CSS
                css_dir = os.path.join(temp_dir, 'styles')
                os.makedirs(css_dir, exist_ok=True)
                css_path = os.path.join(css_dir, 'translation.css')
                
                bilingual_css = """
/* 中英对照样式 */
p {
    text-indent: 2em !important;
    margin-bottom: 1em !important;
    line-height: 1.8 !important;
}

div {
    text-indent: 2em !important;
    margin-bottom: 1em !important;
    line-height: 1.8 !important;
}

.translated {
    display: block;
    color: #555;
    text-indent: 2em !important;
    margin-top: 0.5em !important;
    margin-bottom: 1em !important;
    line-height: 1.8 !important;
}

.no-jump {
    display: block;
    color: #888;
    cursor: default;
    margin-top: 0.3em !important;
}
"""
                with open(css_path, 'w', encoding='utf-8') as f:
                    f.write(bilingual_css)

                # 更新 OPF 文件
                opf_files = [f for f in os.listdir(temp_dir) if f.endswith('.opf')]
                if opf_files:
                    opf_path = os.path.join(temp_dir, opf_files[0])
                    try:
                        with open(opf_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        soup = BeautifulSoup(content, 'lxml-xml')
                        title_elem = soup.find('dc:title')
                        if title_elem:
                            title_elem.string = f"中英双语-{title_elem.string}"
                        
                        # 添加 CSS 引用
                        for root, dirs, files in os.walk(temp_dir):
                            for file in files:
                                if file.endswith('.html') or file.endswith('.xhtml'):
                                    file_path = os.path.join(root, file)
                                    try:
                                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                            html_content = f.read()
                                        
                                        html_soup = BeautifulSoup(html_content, 'lxml')
                                        head = html_soup.find('head')
                                        if head:
                                            css_link = html_soup.find('link', href='styles/translation.css')
                                            if not css_link:
                                                new_link = html_soup.new_tag('link')
                                                new_link['rel'] = 'stylesheet'
                                                new_link['type'] = 'text/css'
                                                new_link['href'] = 'styles/translation.css'
                                                head.append(new_link)
                                        
                                        with open(file_path, 'w', encoding='utf-8') as f:
                                            f.write(str(html_soup))
                                    except Exception as e:
                                        print(f"添加CSS到 {file} 时出错: {e}")
                        
                        with open(opf_path, 'w', encoding='utf-8') as f:
                            f.write(str(soup))
                    except Exception as e:
                        print(f"更新 OPF 时出错: {e}")

                # 重新打包
                with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, temp_dir)
                            zip_ref.write(file_path, arcname)

                print(f"成功生成 EPUB 文件: {output_path}")
                return True

        except Exception as e:
            print(f"生成中英对照 EPUB 时出错: {e}")
            import traceback
            traceback.print_exc()
            return False

    def generate_chinese_epub(self, translated_paragraphs, output_path):
        """生成纯中文 EPUB"""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # 提取原始 EPUB
                with zipfile.ZipFile(self.original_book.epub_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)

                # 创建翻译映射
                translation_map = self._create_translation_map(translated_paragraphs)

                # 处理所有 HTML/XHTML 文件（包括导航文件）
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        if file.endswith('.html') or file.endswith('.xhtml') or 'nav' in file.lower():
                            file_path = os.path.join(root, file)
                            try:
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read()
                                
                                # 判断是否为导航文件
                                is_nav = 'nav' in file.lower()
                                processed_content = self._process_html_content(content, translation_map, 'chinese', is_nav)
                                
                                with open(file_path, 'wb') as f:
                                    f.write(processed_content)
                            except Exception as e:
                                print(f"处理文件 {file} 时出错: {e}")

                # 添加 CSS
                css_dir = os.path.join(temp_dir, 'styles')
                os.makedirs(css_dir, exist_ok=True)
                css_path = os.path.join(css_dir, 'chinese_style.css')
                
                # 从配置读取CSS样式
                css_config = self.config.get('css', {})
                
                chinese_css = f"""/* 纯中文段落样式 - 优化阅读体验 */
/* 从配置文件 pdf_config.json 加载 */

p {{
    text-indent: {css_config.get('paragraph_text_indent', '2em')} !important;
    margin-top: 0 !important;
    margin-bottom: {css_config.get('paragraph_margin_bottom', '1.5em')} !important;
    text-align: justify !important;
    line-height: {css_config.get('paragraph_line_height', '1.8')} !important;
}}

div {{
    text-indent: {css_config.get('paragraph_text_indent', '2em')} !important;
    margin-bottom: {css_config.get('paragraph_margin_bottom', '1.5em')} !important;
    line-height: {css_config.get('paragraph_line_height', '1.8')} !important;
}}

/* 章节标题样式 */
h1, h2, h3, h4, h5, h6 {{
    margin-top: {css_config.get('heading_margin_top', '1.5em')} !important;
    margin-bottom: {css_config.get('heading_margin_bottom', '1em')} !important;
    line-height: 1.4 !important;
}}

/* 列表项样式 */
li {{
    margin-bottom: {css_config.get('list_item_margin_bottom', '0.8em')} !important;
    line-height: {css_config.get('paragraph_line_height', '1.8')} !important;
}}

/* 引用块样式 */
blockquote {{
    margin-top: {css_config.get('blockquote_margin', '1.5em')} !important;
    margin-bottom: {css_config.get('blockquote_margin', '1.5em')} !important;
    padding-left: {css_config.get('blockquote_padding_left', '1.5em')} !important;
    border-left: {css_config.get('blockquote_border_left', '3px solid #ccc')} !important;
    line-height: {css_config.get('paragraph_line_height', '1.8')} !important;
}}
"""
                with open(css_path, 'w', encoding='utf-8') as f:
                    f.write(chinese_css)

                # 更新 OPF 文件
                opf_files = [f for f in os.listdir(temp_dir) if f.endswith('.opf')]
                if opf_files:
                    opf_path = os.path.join(temp_dir, opf_files[0])
                    try:
                        with open(opf_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        soup = BeautifulSoup(content, 'lxml-xml')
                        title_elem = soup.find('dc:title')
                        if title_elem:
                            title_elem.string = f"中文版本-{title_elem.string}"
                        
                        # 添加 CSS 引用
                        for root, dirs, files in os.walk(temp_dir):
                            for file in files:
                                if file.endswith('.html') or file.endswith('.xhtml'):
                                    file_path = os.path.join(root, file)
                                    try:
                                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                            html_content = f.read()
                                        
                                        html_soup = BeautifulSoup(html_content, 'lxml')
                                        head = html_soup.find('head')
                                        if head:
                                            css_link = html_soup.find('link', href='styles/chinese_style.css')
                                            if not css_link:
                                                new_link = html_soup.new_tag('link')
                                                new_link['rel'] = 'stylesheet'
                                                new_link['type'] = 'text/css'
                                                new_link['href'] = 'styles/chinese_style.css'
                                                head.append(new_link)
                                        
                                        with open(file_path, 'w', encoding='utf-8') as f:
                                            f.write(str(html_soup))
                                    except Exception as e:
                                        print(f"添加CSS到 {file} 时出错: {e}")
                        
                        with open(opf_path, 'w', encoding='utf-8') as f:
                            f.write(str(soup))
                    except Exception as e:
                        print(f"更新 OPF 时出错: {e}")

                # 重新打包
                with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, temp_dir)
                            zip_ref.write(file_path, arcname)

                print(f"成功生成 EPUB 文件: {output_path}")
                return True

        except Exception as e:
            print(f"生成纯中文 EPUB 时出错: {e}")
            import traceback
            traceback.print_exc()
            return False
