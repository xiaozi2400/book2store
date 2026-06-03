
"""
电子书翻译库 - 可被其他模块调用的编程接口
"""
import os
import sys
import time
import shutil
from pathlib import Path

# Add the current directory to path for relative imports
if __name__ != "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

from translator.epub_parser import EPUBParser
from translator.cache import CacheManager
from translator.epub_generator import EPUBGenerator
from translator.pdf_converter import PDFConverter
from config import PDF_CONFIG, TRANSLATION_PROVIDER


def get_translator():
    """根据配置选择翻译器"""
    from translator.translator import Translator
    return Translator()


def translate_epub(
    epub_path,
    output_dir=".",
    book_id=None,
    skip_cache=False,
    test_mode=False,
    cache=None,
    progress_callback=None
):
    """
    翻译 EPUB 电子书（库函数版本）
    
    Args:
        epub_path: 输入的 EPUB 文件路径
        output_dir: 输出目录，默认是当前目录
        book_id: 书籍ID，用于记录统计信息
        skip_cache: 是否跳过缓存
        test_mode: 测试模式（只处理前50个段落）
        cache: 可选的缓存实现，默认使用 JSON 缓存
        progress_callback: 可选的进度回调函数
        
    Returns:
        包含输出文件路径、token 统计等信息的字典
    """
    # 初始化配置
    
    # 使用传入的缓存或默认 JSON 缓存
    if cache is None:
        cache = CacheManager()
    
    # 统计开始时间
    start_time = time.time()
    phase_times = {}
    
    # 初始化模块
    parser = EPUBParser(epub_path)
    translator = get_translator()
    converter = PDFConverter()
    
    # 解析 EPUB
    phase_start = time.time()
    if not parser.parse():
        raise RuntimeError("解析 EPUB 文件失败")
    phase_times["解析 EPUB"] = time.time() - phase_start
    
    # 提取段落
    phase_start = time.time()
    all_paragraphs = []
    content_items = parser.get_content_items()
    
    for item in content_items:
        paragraphs = parser.get_paragraphs(item)
        all_paragraphs.extend(paragraphs)
    
    if not all_paragraphs:
        raise RuntimeError("未提取到段落")
    
    # 测试模式：只处理前50个段落
    if test_mode:
        all_paragraphs = all_paragraphs[:50]
    
    phase_times["提取段落"] = time.time() - phase_start
    
    # 翻译段落
    phase_start = time.time()
    
    # 使用缓存（如果未跳过）
    paragraphs_to_translate = []
    cached_results = []
    
    if not skip_cache:
        for para in all_paragraphs:
            # 重复段落直接使用缓存逻辑
            if para.get('is_duplicate'):
                original_id = para.get('original_id')
                if original_id:
                    para['_needs_original_translation'] = original_id
                paragraphs_to_translate.append(para)
                continue
            
            # 检查缓存
            cached = cache.get(para['text'])
            if cached and cached.strip():
                cached_results.append({
                    'id': para['id'],
                    'trans_id': para.get('trans_id'),
                    'original': para['text'],
                    'translated': cached,
                    'html': para['html'],
                    'tier': para.get('tier', 'unknown'),
                    'is_from_cache': True
                })
            else:
                paragraphs_to_translate.append(para)
    else:
        paragraphs_to_translate = all_paragraphs
    
    # 智能分层翻译
    translated_results = []
    if paragraphs_to_translate:
        translated_results = translator.translate_smart(paragraphs_to_translate)
        
        # 空翻译检测：如果所有非重复实时翻译结果都为空，提前返回
        if translated_results:
            fresh_results = [
                r for r in translated_results
                if not r.get('is_duplicate') and not r.get('_needs_original_translation')
            ]
            if fresh_results and all(
                not r.get('translated') or not r['translated'].strip()
                for r in fresh_results
            ):
                print("翻译 API 返回全部为空，翻译失败")
                return {
                    "success": False,
                    "error": "翻译 API 返回全部为空，翻译失败",
                    "total_paragraphs": len(all_paragraphs)
                }
        
        # 保存到缓存
        if not skip_cache:
            for result in translated_results:
                if result.get('translated') and not result.get('is_duplicate'):
                    cache.set(result['original'], result['translated'])
        
        # 处理重复段落（复用翻译结果）
        translation_map = {r['id']: r for r in translated_results if not r.get('is_duplicate')}
        
        for result in translated_results:
            if result.get('_needs_original_translation'):
                original_id = result['_needs_original_translation']
                if original_id in translation_map:
                    result['translated'] = translation_map[original_id]['translated']
                    result['is_duplicate'] = True
    
    # 合并结果
    all_translated = cached_results + translated_results
    phase_times["翻译段落"] = time.time() - phase_start
    
    # 获取文件名和输出路径
    base_name = os.path.basename(epub_path)
    name_without_ext = os.path.splitext(base_name)[0].strip()
    short_name = name_without_ext.split('_')[0].strip()
    
    # 每个版本单独一个子目录
    bilingual_dir = os.path.join(output_dir, f"双语-{short_name}")
    chinese_dir = os.path.join(output_dir, f"中文-{short_name}")
    english_dir = os.path.join(output_dir, f"英文-{short_name}")
    
    os.makedirs(bilingual_dir, exist_ok=True)
    os.makedirs(chinese_dir, exist_ok=True)
    os.makedirs(english_dir, exist_ok=True)
    
    bilingual_epub = os.path.join(bilingual_dir, f"双语-{short_name}.epub")
    chinese_epub = os.path.join(chinese_dir, f"中文-{short_name}.epub")
    english_epub = os.path.join(english_dir, f"英文-{short_name}.epub")
    bilingual_pdf = os.path.join(bilingual_dir, f"双语-{short_name}.pdf")
    chinese_pdf = os.path.join(chinese_dir, f"中文-{short_name}.pdf")
    english_pdf = os.path.join(english_dir, f"英文-{short_name}.pdf")
    
    # 生成 EPUB 文件
    phase_start = time.time()
    generator = EPUBGenerator(parser, PDF_CONFIG)
    
    # 生成中英对照 EPUB
    generator.generate_bilingual_epub(all_translated, bilingual_epub)
    
    # 生成纯中文 EPUB
    generator.generate_chinese_epub(all_translated, chinese_epub)
    
    # 复制英文原版 EPUB
    try:
        shutil.copy2(epub_path, english_epub)
    except Exception as e:
        print(f"复制英文原版 EPUB 失败: {e}")
    
    phase_times["生成 EPUB"] = time.time() - phase_start
    
    # 转换为 PDF
    phase_start = time.time()
    
    if os.path.exists(bilingual_epub):
        converter.convert_to_pdf(bilingual_epub, bilingual_pdf, is_bilingual=True)
    
    if os.path.exists(chinese_epub):
        converter.convert_to_pdf(chinese_epub, chinese_pdf, is_bilingual=False)
    
    if os.path.exists(english_epub):
        converter.convert_to_pdf(english_epub, english_pdf, is_bilingual=False)
    
    phase_times["PDF 转换"] = time.time() - phase_start
    
    # 总耗时
    total_time = time.time() - start_time
    
    # 获取统计信息
    stats = translator.get_stats()
    
    # 构建质量检查所需数据
    source_paragraphs = [p['text'] for p in all_paragraphs]
    translated_paragraphs = [r['translated'] for r in all_translated]
    cache_data = {
        str(i): {"source": r['original'], "translated": r['translated']}
        for i, r in enumerate(all_translated)
    }

    # 返回结果
    return {
        "success": True,
        "output_dir": output_dir,
        "bilingual_epub": bilingual_epub if os.path.exists(bilingual_epub) else None,
        "chinese_epub": chinese_epub if os.path.exists(chinese_epub) else None,
        "english_epub": english_epub if os.path.exists(english_epub) else None,
        "bilingual_pdf": bilingual_pdf if os.path.exists(bilingual_pdf) else None,
        "chinese_pdf": chinese_pdf if os.path.exists(chinese_pdf) else None,
        "english_pdf": english_pdf if os.path.exists(english_pdf) else None,
        "total_paragraphs": len(all_paragraphs),
        "cached_results": len(cached_results),
        "stats": stats,
        "phase_times": phase_times,
        "total_time": total_time,
        "source_paragraphs": source_paragraphs,
        "translated_paragraphs": translated_paragraphs,
        "cache_data": cache_data
    }


