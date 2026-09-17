import os
import re
import shutil
import sys
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


def truncate_at_second_dash(filename):
    """
    在第二个'--'处截断文件名，保留扩展名。
    如果找不到第二个'--'，则返回原文件名。
    """
    basename, ext = os.path.splitext(filename)
    dash_count = 0
    for i, char in enumerate(basename):
        if basename[i:i+2] == '--':
            dash_count += 1
            if dash_count == 2:
                new_basename = basename[:i].rstrip()
                return new_basename + ext
    return filename


def extract_words(text):
    """提取文本中的单词，返回小写单词集合"""
    words = re.findall(r'\w+', text.lower())
    return set(words)


def similarity(set1, set2):
    """计算两个单词集合的相似度（重叠比例）"""
    if not set1 or not set2:
        return 0.0
    intersection = set1.intersection(set2)
    max_size = max(len(set1), len(set2))
    return len(intersection) / max_size


def safe_move(src, dst, dry_run=False):
    """安全移动文件，支持干运行模式"""
    if dry_run:
        print(f"[干运行] 移动: {src} -> {dst}")
        return
    try:
        shutil.move(src, dst)
        print(f"移动: {src} -> {dst}")
    except Exception as e:
        print(f"移动文件时出错 {src}: {e}")
        raise


def safe_rename(src, dst, dry_run=False):
    """安全重命名文件，支持干运行模式"""
    if dry_run:
        print(f"[干运行] 重命名: {src} -> {dst}")
        return
    try:
        os.rename(src, dst)
        print(f"重命名: {src} -> {dst}")
    except Exception as e:
        print(f"重命名文件时出错 {src}: {e}")
        raise


def process_directory(directory, threshold=0.6, dry_run=False):
    """
    处理指定目录下的所有文件：
    1. 重命名文件（在第二个'--'处截断）
    2. 将相似度≥threshold的文件对移动到以第一个文件命名的文件夹中
    """
    original_cwd = os.getcwd()
    os.chdir(directory)
    
    try:
        files = [f for f in os.listdir('.') if os.path.isfile(f)]
        print(f"找到 {len(files)} 个文件")
        
        # 辅助函数：判断两个文件夹名是否相似
        def is_similar_folder(folder1, folder2):
            """判断两个文件夹名是否相似，只比较第一个'_'前的部分"""
            # 提取第一个'_'前的部分
            prefix1 = folder1.split('_')[0].lower().strip()
            prefix2 = folder2.split('_')[0].lower().strip()
            
            # 如果前缀相同，则认为是相似文件夹
            return prefix1 == prefix2
        
        # 第一步：重命名所有文件
        renamed_files = []
        for filename in files:
            new_name = truncate_at_second_dash(filename)
            if new_name != filename:
                base, ext = os.path.splitext(new_name)
                counter = 1
                while os.path.exists(new_name) and not dry_run:
                    new_name = f"{base}_{counter}{ext}"
                    counter += 1
                safe_rename(filename, new_name, dry_run)
                filename = new_name
            renamed_files.append(filename)
        
        # 第二步：为所有文件创建目标文件夹映射
        file_to_folder = {}
        created_folders = set()
        
        # 首先收集所有需要创建的文件夹名
        for filename in renamed_files:
            # 获取文件名（不含扩展名）作为目标文件夹名
            folder_name = os.path.splitext(filename)[0]
            folder_name = re.sub(r'[<>:"/\\|?*]', '_', folder_name)
            file_to_folder[filename] = folder_name
        
        # 然后处理文件夹映射，合并相似文件夹
        for filename in renamed_files:
            target_folder = file_to_folder[filename]
            
            # 检查是否已经创建了相似文件夹
            for existing_folder in created_folders:
                if is_similar_folder(target_folder, existing_folder):
                    # 使用已存在的相似文件夹
                    file_to_folder[filename] = existing_folder
                    break
            else:
                # 没有相似文件夹，使用新文件夹
                created_folders.add(target_folder)
        
        # 第三步：创建文件夹并移动文件
        for filename in renamed_files:
            target_folder = file_to_folder[filename]
            
            # 创建文件夹（如果不存在）
            if not os.path.exists(target_folder) and not dry_run:
                os.makedirs(target_folder)
                print(f"创建文件夹: {target_folder}")
            elif dry_run and not os.path.exists(target_folder):
                print(f"[干运行] 创建文件夹: {target_folder}")
            
            # 移动文件到目标文件夹
            dst = os.path.join(target_folder, filename)
            if os.path.exists(filename):
                safe_move(filename, dst, dry_run)
        
        print("处理完成")
        
    finally:
        os.chdir(original_cwd)


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
    if special_char_ratio > 0.5:  # 如果超过50%是特殊字符
        return False
    
    return True


