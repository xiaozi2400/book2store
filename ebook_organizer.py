import os
import re
import shutil
import sys
import hashlib
import argparse
import warnings

# 可选依赖，用于PDF和EPUB解析
try:
    import PyPDF2
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    warnings.warn("PyPDF2未安装，PDF文件解析功能不可用。请使用 'pip install PyPDF2' 安装。")

try:
    import ebooklib
    from ebooklib import epub
    EPUB_SUPPORT = True
except ImportError:
    EPUB_SUPPORT = False
    warnings.warn("ebooklib未安装，EPUB文件解析功能不可用。请使用 'pip install ebooklib' 安装。")


def calculate_file_hash(filepath, block_size=65536):
    """计算文件的MD5哈希值，用于检测重复文件"""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        buf = f.read(block_size)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(block_size)
    return hasher.hexdigest()


def is_text_page(text, min_chars=100, min_words=10):
    """判断文本是否来自真正的文本页面（而非封面、版权页等）"""
    if not text:
        return False
    
    # 清理文本：去除空格和换行
    cleaned_text = re.sub(r'\s+', '', text).strip()
    
    # 检查字符数
    if len(cleaned_text) < min_chars:
        return False
    
    # 检查单词数（粗略估计）
    words = re.findall(r'\w+', text)
    if len(words) < min_words:
        return False
    
    # 检查是否包含过多的特殊字符或数字（可能是目录、页码等）
    special_char_ratio = len(re.findall(r'[^\w\s]', text)) / max(len(text), 1)
    if special_char_ratio > 0.5:
        return False
    
    return True


def is_toc_page(text):
    """判断页面是否为目录页"""
    if not text:
        return False
    
    # 目录页关键词（中英文）
    toc_keywords = [
        '目录', 'contents', 'table of contents', '章节', 'chapter',
        'contents:', '目录:', '章', '节', 'part', '部分'
    ]
    
    # 清理文本并转为小写
    cleaned_text = text.lower().strip()
    
    # 检查是否包含目录关键词
    for keyword in toc_keywords:
        if keyword.lower() in cleaned_text:
            # 同时检查是否有章节列表特征（数字+标题模式）
            # 目录通常包含章节编号和标题的模式
            if re.search(r'\d+\s+[\u4e00-\u9fff]+', text) or re.search(r'\d+\s+[a-zA-Z]+', text):
                return True
            # 如果有目录关键词且文本较长，也认为是目录页
            if len(text) > 200:
                return True
    return False


