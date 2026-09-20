# noqa: E402 — subproject requires sys.path modification before imports
import argparse
import io
import json
import os
import signal
import sys
import time

# noqa: E402 — subproject requires sys.path modification above
from config import PDF_CONFIG, TRANSLATION_PROVIDER  # noqa: E402
from translator.cache import CacheManager  # noqa: E402
from translator.epub_generator import EPUBGenerator  # noqa: E402
from translator.epub_parser import EPUBParser  # noqa: E402
from translator.pdf_converter import PDFConverter  # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


def get_translator():
    """根据配置选择翻译器"""
    from translator.translator import Translator

    print(f"[翻译器] 使用 {TRANSLATION_PROVIDER.upper()}")
    return Translator()


# 全局变量，用于标记是否收到中断信号
interrupted = False


def signal_handler(signum, frame):
    """信号处理函数"""
    global interrupted
    print("\n收到中断信号，正在停止...")
    interrupted = True
    # 设置全局中断标志和环境变量
    sys.interrupted = True
    os.environ["INTERRUPTED"] = "1"
    # 强制退出
    sys.exit(0)


def main():
    """主函数 - 智能分层翻译版本"""
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 解析命令行参数
    parser = argparse.ArgumentParser(description="电子书翻译和转换脚本 - 智能分层版本")
    parser.add_argument("input_epub", help="输入的 EPUB 文件路径")
    parser.add_argument("--output-dir", "-o", default=".", help="输出目录")
    parser.add_argument("--api-key", "-k", help="DeepSeek API 密钥")
    parser.add_argument("--skip-cache", action="store_true", help="跳过缓存")
    parser.add_argument("--test-mode", action="store_true", help="测试模式（只处理前50个段落）")
    parser.add_argument("--book-id", help="书籍ID（用于跨进程传递Token统计）")

    args = parser.parse_args()

    # 检查输入文件
    if not os.path.exists(args.input_epub):
        print(f"错误：输入文件 {args.input_epub} 不存在")
        sys.exit(1)

    # 检查输出目录
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    # 如果提供了命令行 API 密钥，则使用它
    if args.api_key:
        import config

        config.DEEPSEEK_API_KEY = args.api_key

    # 初始化模块
    print("=" * 60)
    print("电子书智能翻译工具 - 方案C（智能平衡）")
    print("=" * 60)

    parser = EPUBParser(args.input_epub)
    translator = get_translator()
    cache = CacheManager()
    converter = PDFConverter()

    # 统计开始时间
    start_time = time.time()
    phase_times = {}

    # 解析 EPUB
    phase_start = time.time()
    print("\n[1/4] 正在解析 EPUB 文件...")
    if not parser.parse():
        print("解析 EPUB 文件失败")
        sys.exit(1)
    phase_times["解析 EPUB"] = time.time() - phase_start

    # 提取段落
    phase_start = time.time()
    print("\n[2/4] 正在提取段落（智能分层）...")
    all_paragraphs = []
    content_items = parser.get_content_items()

    for item in content_items:
        paragraphs = parser.get_paragraphs(item)
        all_paragraphs.extend(paragraphs)

    if not all_paragraphs:
        print("未提取到段落")
        sys.exit(1)

    # 打印提取报告
    parser.print_extraction_report()

    # 测试模式：只处理前50个段落
    if args.test_mode:
        print("\n测试模式：只处理前 50 个段落")
        all_paragraphs = all_paragraphs[:50]

    print(f"共提取到 {len(all_paragraphs)} 个段落")
    phase_times["提取段落"] = time.time() - phase_start

    # 检查是否收到中断信号
    if interrupted:
        print("处理被中断")
        sys.exit(1)

    # 翻译段落
    phase_start = time.time()
    print("\n[3/4] 正在翻译段落（智能分层翻译）...")

    # 使用缓存（如果未跳过）
    paragraphs_to_translate = []
    cached_results = []

    if not args.skip_cache:
        print("检查缓存...")
        for para in all_paragraphs:
            # 检查是否收到中断信号
            if interrupted:
                print("处理被中断")
                sys.exit(1)

            # 重复段落直接使用缓存逻辑
            if para.get("is_duplicate"):
                # 找到原文的翻译
                original_id = para.get("original_id")
                if original_id:
                    # 标记为重复，稍后处理
                    para["_needs_original_translation"] = original_id
                paragraphs_to_translate.append(para)
                continue

            # 检查缓存
            cached = cache.get(para["text"])
            if cached and cached.strip():
                cached_results.append(
                    {
                        "id": para["id"],
                        "trans_id": para.get("trans_id"),
                        "original": para["text"],
                        "translated": cached,
                        "html": para["html"],
                        "tier": para.get("tier", "unknown"),
                        "is_from_cache": True,
                    }
                )
            else:
                paragraphs_to_translate.append(para)

        print(f"缓存命中: {len(cached_results)} 个段落")
        print(f"需要翻译: {len(paragraphs_to_translate)} 个段落")
    else:
        paragraphs_to_translate = all_paragraphs
        print("跳过缓存，全部重新翻译")

    # 智能分层翻译
    translated_results = []
    if paragraphs_to_translate:
        translated_results = translator.translate_smart(paragraphs_to_translate)

        # 保存到缓存
        if not args.skip_cache:
            for result in translated_results:
                if result.get("translated") and not result.get("is_duplicate"):
                    cache.set(result["original"], result["translated"])

        # 处理重复段落（复用翻译结果）
        translation_map = {r["id"]: r for r in translated_results if not r.get("is_duplicate")}

        for result in translated_results:
            if result.get("_needs_original_translation"):
                original_id = result["_needs_original_translation"]
                if original_id in translation_map:
                    result["translated"] = translation_map[original_id]["translated"]
                    result["is_duplicate"] = True

    # 合并结果
    all_translated = cached_results + translated_results

    # 打印翻译报告
    translator.print_translation_report()

    phase_times["翻译段落"] = time.time() - phase_start

    # 检查是否收到中断信号
    if interrupted:
        print("处理被中断")
        sys.exit(1)

    # 获取文件名
    base_name = os.path.basename(args.input_epub)
    name_without_ext = os.path.splitext(base_name)[0]

    short_name = name_without_ext.split("_")[0].strip()

    # 每个版本单独一个子目录
    bilingual_dir = os.path.join(args.output_dir, f"双语-{short_name}")
    chinese_dir = os.path.join(args.output_dir, f"中文-{short_name}")
    english_dir = os.path.join(args.output_dir, f"英文-{short_name}")

    os.makedirs(bilingual_dir, exist_ok=True)
    os.makedirs(chinese_dir, exist_ok=True)
    os.makedirs(english_dir, exist_ok=True)

    bilingual_epub = os.path.join(bilingual_dir, f"双语-{short_name}.epub")
    chinese_epub = os.path.join(chinese_dir, f"中文-{short_name}.epub")
    english_epub = os.path.join(english_dir, f"英文-{short_name}.epub")
    bilingual_pdf = os.path.join(bilingual_dir, f"双语-{short_name}.pdf")
    chinese_pdf = os.path.join(chinese_dir, f"中文-{short_name}.pdf")
    english_pdf = os.path.join(english_dir, f"英文-{short_name}.pdf")

    # 打印输出路径
    print(f"\n输出目录：{args.output_dir}")
    print(f"双语 EPUB：{bilingual_epub}")
    print(f"中文 EPUB：{chinese_epub}")
    print(f"英文 EPUB：{english_epub}")
    print(f"双语 PDF：{bilingual_pdf}")
    print(f"中文 PDF：{chinese_pdf}")
    print(f"英文 PDF：{english_pdf}")

    # 生成 EPUB 文件
    phase_start = time.time()
    print("\n[4/4] 正在生成 EPUB 文件...")
    generator = EPUBGenerator(parser, PDF_CONFIG)

    # 生成中英对照 EPUB
    print("\n生成中英对照 EPUB...")
    if generator.generate_bilingual_epub(all_translated, bilingual_epub):
        print("✓ 中英对照 EPUB 生成成功")
    else:
        print("✗ 中英对照 EPUB 生成失败")

    # 生成纯中文 EPUB
    print("\n生成纯中文 EPUB...")
    if generator.generate_chinese_epub(all_translated, chinese_epub):
        print("✓ 纯中文 EPUB 生成成功")
    else:
        print("✗ 纯中文 EPUB 生成失败")

    # 复制英文原版 EPUB
    print("\n复制英文原版 EPUB...")
    import shutil

    try:
        shutil.copy2(args.input_epub, english_epub)
        print("✓ 英文原版 EPUB 生成成功")
    except Exception as e:
        print(f"✗ 英文原版 EPUB 生成失败: {e}")

    phase_times["生成 EPUB"] = time.time() - phase_start

    # 转换为 PDF
    phase_start = time.time()
    print("\n[额外] 正在转换为 PDF...")

    if os.path.exists(bilingual_epub):
        print("转换双语 EPUB...")
        if converter.convert_to_pdf(bilingual_epub, bilingual_pdf, is_bilingual=True):
            print("✓ 双语 PDF 生成成功")
        else:
            print("✗ 双语 PDF 生成失败")

    if os.path.exists(chinese_epub):
        print("转换中文 EPUB...")
        if converter.convert_to_pdf(chinese_epub, chinese_pdf, is_bilingual=False):
            print("✓ 中文 PDF 生成成功")
        else:
            print("✗ 中文 PDF 生成失败")

    if os.path.exists(english_epub):
        print("转换英文原版 EPUB...")
        if converter.convert_to_pdf(english_epub, english_pdf, is_bilingual=False):
            print("✓ 英文原版 PDF 生成成功")
        else:
            print("✗ 英文原版 PDF 生成失败")

    phase_times["PDF 转换"] = time.time() - phase_start

    # 总耗时
    total_time = time.time() - start_time

    # 显示统计信息
    print("\n" + "=" * 60)
    print("翻译统计信息")
    print("=" * 60)
    stats = translator.get_stats()
    print(f"总段落数: {len(all_paragraphs)}")
    print(f"缓存命中: {len(cached_results)} ({len(cached_results)/len(all_paragraphs)*100:.1f}%)")
    print(f"API 调用次数: {stats['api_calls']}")
    print(f"翻译段落数: {stats['translated_paragraphs']}")
    print(f"总 Token 消耗: {stats['total_tokens']}")
    if stats["translated_paragraphs"] > 0:
        print(f"平均每段落 Token: {stats['total_tokens']/stats['translated_paragraphs']:.1f}")
    print(f"重试次数: {stats['retried']}")
    print(f"失败次数: {stats['failed']}")

    # 显示时间统计
    print("\n" + "=" * 60)
    print("时间统计")
    print("=" * 60)
    for phase, duration in phase_times.items():
        print(f"{phase}: {duration:.2f} 秒")
    print(f"总耗时: {total_time:.2f} 秒")

    # 成本估算
    if stats["total_tokens"] > 0:
        cost = stats["total_tokens"] / 1000000  # DeepSeek 约 1元/百万token
        print(f"\n估算成本: {cost:.4f} 元")

    # 如果指定了 book_id，将 Token 统计写入临时 JSON 文件（用于跨进程通信）
    if args.book_id:
        import tempfile

        stats_file = os.path.join(tempfile.gettempdir(), f"translation_stats_{args.book_id}.json")
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "prompt_tokens": stats.get("prompt_tokens", 0),
                    "completion_tokens": stats.get("completion_tokens", 0),
                    "total_tokens": stats.get("total_tokens", 0),
                    "api_calls": stats.get("api_calls", 0),
                    "cache_hits": stats.get("cache_hits", 0),
                    "translated_paragraphs": stats.get("translated_paragraphs", 0),
                },
                f,
                ensure_ascii=False,
            )
        print("[Token统计] 已保存到临时文件")

    print("=" * 60)
    print("处理完成！")
    print("=" * 60)
    print("生成的文件：")
    if os.path.exists(bilingual_epub):
        print(f"  ✓ 中英双语 EPUB: {bilingual_epub}")
    if os.path.exists(chinese_epub):
        print(f"  ✓ 纯中文 EPUB: {chinese_epub}")
    if os.path.exists(bilingual_pdf):
        print(f"  ✓ 中英双语 PDF: {bilingual_pdf}")
    if os.path.exists(chinese_pdf):
        print(f"  ✓ 中文 PDF: {chinese_pdf}")


if __name__ == "__main__":
    main()
