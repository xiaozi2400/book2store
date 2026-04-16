import os
import sys
import argparse
from translator.epub_parser import EPUBParser
from translator.deepseek_api import DeepSeekTranslator
from translator.cache import CacheManager
from translator.epub_generator import EPUBGenerator
from translator.pdf_converter import PDFConverter

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='电子书翻译和转换脚本')
    parser.add_argument('input_epub', help='输入的 EPUB 文件路径')
    parser.add_argument('--output-dir', '-o', default='.', help='输出目录')
    parser.add_argument('--api-key', '-k', help='DeepSeek API 密钥')
    
    args = parser.parse_args()
    
    # 检查输入文件
    if not os.path.exists(args.input_epub):
        print(f"错误：输入文件 {args.input_epub} 不存在")
        sys.exit(1)
    
    # 检查输出目录
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    
    # 初始化模块
    parser = EPUBParser(args.input_epub)
    translator = DeepSeekTranslator()
    cache = CacheManager()
    converter = PDFConverter()
    
    # 解析 EPUB
    print("正在解析 EPUB 文件...")
    if not parser.parse():
        print("解析 EPUB 文件失败")
        sys.exit(1)
    
    # 提取段落
    print("正在提取段落...")
    all_paragraphs = []
    content_items = parser.get_content_items()
    
    for item in content_items:
        paragraphs = parser.get_paragraphs(item)
        all_paragraphs.extend(paragraphs)
    
    if not all_paragraphs:
        print("未提取到段落")
        sys.exit(1)
    
    print(f"共提取到 {len(all_paragraphs)} 个段落")
    
    # 翻译段落
    print("正在翻译段落...")
    translated_paragraphs = []
    
    for i, paragraph in enumerate(all_paragraphs):
        # 检查缓存
        cached_translation = cache.get(paragraph['text'])
        if cached_translation:
            print(f"段落 {i+1}/{len(all_paragraphs)} (缓存命中)")
            translated = cached_translation
        else:
            print(f"段落 {i+1}/{len(all_paragraphs)}")
            translated = translator.translate(paragraph['text'])
            # 保存到缓存
            if translated:
                cache.set(paragraph['text'], translated)
        
        translated_paragraphs.append({
            'original': paragraph['text'],
            'translated': translated,
            'html': paragraph['html']
        })
    
    # 获取文件名
    base_name = os.path.basename(args.input_epub)
    name_without_ext = os.path.splitext(base_name)[0]
    
    # 生成输出文件路径
    bilingual_epub = os.path.join(args.output_dir, f"中英双语-{base_name}")
    chinese_epub = os.path.join(args.output_dir, f"中文版本-{base_name}")
    bilingual_pdf = os.path.join(args.output_dir, f"中英双语-{name_without_ext}.pdf")
    chinese_pdf = os.path.join(args.output_dir, f"中文版本-{name_without_ext}.pdf")
    
    # 生成 EPUB 文件
    print("正在生成 EPUB 文件...")
    generator = EPUBGenerator(parser.get_book())
    
    # 生成中英对照 EPUB
    if not generator.generate_bilingual_epub(translated_paragraphs, bilingual_epub):
        print("生成中英对照 EPUB 失败")
    
    # 生成纯中文 EPUB
    if not generator.generate_chinese_epub(translated_paragraphs, chinese_epub):
        print("生成纯中文 EPUB 失败")
    
    # 转换为 PDF
    print("正在转换为 PDF...")
    
    if os.path.exists(bilingual_epub):
        converter.convert_to_pdf(bilingual_epub, bilingual_pdf)
    
    if os.path.exists(chinese_epub):
        converter.convert_to_pdf(chinese_epub, chinese_pdf)
    
    print("处理完成！")

if __name__ == "__main__":
    main()
