import os
import sys
import signal
import time
import argparse
from translator.epub_parser import EPUBParser
from translator.deepseek_api import DeepSeekTranslator
from translator.cache import CacheManager
from translator.epub_generator import EPUBGenerator
from translator.pdf_converter import PDFConverter

# 全局变量，用于标记是否收到中断信号
interrupted = False

def signal_handler(signum, frame):
    """信号处理函数"""
    global interrupted
    print("\n收到中断信号，正在停止...")
    interrupted = True
    # 设置全局中断标志和环境变量
    sys.interrupted = True
    os.environ['INTERRUPTED'] = '1'
    # 强制退出
    sys.exit(0)

def main():
    """主函数"""
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
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
    
    # 如果提供了命令行 API 密钥，则使用它
    if args.api_key:
        # 动态修改 config 模块中的 API 密钥
        import config
        config.DEEPSEEK_API_KEY = args.api_key
    
    translator = DeepSeekTranslator()
    cache = CacheManager()
    converter = PDFConverter()
    
    # 统计开始时间
    start_time = time.time()
    phase_times = {}
    
    # 解析 EPUB
    phase_start = time.time()
    print("正在解析 EPUB 文件...")
    if not parser.parse():
        print("解析 EPUB 文件失败")
        sys.exit(1)
    phase_times["解析 EPUB"] = time.time() - phase_start
    
    # 提取段落
    phase_start = time.time()
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
    phase_times["提取段落"] = time.time() - phase_start
    
    # 翻译段落
    phase_start = time.time()
    print("正在翻译段落...")
    translated_paragraphs = []
    cache_misses = []
    cache_hits_count = 0
    
    # 先检查缓存
    for i, paragraph in enumerate(all_paragraphs):
        # 检查是否收到中断信号
        if interrupted:
            print("处理被中断")
            sys.exit(1)
        
        cached_translation = cache.get(paragraph['text'])
        # 只有缓存存在且不为空时才使用缓存
        if cached_translation and cached_translation.strip():
            print(f"段落 {i+1}/{len(all_paragraphs)} (缓存命中)")
            translated_paragraphs.append({
                'original': paragraph['text'],
                'translated': cached_translation,
                'html': paragraph['html']
            })
            cache_hits_count += 1
        else:
            # 缓存为空或不存在，需要重新翻译
            if cached_translation is not None and not cached_translation.strip():
                print(f"段落 {i+1}/{len(all_paragraphs)} (缓存为空，需要重新翻译)")
            cache_misses.append(paragraph)
    
    # 更新缓存命中统计
    translator.stats["cache_hits"] = cache_hits_count
    
    # 使用优化的翻译方法处理未缓存的段落
    if cache_misses:
        print(f"需要翻译 {len(cache_misses)} 个段落 (缓存未命中)")
        translated_count = 0
        failed_count = 0
        try:
            # 使用同步但更高效的方式：小批量、高并发
            # 减小批量大小（每批3个），增加并发数（10个线程）
            optimized_results = translator.translate_optimized(cache_misses, batch_size=3, max_workers=10)
            # 保存到缓存
            for result in optimized_results:
                if result['translated'] and result['translated'].strip():
                    cache.set(result['original'], result['translated'])
                    translated_count += 1
                else:
                    failed_count += 1
                    print(f"警告：段落翻译失败: {result['original'][:50]}...")
            # 添加到结果
            translated_paragraphs.extend(optimized_results)
            print(f"翻译完成：成功 {translated_count} 个，失败 {failed_count} 个")
        except Exception as e:
            print(f"翻译过程出错: {e}")
            print("继续执行，使用已翻译的段落")
    else:
        print("所有段落都命中缓存，无需翻译")
    phase_times["翻译段落"] = time.time() - phase_start
    
    # 检查是否收到中断信号
    if interrupted:
        print("处理被中断")
        sys.exit(1)
    
    # 获取文件名
    base_name = os.path.basename(args.input_epub)
    name_without_ext = os.path.splitext(base_name)[0]
    
    # 生成输出文件路径
    bilingual_epub = os.path.join(args.output_dir, f"中英双语-{base_name}")
    chinese_epub = os.path.join(args.output_dir, f"中文版本-{base_name}")
    bilingual_pdf = os.path.join(args.output_dir, f"中英双语-{name_without_ext}.pdf")
    chinese_pdf = os.path.join(args.output_dir, f"中文版本-{name_without_ext}.pdf")
    
    # 打印输出路径
    print(f"输出目录：{args.output_dir}")
    print(f"双语 EPUB：{bilingual_epub}")
    print(f"中文 EPUB：{chinese_epub}")
    print(f"双语 PDF：{bilingual_pdf}")
    print(f"中文 PDF：{chinese_pdf}")
    
    # 生成 EPUB 文件
    phase_start = time.time()
    print("正在生成 EPUB 文件...")
    generator = EPUBGenerator(parser)
    
    # 生成中英对照 EPUB
    print(f"正在生成中英对照 EPUB：{bilingual_epub}")
    if not generator.generate_bilingual_epub(translated_paragraphs, bilingual_epub):
        print("生成中英对照 EPUB 失败")
    else:
        print(f"生成中英对照 EPUB 成功：{bilingual_epub}")
    
    # 生成纯中文 EPUB
    print(f"正在生成纯中文 EPUB：{chinese_epub}")
    if not generator.generate_chinese_epub(translated_paragraphs, chinese_epub):
        print("生成纯中文 EPUB 失败")
    else:
        print(f"生成纯中文 EPUB 成功：{chinese_epub}")
    phase_times["生成 EPUB"] = time.time() - phase_start
    
    # 转换为 PDF
    phase_start = time.time()
    print("正在转换为 PDF...")
    
    if os.path.exists(bilingual_epub):
        print(f"正在转换双语 EPUB：{bilingual_epub}")
        success = converter.convert_to_pdf(bilingual_epub, bilingual_pdf, is_bilingual=True)
        if success:
            print(f"双语 PDF 生成成功：{bilingual_pdf}")
        else:
            print("双语 PDF 生成失败")
    else:
        print(f"双语 EPUB 文件不存在：{bilingual_epub}")

    if os.path.exists(chinese_epub):
        print(f"正在转换中文 EPUB：{chinese_epub}")
        success = converter.convert_to_pdf(chinese_epub, chinese_pdf, is_bilingual=False)
        if success:
            print(f"中文 PDF 生成成功：{chinese_pdf}")
        else:
            print("中文 PDF 生成失败")
    else:
        print(f"中文 EPUB 文件不存在：{chinese_epub}")
    phase_times["转换 PDF"] = time.time() - phase_start
    
    # 总耗时
    total_time = time.time() - start_time
    
    # 显示统计信息
    print("\n=== 翻译统计信息 ===")
    stats = translator.get_stats()
    print(f"总段落数: {len(all_paragraphs)}")
    print(f"缓存命中: {stats['cache_hits']} ({stats['cache_hits']/len(all_paragraphs)*100:.1f}%)")
    print(f"API 调用次数: {stats['api_calls']}")
    print(f"翻译段落数: {stats['translated_paragraphs']}")
    print(f"总 Token 消耗: {stats['total_tokens']}")
    print(f"平均每段落 Token: {stats['total_tokens']/max(stats['translated_paragraphs'], 1):.1f}")
    print("====================")
    
    # 显示时间统计
    print("\n=== 时间统计 ===")
    for phase, duration in phase_times.items():
        print(f"{phase}: {duration:.2f} 秒")
    print(f"总耗时: {total_time:.2f} 秒")
    print("====================")
    
    print("\n处理完成！")
    print(f"生成的文件：")
    print(f"  - 中英双语 EPUB: {bilingual_epub}")
    print(f"  - 纯中文 EPUB: {chinese_epub}")
    print(f"  - 中英双语 PDF: {bilingual_pdf}")
    print(f"  - 纯中文 PDF: {chinese_pdf}")

if __name__ == "__main__":
    main()