def convert_english_pdf_only(
    epub_path,
    output_dir="."
):
    """
    仅转换英文原版 EPUB 为 PDF（无需翻译）
    
    Args:
        epub_path: 输入的 EPUB 文件路径
        output_dir: 输出目录，默认是当前目录
        
    Returns:
        生成的英文 PDF 文件路径
    """
    
    # 获取文件名和输出路径
    base_name = os.path.basename(epub_path)
    name_without_ext = os.path.splitext(base_name)[0].strip()
    short_name = name_without_ext.split('_')[0].strip()
    
    english_dir = os.path.join(output_dir, f"英文-{short_name}")
    os.makedirs(english_dir, exist_ok=True)
    
    english_epub = os.path.join(english_dir, f"英文-{short_name}.epub")
    english_pdf = os.path.join(english_dir, f"英文-{short_name}.pdf")
    
    # 先复制英文 EPUB
    try:
        shutil.copy2(epub_path, english_epub)
    except Exception as e:
        print(f"复制英文原版 EPUB 失败: {e}")
        return None
    
    # 转换 PDF
    if os.path.exists(english_epub):
        converter = PDFConverter()
        converter.convert_to_pdf(english_epub, english_pdf, is_bilingual=False)
    
    return english_pdf if os.path.exists(english_pdf) else None

