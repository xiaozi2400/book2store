import sys
sys.path.insert(0, 'd:\\project\\bookfile_bat\\ebook_translator')

from translator.epub_parser import EPUBParser
from translator.epub_generator import EPUBGenerator
from translator.pdf_converter import PDFConverter
from translator.cache import CacheManager
import os

def generate_chinese_pdf():
    """生成中文版本EPUB和PDF"""
    
    epub_path = 'd:\\project\\bookfile_bat\\ebook_translator\\The Million-Dollar, One-Person Business-A Make Great Money.epub'
    output_dir = '.\\output_test'
    
    print('=== 生成中文版本EPUB和PDF ===\n')
    
    # 1. 解析EPUB
    print('1. 解析EPUB...')
    parser = EPUBParser(epub_path)
    success = parser.parse()
    
    if not success:
        print('解析EPUB失败')
        return
    
    # 2. 获取所有段落并检查缓存
    print('2. 获取翻译段落...')
    all_paragraphs = []
    cache = CacheManager()
    
    for item in parser.get_content_items():
        paragraphs = parser.get_paragraphs(item)
        for para in paragraphs:
            para_text = para.get('text', '')
            cached = cache.get(para_text)
            
            if cached:
                all_paragraphs.append({
                    'id': para.get('id'),
                    'original': para_text,
                    'translated': cached,
                    'html': para.get('html', ''),
                    'tier': para.get('tier', 'unknown')
                })
    
    print(f'   找到 {len(all_paragraphs)} 个已翻译段落')
    
    # 3. 生成中文版本EPUB
    print('3. 生成中文版本EPUB...')
    generator = EPUBGenerator(parser)
    
    os.makedirs(output_dir, exist_ok=True)
    epub_output_path = os.path.join(output_dir, '中文版本-The Million-Dollar, One-Person Business-A Make Great Money.epub')
    
    success = generator.generate_chinese_epub(all_paragraphs, epub_output_path)
    
    if not success:
        print('生成EPUB失败')
        return
    
    print(f'   ✓ EPUB已生成: {epub_output_path}')
    
    # 4. 转换为PDF
    print('\n4. 转换为PDF...')
    pdf_output_path = os.path.join(output_dir, '中文版本-The Million-Dollar, One-Person Business-A Make Great Money.pdf')
    
    converter = PDFConverter()
    success = converter.convert_to_pdf(epub_output_path, pdf_output_path, is_bilingual=False)
    
    if success:
        print(f'   ✓ PDF已生成: {pdf_output_path}')
        print('\n=== 完成 ===')
        print(f'行间距: 1.8倍')
        print(f'段间距: 1.5em（增加）')
        print(f'首行缩进: 2em（标准中文缩进）')
    else:
        print('   ✗ PDF转换失败')

if __name__ == '__main__':
    generate_chinese_pdf()
