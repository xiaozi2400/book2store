import os
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import shutil
import tempfile

def normalize_text(text):
    """标准化文本：去除多余空格"""
    if not text:
        return ""
    return ' '.join(text.split()).strip()

# 专业电子书翻译 CSS 样式
BILINGUAL_CSS = """
/* 中英对照专业样式 - 专业中文排版 */
body {
    font-family: "SimSun", "Source Han Serif SC", "Noto Serif CJK SC", serif;
    font-size: 16px;
    line-height: 1.6;
    text-align: justify;
    hyphens: auto;
    -webkit-hyphens: auto;
    -epub-hyphens: auto;
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
    font-family: "SimHei", "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
    font-weight: bold;
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
    font-family: "SimSun", "Source Han Serif SC", "Noto Serif CJK SC", serif;
    font-size: 14px;
    line-height: 1.6;
    text-align: justify;
    hyphens: auto;
    -webkit-hyphens: auto;
    -epub-hyphens: auto;
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
    font-family: "SimHei", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
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
    """EPUB 生成器"""

    def __init__(self, original_book):
        """初始化生成器"""
        self.original_book = original_book

    def _process_html_content(self, content, translation_map, mode):
        """统一处理HTML内容"""
        soup = BeautifulSoup(content, 'lxml')
        
        # 定义需要处理的标签，按优先级排序（先处理内层标签）
        tags_to_process = [
            'a', 'sup', 'sub', 'em', 'i', 'b', 'strong', 'code', 'span',  # 内联标签
            'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'dt', 'dd', 'div'  # 块级标签
        ]
        
        processed_tags = set()
        
        # 多遍处理，确保嵌套标签都被处理
        for _ in range(3):  # 最多3遍
            for tag_name in tags_to_process:
                for tag in soup.find_all(tag_name):
                    if id(tag) in processed_tags:
                        continue
                    
                    # 跳过已翻译的标签
                    if tag.find(class_='translated') or 'translated' in tag.get('class', []):
                        processed_tags.add(id(tag))
                        continue
                    
                    # 获取纯文本内容
                    text = tag.get_text(strip=True)
                    normalized_text = normalize_text(text)
                    
                    if not normalized_text or len(normalized_text) <= 1:
                        processed_tags.add(id(tag))
                        continue
                    
                    # 查找翻译
                    translation = translation_map.get(normalized_text)
                    if not translation:
                        continue
                    
                    # 应用翻译
                    if mode == 'bilingual':
                        # 保留原始属性（如链接href）
                        original_attrs = dict(tag.attrs)
                        original_text = text
                        
                        tag.clear()
                        tag.append(original_text)
                        tag.append(soup.new_tag('br'))
                        translated_span = soup.new_tag('span')
                        translated_span['class'] = 'translated'
                        translated_span.string = translation
                        tag.append(translated_span)
                        
                        # 恢复原始属性（除了class）
                        for attr, value in original_attrs.items():
                            if attr != 'class':
                                tag[attr] = value
                    else:
                        # 纯中文模式：保留属性，替换文本
                        original_attrs = {k: v for k, v in tag.attrs.items() if k != 'class'}
                        tag.string = translation
                        for attr, value in original_attrs.items():
                            tag[attr] = value
                    
                    processed_tags.add(id(tag))
        
        # 清理分隔符
        for text_node in soup.find_all(text=True):
            if '===DEEPSEEK_BATCH_SEPARATOR===' in text_node:
                text_node.replace_with(text_node.replace('===DEEPSEEK_BATCH_SEPARATOR===', ''))
        
        return soup.prettify().encode('utf-8')

    def _process_toc_content(self, content, translation_map, mode):
        """处理目录内容，保留链接结构"""
        soup = BeautifulSoup(content, 'lxml')

        all_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'span', 'div', 'a', 'sup', 'sub', 'em', 'i', 'b', 'strong']
        processed_tags = set()

        # 第一遍：处理所有标签，从最内层开始
        for tag_name in reversed(all_tags):
            for tag in soup.find_all(tag_name):
                if id(tag) in processed_tags:
                    continue
                    
                if tag.find(class_='translated'):
                    processed_tags.add(id(tag))
                    continue
                
                # 检查是否有子标签需要优先处理
                has_unprocessed_child = False
                for child in tag.find_all(True):
                    if child.name in all_tags and id(child) not in processed_tags:
                        has_unprocessed_child = True
                        break
                
                if has_unprocessed_child:
                    continue
                
                text = tag.get_text(strip=True)
                normalized_text = normalize_text(text)
                
                if normalized_text and normalized_text in translation_map:
                    translation = translation_map[normalized_text]
                    
                    if mode == 'bilingual':
                        # 对于链接标签，保留链接但添加翻译
                        if tag.name == 'a':
                            href = tag.get('href', '')
                            tag.clear()
                            tag.append(text)
                            tag.append(soup.new_tag('br'))
                            translated_span = soup.new_tag('span')
                            translated_span['class'] = 'translated'
                            translated_span.string = translation
                            tag.append(translated_span)
                            if href:
                                tag['href'] = href
                        else:
                            original_text = text
                            tag.clear()
                            tag.append(original_text)
                            tag.append(soup.new_tag('br'))
                            translated_span = soup.new_tag('span')
                            translated_span['class'] = 'translated'
                            translated_span.string = translation
                            tag.append(translated_span)
                    else:
                        # 纯中文模式：替换文本但保留链接属性
                        if tag.name == 'a':
                            href = tag.get('href', '')
                            tag.string = translation
                            if href:
                                tag['href'] = href
                        else:
                            tag.string = translation
                    
                    processed_tags.add(id(tag))
        
        # 第二遍：处理剩余的标签
        for tag_name in all_tags:
            for tag in soup.find_all(tag_name):
                if id(tag) in processed_tags:
                    continue
                    
                if tag.find(class_='translated'):
                    processed_tags.add(id(tag))
                    continue
                
                text = tag.get_text(strip=True)
                normalized_text = normalize_text(text)
                
                if normalized_text and normalized_text in translation_map:
                    translation = translation_map[normalized_text]
                    
                    if mode == 'bilingual':
                        if tag.name == 'a':
                            href = tag.get('href', '')
                            tag.clear()
                            tag.append(text)
                            tag.append(soup.new_tag('br'))
                            translated_span = soup.new_tag('span')
                            translated_span['class'] = 'translated'
                            translated_span.string = translation
                            tag.append(translated_span)
                            if href:
                                tag['href'] = href
                        else:
                            original_text = text
                            tag.clear()
                            tag.append(original_text)
                            tag.append(soup.new_tag('br'))
                            translated_span = soup.new_tag('span')
                            translated_span['class'] = 'translated'
                            translated_span.string = translation
                            tag.append(translated_span)
                    else:
                        if tag.name == 'a':
                            href = tag.get('href', '')
                            tag.string = translation
                            if href:
                                tag['href'] = href
                        else:
                            tag.string = translation
                    processed_tags.add(id(tag))

        for text_node in soup.find_all(text=True):
            if '===DEEPSEEK_BATCH_SEPARATOR===' in text_node:
                text_node.replace_with(text_node.replace('===DEEPSEEK_BATCH_SEPARATOR===', ''))

        return soup.prettify().encode('utf-8')

    def generate_bilingual_epub(self, translated_paragraphs, output_path):
        """生成中英对照 EPUB"""
        try:
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                # 提取原始 EPUB 到临时目录
                import zipfile
                with zipfile.ZipFile(self.original_book.epub_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)

                # 创建翻译映射 - 使用标准化文本作为键
                translation_map = {}
                for para in translated_paragraphs:
                    if para['original'] and para['translated']:
                        # 使用标准化文本作为键
                        normalized_key = normalize_text(para['original'])
                        translation_map[normalized_key] = para['translated']

                # 处理所有 HTML 文件，包括目录文件
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        if file.endswith('.html') or file.endswith('.xhtml'):
                            file_path = os.path.join(root, file)
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                            
                            # 处理内容，保留链接结构
                            processed_content = self._process_html_content(content, translation_map, 'bilingual')
                            
                            # 写回文件
                            with open(file_path, 'wb') as f:
                                f.write(processed_content)

                # 添加自定义 CSS 文件 - 只添加翻译相关的小样式，不覆盖原有样式
                css_dir = os.path.join(temp_dir, 'styles')
                if not os.path.exists(css_dir):
                    os.makedirs(css_dir)
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
"""
                with open(css_path, 'w', encoding='utf-8') as f:
                    f.write(bilingual_css)

                # 更新 OPF 文件
                opf_files = [f for f in os.listdir(temp_dir) if f.endswith('.opf')]
                if opf_files:
                    opf_path = os.path.join(temp_dir, opf_files[0])
                    with open(opf_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # 更新标题
                    soup = BeautifulSoup(content, 'lxml')
                    title_elem = soup.find('dc:title')
                    if title_elem:
                        title_elem.string = f"中英双语-{title_elem.string}"
                    
                    # 添加 CSS 引用到所有 HTML 文件（如果还没有的话）
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            if file.endswith('.html') or file.endswith('.xhtml'):
                                file_path = os.path.join(root, file)
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    html_content = f.read()
                                
                                html_soup = BeautifulSoup(html_content, 'lxml')
                                head = html_soup.find('head')
                                if head:
                                    # 检查是否已有翻译 CSS 引用
                                    css_link = html_soup.find('link', href='styles/translation.css')
                                    if not css_link:
                                        new_link = html_soup.new_tag('link')
                                        new_link['rel'] = 'stylesheet'
                                        new_link['type'] = 'text/css'
                                        new_link['href'] = 'styles/translation.css'
                                        head.append(new_link)
                                
                                with open(file_path, 'w', encoding='utf-8') as f:
                                    f.write(str(html_soup))
                    
                    # 写回 OPF 文件
                    with open(opf_path, 'w', encoding='utf-8') as f:
                        f.write(soup.prettify())

                # 重新打包为 EPUB
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
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                # 提取原始 EPUB 到临时目录
                import zipfile
                with zipfile.ZipFile(self.original_book.epub_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)

                # 创建翻译映射 - 使用标准化文本作为键
                translation_map = {}
                for para in translated_paragraphs:
                    if para['original'] and para['translated']:
                        # 使用标准化文本作为键
                        normalized_key = normalize_text(para['original'])
                        translation_map[normalized_key] = para['translated']

                # 处理所有 HTML 文件，包括目录文件
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        if file.endswith('.html') or file.endswith('.xhtml'):
                            file_path = os.path.join(root, file)
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                            
                            # 处理内容，保留链接结构
                            processed_content = self._process_html_content(content, translation_map, 'chinese')
                            
                            # 写回文件
                            with open(file_path, 'wb') as f:
                                f.write(processed_content)

                css_dir = os.path.join(temp_dir, 'styles')
                if not os.path.exists(css_dir):
                    os.makedirs(css_dir)
                css_path = os.path.join(css_dir, 'chinese_style.css')
                chinese_css = """
/* 纯中文段落首行缩进 - 使用 !important 确保优先级 */
p {
    text-indent: 2em !important;
    margin-top: 0 !important;
    margin-bottom: 1em !important;
    text-align: justify !important;
    line-height: 1.8 !important;
}

div {
    text-indent: 2em !important;
    margin-bottom: 1em !important;
    line-height: 1.8 !important;
}
"""
                with open(css_path, 'w', encoding='utf-8') as f:
                    f.write(chinese_css)

                # 更新 OPF 文件
                opf_files = [f for f in os.listdir(temp_dir) if f.endswith('.opf')]
                if opf_files:
                    opf_path = os.path.join(temp_dir, opf_files[0])
                    with open(opf_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # 更新标题
                    soup = BeautifulSoup(content, 'lxml')
                    title_elem = soup.find('dc:title')
                    if title_elem:
                        title_elem.string = f"中文版本-{title_elem.string}"
                    
                    # 添加 CSS 引用到所有 HTML 文件
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            if file.endswith('.html') or file.endswith('.xhtml'):
                                file_path = os.path.join(root, file)
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
                    
                    # 写回 OPF 文件
                    with open(opf_path, 'w', encoding='utf-8') as f:
                        f.write(soup.prettify())

                # 重新打包为 EPUB
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