def _extract_pdf_text(filepath, target_text_pages=2, max_total_pages=10):
    """从PDF文件提取文本页面，优先使用目录页"""
    if not PDF_SUPPORT:
        print(f"警告: PyPDF2未安装，跳过PDF文件 {filepath}")
        return ""
    
    try:
        text = ""
        text_pages_found = 0
        toc_text = ""  # 目录页文本
        
        with open(filepath, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            total_pages = min(len(pdf_reader.pages), max_total_pages)
            
            # 第一遍：查找目录页
            for i in range(total_pages):
                page = pdf_reader.pages[i]
                page_text = page.extract_text()
                if is_toc_page(page_text):
                    toc_text = page_text
                    break
            
            # 如果找到目录页，优先使用目录页进行判断
            if toc_text:
                print("    找到目录页，使用目录页进行语言判断")
                return toc_text
            
            # 如果没有找到目录页，使用普通文本页面
            for i in range(total_pages):
                if text_pages_found >= target_text_pages:
                    break
                    
                page = pdf_reader.pages[i]
                page_text = page.extract_text()
                
                if is_text_page(page_text):
                    text += page_text + "\n"
                    text_pages_found += 1
        
        return text
    except Exception as e:
        print(f"读取PDF文件 {filepath} 时出错: {e}")
        return ""


def _extract_epub_text(filepath, target_text_pages=2, max_total_pages=10):
    """从EPUB文件提取文本页面，优先使用目录页"""
    if not EPUB_SUPPORT:
        print(f"警告: ebooklib未安装，跳过EPUB文件 {filepath}")
        return ""
    
    try:
        text = ""
        text_pages_found = 0
        items_checked = 0
        toc_text = ""  # 目录页文本
        
        book = epub.read_epub(filepath)
        
        # 第一遍：查找目录页
        for item in book.get_items():
            if items_checked >= max_total_pages:
                break
                
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                items_checked += 1
                content = item.get_content().decode('utf-8', errors='ignore')
                content = re.sub(r'<[^>]+>', ' ', content)
                content = re.sub(r'\s+', ' ', content).strip()
                
                if is_toc_page(content):
                    toc_text = content
                    break
        
        # 如果找到目录页，优先使用目录页进行判断
        if toc_text:
            print("    找到目录页，使用目录页进行语言判断")
            return toc_text
        
        # 如果没有找到目录页，使用普通文本页面
        items_checked = 0
        for item in book.get_items():
            if text_pages_found >= target_text_pages or items_checked >= max_total_pages:
                break
                
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                items_checked += 1
                content = item.get_content().decode('utf-8', errors='ignore')
                content = re.sub(r'<[^>]+>', ' ', content)
                content = re.sub(r'\s+', ' ', content).strip()
                
                if is_text_page(content):
                    text += content + "\n"
                    text_pages_found += 1
        
        return text
    except Exception as e:
        print(f"读取EPUB文件 {filepath} 时出错: {e}")
        return ""


def extract_text(filepath, target_text_pages=2):
    """提取文件的文本内容，跳过非文本页面"""
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == '.pdf':
        return _extract_pdf_text(filepath, target_text_pages)
    elif ext == '.epub':
        return _extract_epub_text(filepath, target_text_pages)
    else:
        return ""


def detect_language(text):
    """
    检测文本语言：中文版本、英文版本、中英双语
    
    判断规则：
    - 中文字符占比 >= 90% → 中文版本（只允许极少量英文如书名、专有名词）
    - 英文字符占比 >= 90% → 英文版本
    - 中英文都存在且各自占比 >= 10% → 中英双语（中英文对照书籍）
    - 其他情况根据占比高的判断
    
    参数:
        text: 要检测的文本
    
    返回:
        'zh': 中文版本（允许少量英文）
        'en': 英文版本
        'zh-en': 中英双语
        None: 无法确定
    """
    if not text:
        return None
    
    # 检测中文字符（Unicode范围）
    zh_pattern = re.compile(r'[\u4e00-\u9fff]')
    chinese_chars = zh_pattern.findall(text)
    chinese_count = len(chinese_chars)
    
    # 检测英文字母
    en_pattern = re.compile(r'[a-zA-Z]')
    english_chars = en_pattern.findall(text)
    english_count = len(english_chars)
    
    # 计算总字符数（只考虑中文和英文）
    total_relevant = chinese_count + english_count
    
    if total_relevant == 0:
        return None
    
    # 计算占比
    zh_ratio = chinese_count / total_relevant
    en_ratio = english_count / total_relevant
    
    # 判断规则
    if zh_ratio >= 0.9:
        # 中文字符占90%以上 → 中文版本（允许极少量英文）
        return 'zh'
    elif en_ratio >= 0.9:
        # 英文字符占90%以上 → 英文版本
        return 'en'
    elif chinese_count > 0 and english_count > 0:
        # 中英文都存在且都有一定比例 → 中英双语
        # 只要中英文都超过10%就认为是双语
        if zh_ratio >= 0.1 and en_ratio >= 0.1:
            return 'zh-en'
        # 如果一方占比极低，按占比高的判断
        elif zh_ratio > en_ratio:
            return 'zh'
        else:
            return 'en'
    elif chinese_count > 0:
        return 'zh'
    elif english_count > 0:
        return 'en'
    else:
        return None


def collect_all_ebooks(root_dir):
    """递归收集所有子目录中的PDF和EPUB文件"""
    ebooks = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.lower().endswith(('.pdf', '.epub')):
                filepath = os.path.join(dirpath, filename)
                ebooks.append((filepath, dirpath, filename))
    return ebooks


def extract_book_title(filename):
    """
    从文件名中提取书名
    去除语言前缀、版本信息等，只保留核心书名
    """
    # 移除语言前缀
    prefixes = ['中文版本-', '英文版本-', '中英双语-']
    for prefix in prefixes:
        if filename.startswith(prefix):
            filename = filename[len(prefix):]
            break
    
    # 提取主文件名（不含扩展名）
    base_name = os.path.splitext(filename)[0]
    
    # 移除版本信息（如 -- Author Name, 1.0, etc.）
    # 处理常见的分隔符
    for delimiter in [' -- ', ' - ', '_', '.', ' ']:
        if delimiter in base_name:
            # 取第一个分隔符前的部分作为书名
            parts = base_name.split(delimiter)
            # 选择最合理的书名部分（通常是第一个部分）
            # 但需要避免选择太短的部分
            for i, part in enumerate(parts):
                if len(part) > 2:  # 至少3个字符
                    return part.strip()
    
    # 如果没有找到合适的分隔符，返回整个基名
    return base_name.strip()


def organize_ebooks(source_dir, output_dir=None, dry_run=False):
    """
    组织电子书文件：
    1. 将所有电子书按书名分类存放
    2. PDF和EPUB分开存放在 书名+格式名称 的文件夹中
    3. 删除重复文件
    4. 检测语言并添加前缀
    """
    original_cwd = os.getcwd()
    
    try:
        # 收集所有电子书
        ebooks = collect_all_ebooks(source_dir)
        print(f"找到 {len(ebooks)} 个电子书文件")
        
        if not ebooks:
            print("没有找到任何电子书文件")
            return
        
        # 步骤1：为每个文件创建书名目录结构并移动文件
        print("\n步骤1：按书名和格式分类存放电子书...")
        moved_files = []
        
        for filepath, dirpath, filename in ebooks:
            # 提取书名
            book_title = extract_book_title(filename)
            if not book_title:
                book_title = "Unknown"
            
            # 获取文件扩展名
            ext = os.path.splitext(filename)[1].lower()
            
            # 确定格式目录名称
            if ext == '.pdf':
                format_name = 'PDF'
            elif ext == '.epub':
                format_name = 'EPUB'
            else:
                format_name = 'Other'
            
            # 创建书名+格式的目录路径
            if output_dir is None:
                # 使用书名作为输出目录名
                book_dir = os.path.join(source_dir, book_title)
            else:
                book_dir = os.path.join(output_dir, book_title)
            
            # 格式目录：书名+格式名称
            format_dir = os.path.join(book_dir, f"{book_title}-{format_name}")
            
            # 创建目录结构
            if not os.path.exists(book_dir) and not dry_run:
                os.makedirs(book_dir)
                print(f"创建目录: {book_dir}")
            elif dry_run and not os.path.exists(book_dir):
                print(f"[干运行] 创建目录: {book_dir}")
            
            if not os.path.exists(format_dir) and not dry_run:
                os.makedirs(format_dir)
                print(f"创建目录: {format_dir}")
            elif dry_run and not os.path.exists(format_dir):
                print(f"[干运行] 创建目录: {format_dir}")
            
            # 目标文件路径
            new_path = os.path.join(format_dir, filename)
            
            # 处理文件名冲突
            if os.path.exists(new_path):
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(os.path.join(format_dir, f"{base}_{counter}{ext}")):
                    counter += 1
                new_path = os.path.join(format_dir, f"{base}_{counter}{ext}")
            
            # 移动文件
            if dry_run:
                print(f"  [干运行] 移动: {filepath} -> {new_path}")
            else:
                shutil.move(filepath, new_path)
                print(f"  移动: {filepath} -> {new_path}")
            
            moved_files.append((new_path, os.path.basename(new_path), format_dir))
        
        # 步骤2：检测并删除重复文件
        print("\n步骤2：检测并删除重复文件...")
        file_hashes = {}
        duplicates = []
        
        for filepath, filename, format_dir in moved_files:
            if dry_run:
                hash_val = "DRY_RUN_HASH"
            else:
                hash_val = calculate_file_hash(filepath)
            
            if hash_val in file_hashes:
                duplicates.append((filepath, file_hashes[hash_val]))
            else:
                file_hashes[hash_val] = filepath
        
        if duplicates:
            print(f"  发现 {len(duplicates)} 组重复文件:")
            for duplicate, original in duplicates:
                print(f"    删除重复: {os.path.basename(duplicate)} (重复于 {os.path.basename(original)})")
                if not dry_run:
                    os.remove(duplicate)
        else:
            print("  未发现重复文件")
        
        # 步骤3：检测语言并添加前缀
        print("\n步骤3：检测语言并添加前缀...")
        
        # 前缀映射
        prefix_map = {
            'zh': '中文版本-',
            'en': '英文版本-',
            'zh-en': '中英双语-'
        }
        
        for filepath, filename, format_dir in moved_files:
            # 跳过已删除的重复文件
            if not os.path.exists(filepath):
                continue
            
            # 检查是否已有前缀
            existing_prefix = None
            name_without_prefix = filename
            for prefix in prefix_map.values():
                if filename.startswith(prefix):
                    existing_prefix = prefix
                    name_without_prefix = filename[len(prefix):]
                    break
            
            print(f"  处理: {filename}")
            
            # 提取文本（跳过非文本页面，优先使用目录页）
            text = extract_text(filepath, target_text_pages=2)
            if not text:
                print("    警告: 无法提取足够文本内容，跳过")
                continue
            
            # 检测语言
            lang = detect_language(text)
            if lang is None:
                print("    警告: 无法检测语言，跳过")
                continue
            
            # 确定正确的前缀
            correct_prefix = prefix_map.get(lang)
            if not correct_prefix:
                continue
            
            # 如果已有前缀且正确，则无需修改
            if existing_prefix == correct_prefix:
                print(f"    前缀正确，无需修改")
                continue
            
            # 构建新文件名（使用正确的前缀）
            if existing_prefix:
                # 已有前缀但不正确，替换为正确的前缀
                new_name = correct_prefix + name_without_prefix
            else:
                # 没有前缀，添加正确的前缀
                new_name = correct_prefix + filename
            
            new_path = os.path.join(format_dir, new_name)
            
            # 避免文件名冲突
            if os.path.exists(new_path) and new_path != filepath:
                base, ext = os.path.splitext(new_name)
                counter = 1
                while os.path.exists(os.path.join(format_dir, f"{base}_{counter}{ext}")):
                    counter += 1
                new_path = os.path.join(format_dir, f"{base}_{counter}{ext}")
            
            if dry_run:
                print(f"    [干运行] 重命名: {filename} -> {os.path.basename(new_path)}")
            else:
                os.rename(filepath, new_path)
                print(f"    重命名: {filename} -> {os.path.basename(new_path)}")
        
        # 步骤4：删除不包含电子书的文件夹
        print("\n步骤4：删除不包含电子书的文件夹...")
        
        # 收集所有包含电子书的目录
        ebook_dirs = set()
        for filepath, filename, format_dir in moved_files:
            if os.path.exists(filepath):
                # 添加书名目录和格式目录到保护列表
                book_dir = os.path.dirname(format_dir)
                ebook_dirs.add(os.path.abspath(book_dir))
                ebook_dirs.add(os.path.abspath(format_dir))
        
        for dirpath, dirnames, filenames in os.walk(source_dir, topdown=False):
            dir_abs = os.path.abspath(dirpath)
            
            # 跳过包含电子书的目录
            if dir_abs in ebook_dirs:
                continue
            
            # 检查是否包含电子书文件
            has_ebook = False
            for filename in filenames:
                if filename.lower().endswith(('.pdf', '.epub')):
                    has_ebook = True
                    break
            
            # 检查子目录是否包含电子书
            for subdir in dirnames:
                subdir_path = os.path.join(dirpath, subdir)
                for root, _, files in os.walk(subdir_path):
                    for filename in files:
                        if filename.lower().endswith(('.pdf', '.epub')):
                            has_ebook = True
                            break
                    if has_ebook:
                        break
            
            if not has_ebook:
                if dry_run:
                    print(f"  [干运行] 删除不包含电子书的文件夹: {dirpath}")
                else:
                    # 删除文件夹及其内容
                    shutil.rmtree(dirpath)
                    print(f"  删除不包含电子书的文件夹: {dirpath}")
        
        print("\n处理完成！")
        
    finally:
        os.chdir(original_cwd)


def main():
    parser = argparse.ArgumentParser(description='组织电子书文件')
    parser.add_argument('directory', nargs='?', default='.',
                        help='要处理的目录（默认为当前目录）')
    parser.add_argument('--output', '-o',
                        help='输出目录（默认为源目录下的organized_books文件夹）')
    parser.add_argument('--dry-run', action='store_true',
                        help='干运行模式，只显示将要执行的操作而不实际执行')
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.directory):
        print(f"错误：目录 '{args.directory}' 不存在")
        sys.exit(1)
    
    organize_ebooks(args.directory, args.output, args.dry_run)


if __name__ == "__main__":
    main()