def _extract_pdf_text(filepath, target_text_pages=2, max_total_pages=10):
    """从PDF文件提取文本页面，跳过非文本页面"""
    if not PDF_SUPPORT:
        print(f"警告: PyPDF2未安装，跳过PDF文件 {filepath}")
        return ""
    
    try:
        text = ""
        text_pages_found = 0
        
        with open(filepath, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            total_pages = min(len(pdf_reader.pages), max_total_pages)
            
            for i in range(total_pages):
                if text_pages_found >= target_text_pages:
                    break
                    
                page = pdf_reader.pages[i]
                page_text = page.extract_text()
                
                if is_text_page(page_text):
                    text += page_text + "\n"
                    text_pages_found += 1
                else:
                    # 非文本页面，跳过
                    continue
        
        return text
    except Exception as e:
        print(f"读取PDF文件 {filepath} 时出错: {e}")
        return ""


def _extract_epub_text(filepath, target_text_pages=2, max_total_pages=10):
    """从EPUB文件提取文本页面，跳过非文本页面"""
    if not EPUB_SUPPORT:
        print(f"警告: ebooklib未安装，跳过EPUB文件 {filepath}")
        return ""
    
    try:
        text = ""
        text_pages_found = 0
        items_checked = 0
        
        book = epub.read_epub(filepath)
        
        for item in book.get_items():
            if text_pages_found >= target_text_pages or items_checked >= max_total_pages:
                break
                
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                items_checked += 1
                content = item.get_content().decode('utf-8', errors='ignore')
                # 简单去除HTML标签
                content = re.sub(r'<[^>]+>', ' ', content)
                # 清理多余空格
                content = re.sub(r'\s+', ' ', content).strip()
                
                if is_text_page(content):
                    text += content + "\n"
                    text_pages_found += 1
                else:
                    # 非文本页面，跳过
                    continue
        
        return text
    except Exception as e:
        print(f"读取EPUB文件 {filepath} 时出错: {e}")
        return ""


def extract_text(filepath, target_text_pages=2, max_total_pages=10):
    """
    提取文件的文本内容，跳过非文本页面（如封面、版权页等）
    
    参数:
        filepath: 文件路径
        target_text_pages: 要提取的文本页面数量（默认2页）
        max_total_pages: 最多检查的总页数（默认10页）
    
    返回:
        提取的文本字符串
    """
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == '.pdf':
        return _extract_pdf_text(filepath, target_text_pages, max_total_pages)
    elif ext == '.epub':
        return _extract_epub_text(filepath, target_text_pages, max_total_pages)
    else:
        return ""


def detect_language(text):
    """检测文本语言：纯英文或中英混合"""
    if not text:
        return None
    
    # 检测中文字符（Unicode范围）
    zh_pattern = re.compile(r'[\u4e00-\u9fff]')
    has_chinese = bool(zh_pattern.search(text))
    
    # 检测英文字母
    en_pattern = re.compile(r'[a-zA-Z]')
    has_english = bool(en_pattern.search(text))
    
    if has_chinese:
        return 'zh-en'  # 中英混合
    elif has_english:
        return 'en'     # 纯英文
    else:
        return None     # 无法确定


def detect_language_and_prefix(directory, pages=2, dry_run=False):
    """
    检测PDF和EPUB文件的语言并添加前缀
    注意：会自动跳过非文本页面（如封面、版权页等），只分析真正的文本页面
    """
    original_cwd = os.getcwd()
    os.chdir(directory)
    
    try:
        # 支持递归查找子目录
        for root, dirs, files in os.walk('.'):
            for filename in files:
                if not filename.lower().endswith(('.pdf', '.epub')):
                    continue
                
                # 跳过已经添加前缀的文件
                if filename.startswith(('英文-', '双语-')):
                    continue
                
                filepath = os.path.join(root, filename)
                print(f"处理文件: {filepath}")
                
                # 提取文本（跳过非文本页面如封面、版权页等）
                text = extract_text(filepath, target_text_pages=pages, max_total_pages=10)
                if not text:
                    print(f"  警告: 无法提取足够文本内容，跳过")
                    continue
                
                # 检测语言
                lang = detect_language(text)
                if lang is None:
                    print(f"  警告: 无法检测语言，跳过")
                    continue
                
                # 确定前缀
                if lang == 'en':
                    prefix = '英文-'
                elif lang == 'zh-en':
                    prefix = '双语-'
                else:
                    continue
                
                # 构建新文件名
                new_name = prefix + filename
                # 避免文件名冲突
                base, ext = os.path.splitext(new_name)
                counter = 1
                while os.path.exists(os.path.join(root, new_name)) and not dry_run:
                    new_name = f"{base}_{counter}{ext}"
                    counter += 1
                
                new_path = os.path.join(root, new_name)
                
                if dry_run:
                    print(f"  [干运行] 重命名: {filepath} -> {new_path}")
                else:
                    try:
                        os.rename(filepath, new_path)
                        print(f"  重命名: {filename} -> {new_name}")
                    except Exception as e:
                        print(f"  重命名文件时出错 {filepath}: {e}")
        
        print("语言检测加前缀处理完成")
        
    finally:
        os.chdir(original_cwd)


def main():
    parser = argparse.ArgumentParser(description='处理文件：重命名并分组相似文件或检测语言添加前缀')
    parser.add_argument('directory', nargs='?', default='file',
                        help='要处理的目录（默认为当前目录下的file文件夹）')
    parser.add_argument('--mode', choices=['rename', 'lang', 'both'], default='rename',
                        help='处理模式：rename=重命名分组, lang=语言检测加前缀, both=两者都执行（默认rename）')
    parser.add_argument('--threshold', type=float, default=0.6,
                        help='相似度阈值（默认0.6），仅在rename或both模式下有效')
    parser.add_argument('--pages', type=int, default=2,
                        help='检测语言时分析的文本页面数（默认2页，自动跳过非文本页面），仅在lang或both模式下有效')
    parser.add_argument('--dry-run', action='store_true',
                        help='干运行模式，只显示将要执行的操作而不实际执行')
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.directory):
        print(f"错误：目录 '{args.directory}' 不存在")
        sys.exit(1)
    
    if args.mode in ['rename', 'both']:
        print(f"执行重命名分组功能...")
        process_directory(args.directory, args.threshold, args.dry_run)
    
    if args.mode in ['lang', 'both']:
        print(f"执行语言检测加前缀功能...")
        detect_language_and_prefix(args.directory, args.pages, args.dry_run)


if __name__ == "__main__":
    main()