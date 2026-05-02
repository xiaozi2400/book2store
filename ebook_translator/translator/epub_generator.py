import os
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import shutil
import tempfile
import zipfile

def normalize_text(text):
    """标准化文本：去除多余空格，统一Unicode特殊字符"""
    if not text:
        return ""
    text = text.replace('\u2014', '-').replace('\u2013', '-')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2026', '...')
    text = ' '.join(text.split()).strip()
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
        """创建翻译映射 - 使用标准化原文作为键"""
        translation_map = {}

        for para in translated_paragraphs:
            original = para.get('original')
            translated = para.get('translated')
            if original and translated:
                normalized = normalize_text(original)
                translation_map[normalized] = {
                    'original': original,
                    'translated': translated,
                    'html': para.get('html', ''),
                    'is_duplicate': para.get('is_duplicate', False)
                }

        admonition_labels = {
            'Note': '注意', 'NOTE': '注意', 'note': '注意',
            'Tip': '提示', 'TIP': '提示', 'tip': '提示',
            'Warning': '警告', 'WARNING': '警告', 'warning': '警告',
            'Caution': '注意', 'CAUTION': '注意', 'caution': '注意',
            'Important': '重要', 'IMPORTANT': '重要', 'important': '重要',
        }
        for en, zh in admonition_labels.items():
            normalized = normalize_text(en)
            if normalized not in translation_map:
                translation_map[normalized] = {
                    'original': en, 'translated': zh,
                    'html': en, 'is_duplicate': False
                }

        return translation_map

    def _extract_non_link_text(self, tag):
        """提取标签中未被处理的纯文本部分"""
        from bs4 import NavigableString
        parts = []
        for child in tag.children:
            if isinstance(child, NavigableString):
                t = str(child).strip()
                if t:
                    parts.append(t)
            elif hasattr(child, 'name') and not child.get('data-original'):
                t = child.get_text(strip=True)
                if t:
                    parts.append(t)
        return ' '.join(parts)

    def _replace_non_link_text(self, tag, translation):
        """替换标签中非 <a> 标签的文本为翻译内容"""
        from bs4 import NavigableString
        
        # 移除所有非 <a> 标签的 NavigableString
        to_remove = []
        for child in tag.children:
            if isinstance(child, NavigableString):
                to_remove.append(child)
        
        for child in to_remove:
            child.extract()
        
        # 在第一个子元素前插入翻译文本
        first = next(tag.children, None)
        if first:
            first.insert_before(translation)
        else:
            tag.string = translation

    def _process_html_content(self, content, translation_map, mode, is_nav=False):
        """统一处理HTML内容 - 块级标签优先，避免inline标签干扰

        Args:
            content: HTML内容
            translation_map: 翻译映射（使用标准化原文作为键）
            mode: 翻译模式 ('bilingual' 或 'chinese')
            is_nav: 是否为导航文件，导航文件需要保留链接
        """
        soup = BeautifulSoup(content, 'lxml')

        total_matched = 0
        total_checked = 0
        unmatched_samples = []

        # 块级标签（先处理，blockquote最优先避免子元素先被处理）
        block_tags = ['blockquote', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'dt', 'dd',
                      'figcaption', 'td', 'th', 'caption']

        # 回退匹配列表
        fallback_list = []
        agg_sigs = {}
        for k, v in translation_map.items():
            orig = v.get('original', '')
            if orig:
                fallback_list.append((normalize_text(orig)[:80], v))
                if len(orig) > 50:
                    sig = ''.join(ch.lower() for ch in orig[:200] if ch.isalnum())
                    agg_sigs[sig] = v
        translation_list = fallback_list

        # 处理块级标签
        for tag_name in block_tags:
            for tag in soup.find_all(tag_name):
                if tag.find(class_='translated'):
                    continue

                text = tag.get_text(strip=True)
                normalized_text = normalize_text(text)
                if not normalized_text or len(normalized_text) <= 1:
                    continue

                total_checked += 1
                para_data = translation_map.get(normalized_text)

                if not para_data and len(text) > 50:
                    text_prefix = normalized_text[:80]
                    for orig_prefix, entry in translation_list:
                        if text_prefix == orig_prefix:
                            para_data = entry
                            break
                    if not para_data and agg_sigs:
                        sig = ''.join(ch.lower() for ch in text[:200] if ch.isalnum())
                        para_data = agg_sigs.get(sig)

                if not para_data:
                    if tag_name == 'blockquote':
                        from bs4 import NavigableString
                        ns_matched = False
                        for child in list(tag.children):
                            if isinstance(child, NavigableString):
                                child_text = str(child).strip()
                                child_norm = normalize_text(child_text)
                                if not child_norm or len(child_norm) <= 1:
                                    continue
                                child_data = translation_map.get(child_norm)
                                if not child_data and len(child_text) > 50:
                                    child_prefix = child_norm[:80]
                                    for orig_prefix, entry in translation_list:
                                        if child_prefix == orig_prefix:
                                            child_data = entry
                                            break
                                    if not child_data and agg_sigs:
                                        sig = ''.join(ch.lower() for ch in child_text[:200] if ch.isalnum())
                                        child_data = agg_sigs.get(sig)
                                if child_data:
                                    child.replace_with(child_data['translated'])
                                    total_matched += 1
                                    ns_matched = True
                        if ns_matched:
                            tag['data-original'] = text
                            continue
                    if len(unmatched_samples) < 10:
                        unmatched_samples.append(text[:100])
                    continue

                translation = para_data['translated']
                total_matched += 1

                tag['data-original'] = text

                if mode == 'bilingual':
                    tag.clear()
                    tag.append(text)
                    span = soup.new_tag('span')
                    span['class'] = 'translated'
                    span.string = translation
                    tag.append(' / ')
                    tag.append(span)
                else:
                    tag.clear()
                    tag.string = translation

        # 处理 <div> 标签（可能包含子块级元素，更复杂）
        for tag in soup.find_all('div'):
            if tag.find(class_='translated'):
                continue

            if any(hasattr(c, 'get') and c.get('data-original') for c in tag.children):
                continue

            text = tag.get_text(strip=True)
            normalized_text = normalize_text(text)
            if not normalized_text or len(normalized_text) <= 1:
                continue

            total_checked += 1
            para_data = translation_map.get(normalized_text)

            if not para_data and len(text) > 50:
                text_prefix = normalized_text[:80]
                for orig_prefix, entry in translation_list:
                    if text_prefix == orig_prefix:
                        para_data = entry
                        break
                if not para_data and agg_sigs:
                    sig = ''.join(ch.lower() for ch in text[:200] if ch.isalnum())
                    para_data = agg_sigs.get(sig)

            if not para_data:
                if len(unmatched_samples) < 10:
                    unmatched_samples.append(text[:100])
                continue

            translation = para_data['translated']
            total_matched += 1

            tag['data-original'] = text

            if mode == 'bilingual':
                tag.clear()
                tag.append(text)
                span = soup.new_tag('span')
                span['class'] = 'translated'
                span.string = translation
                tag.append(' / ')
                tag.append(span)
            else:
                tag.clear()
                tag.string = translation

        # 处理剩余的 inline 标签（不在已处理块级标签内的独立inline标签）
        inline_tags = ['a', 'sup', 'sub', 'em', 'i', 'b', 'strong', 'code', 'span']

        for tag_name in inline_tags:
            for tag in soup.find_all(tag_name):
                if tag.find(class_='translated'):
                    continue

                # 如果父级标签已经被处理过（有data-original），跳过
                parent = tag.parent
                if parent and parent.get('data-original'):
                    continue

                text = tag.get_text(strip=True)
                normalized_text = normalize_text(text)
                if not normalized_text or len(normalized_text) <= 1:
                    continue

                total_checked += 1
                para_data = translation_map.get(normalized_text)

                if not para_data:
                    if len(unmatched_samples) < 10:
                        unmatched_samples.append(text[:100])
                    continue

                translation = para_data['translated']
                total_matched += 1

                tag['data-original'] = text

                if tag.name == 'a' and tag.has_attr('href'):
                    if mode == 'bilingual':
                        tag.clear()
                        tag.append(text)
                        span = soup.new_tag('span')
                        span['class'] = 'translated'
                        span.string = translation
                        tag.append(' / ')
                        tag.append(span)
                    else:
                        tag.clear()
                        tag.string = translation
                elif mode == 'bilingual':
                    tag.clear()
                    tag.append(text)
                    span = soup.new_tag('span')
                    span['class'] = 'translated'
                    span.string = translation
                    tag.append(' / ')
                    tag.append(span)
                else:
                    tag.clear()
                    tag.string = translation

        # 统计日志
        if unmatched_samples:
            print(f"[{mode}] Total tags: {total_checked}, Matched: {total_matched}, "
                  f"Unmatched: {total_checked - total_matched} "
                  f"({(total_matched / total_checked * 100):.1f}%)")
            print(f"[{mode}] Unmatched samples: {unmatched_samples[:3]}")

        return str(soup)

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
                                
                                with open(file_path, 'w', encoding='utf-8') as f:
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
                                
                                with open(file_path, 'w', encoding='utf-8') as f:
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
