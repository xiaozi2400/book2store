"""
命令行主入口 - 电子书自动化处理系统
"""
import os
import sys
import json
import shutil
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.database import DatabaseManager
from automation.directory_scanner import scan_input_directory
from automation.content_summarizer import generate_summary
from automation.image_extractor import extract_images
from automation.ai_copywriter import generate_copywriting
from automation.link_importer import import_links
from automation.xianyu_publisher import publish_to_xianyu
from automation.config import config
from automation.utils import extract_title_from_filename

app = typer.Typer(help="电子书自动化处理系统")
console = Console()


def extract_epub_metadata(epub_path: Path) -> dict:
    """从 EPUB 文件提取元数据（复用 directory_scanner 的逻辑）"""
    try:
        import ebooklib
        from ebooklib import epub
        
        book = epub.read_epub(str(epub_path))
        metadata = {
            'title': None,
            'author': None,
            'language': 'en',
        }
        
        if book.get_metadata('DC', 'title'):
            metadata['title'] = book.get_metadata('DC', 'title')[0][0]
        
        if book.get_metadata('DC', 'creator'):
            metadata['author'] = book.get_metadata('DC', 'creator')[0][0]
        
        if book.get_metadata('DC', 'language'):
            lang = book.get_metadata('DC', 'language')[0][0]
            metadata['language'] = lang.lower()
        
        return metadata
    except Exception:
        return {
            'title': None,
            'author': "Unknown",
            'language': 'en',
        }


@app.command()
def scan():
    """扫描输入目录，检测新书籍"""
    console.print("[bold blue]开始扫描输入目录...[/bold blue]")
    books = scan_input_directory()

    if books:
        table = Table(title="扫描结果")
        table.add_column("书名", style="cyan")
        table.add_column("作者", style="green")
        table.add_column("语言", style="yellow")

        for book in books:
            table.add_row(
                book.get('title', 'Unknown'),
                book.get('author', 'Unknown'),
                book.get('language', 'en')
            )

        console.print(table)
        console.print(f"[bold green]发现 {len(books)} 本新书籍[/bold green]")
    else:
        console.print("[yellow]未发现新书籍[/yellow]")


@app.command()
def status():
    """查看处理状态"""
    db = DatabaseManager()
    stats = db.get_stats()

    table = Table(title="处理统计")
    table.add_column("状态", style="cyan")
    table.add_column("数量", style="green")

    table.add_row("总计", str(stats['total']))
    table.add_row("待处理", str(stats['pending']))
    table.add_row("处理中", str(stats['processing']))
    table.add_row("已完成", str(stats['completed']))
    table.add_row("已发布", str(stats['published']))
    table.add_row("失败", str(stats['failed']))

    console.print(table)


@app.command()
def list(
    status_filter: Optional[str] = typer.Option(None, help="按状态筛选"),
    limit: int = typer.Option(10, help="显示数量")
):
    """列出书籍"""
    db = DatabaseManager()
    books = db.get_all_books(status=status_filter)

    if not books:
        console.print("[yellow]没有找到书籍[/yellow]")
        return

    table = Table(title=f"书籍列表 (共 {len(books)} 本)")
    table.add_column("ID", style="dim", width=8)
    table.add_column("书名", style="cyan")
    table.add_column("作者", style="green")
    table.add_column("状态", style="yellow")
    table.add_column("创建时间", style="dim")

    for book in books[:limit]:
        table.add_row(
            book.id[:8],
            book.title or 'Unknown',
            book.author or 'Unknown',
            book.status,
            book.created_at.strftime('%Y-%m-%d %H:%M')
        )

    console.print(table)


@app.command()
def process(
    book_id: str = typer.Argument(..., help="书籍ID"),
    skip_publish: bool = typer.Option(False, help="跳过发布步骤")
):
    """处理指定书籍"""
    from automation.translation_processor import translate_book

    console.print(f"[bold blue]开始处理书籍: {book_id}[/bold blue]")

    db = DatabaseManager()
    book = db.get_all_books()

    book_obj = None
    for b in book:
        if b.id == book_id or b.id.startswith(book_id) or b.filename.startswith(book_id):
            book_obj = b
            break

    if not book_obj:
        console.print(f"[bold red]未找到书籍: {book_id}[/bold red]")
        raise typer.Exit(1)

    db.create_book_output(book_obj.id)

    input_path = Path(config.input_dir) / book_obj.filename

    if not input_path.exists():
        console.print(f"[bold red]文件不存在: {input_path}[/bold red]")
        raise typer.Exit(1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("处理中...", total=None)

        progress.update(task, description="翻译并生成PDF...")
        if not translate_book(book_obj.id, str(input_path)):
            console.print("[bold red]翻译失败，停止处理[/bold red]")
            raise typer.Exit(1)

        progress.update(task, description="生成精简版...")
        generate_summary(book_id, str(input_path))

        progress.update(task, description="生成主图...")
        from automation.image_generator import generate_main_image
        generate_main_image(book_id)

        progress.update(task, description="提取图片...")
        base_name = Path(input_path).stem.strip()
        pdf_path = Path(config.output_dir) / base_name / "PDF" / f"中英双语-{base_name}.pdf"
        extract_images(book_id, str(input_path), str(pdf_path) if pdf_path.exists() else None)

        progress.update(task, description="生成文案...")
        generate_copywriting(book_id, {
            'title': book_obj.title,
            'author': book_obj.author,
            'summary': book_obj.summary_text or ''
        })

        if not skip_publish:
            progress.update(task, description="发布到闲鱼...")
            publish_to_xianyu(book_id)

        progress.update(task, description="完成!", completed=True)

    console.print(f"[bold green]处理完成: {book_id}[/bold green]")
    steps = db.get_token_summary(book_id)
    if steps:
        console.print(format_token_summary(steps))

    # 展示质量报告
    try:
        report_data = db.get_book_quality_report(book_obj.id)
        if report_data:
            report = json.loads(report_data)
            console.print("\n[bold]===== 翻译质量报告 =====[/bold]")
            report_table = Table(title="翻译质量报告")
            report_table.add_column("维度", style="cyan")
            report_table.add_column("得分", justify="right")
            report_table.add_column("问题")

            for dim_name, dim_result in report.get("dimensions", {}).items():
                issues = dim_result.get("issues", [])
                main_issues = "；".join(issues[:3]) if issues else "无"
                score = dim_result.get("score", "")
                report_table.add_row(dim_name, str(score), main_issues)

            console.print(report_table)
            grade = report.get('overall_grade', '')
            score = report.get('overall_score', '')
            console.print(f"总体评分: {grade} ({score}分)" if grade or score else "")
    except Exception as e:
        console.print(f"[dim]质量报告加载失败: {e}[/dim]")


@app.command()
def import_links(
    excel_path: str = typer.Argument(..., help="Excel文件路径")
):
    """从Excel导入分享链接"""
    console.print(f"[bold blue]导入分享链接: {excel_path}[/bold blue]")

    result = import_links(excel_path)

    if 'error' in result:
        console.print(f"[bold red]导入失败: {result['error']}[/bold red]")
        raise typer.Exit(1)

    console.print(f"[bold green]导入完成: {result['matched']}/{result['total']} 匹配成功[/bold green]")


@app.command()
def generate_template():
    """生成Excel导入模板"""
    from automation.link_importer import LinkImporter

    importer = LinkImporter()
    template_path = importer.generate_excel_template()

    console.print(f"[bold green]模板已生成: {template_path}[/bold green]")


@app.command()
def publish(
    book_id: str = typer.Argument(..., help="书籍ID"),
    auto: bool = typer.Option(False, help="自动发布（跳过手动确认）")
):
    """发布到闲鱼"""
    console.print(f"[bold blue]发布到闲鱼: {book_id}[/bold blue]")

    if not auto:
        confirm = typer.confirm("确认发布？")
        if not confirm:
            console.print("[yellow]已取消[/yellow]")
            raise typer.Exit()

    success = publish_to_xianyu(book_id)

    if success:
        console.print(f"[bold green]发布成功: {book_id}[/bold green]")
    else:
        console.print(f"[bold red]发布失败: {book_id}[/bold red]")
        raise typer.Exit(1)


@app.command()
def generate_list(
    book_id: str = typer.Argument(..., help="书籍ID")
):
    """生成闲鱼发布清单（备用方案）"""
    from automation.xianyu_publisher import XianyuPublisher

    publisher = XianyuPublisher()
    list_path = publisher.generate_publish_list(book_id)

    console.print(f"[bold green]发布清单已生成: {list_path}[/bold green]")


@app.command()
def auto(
    skip_publish: bool = typer.Option(False, help="跳过发布步骤"),
    skip_translate: bool = typer.Option(False, help="跳过翻译步骤"),
    skip_summarize: bool = typer.Option(False, help="跳过生成精简版"),
    skip_images: bool = typer.Option(False, help="跳过图片提取"),
    skip_copywriting: bool = typer.Option(False, help="跳过文案生成"),
    skip_cache: bool = typer.Option(False, help="跳过翻译缓存，强制重新翻译"),
):
    """一键处理：扫描输入目录，自动处理所有新书籍"""
    from automation.directory_scanner import scan_input_directory
    from automation.translation_processor import translate_book
    from automation.image_extractor import extract_images
    from automation.ai_copywriter import generate_copywriting
    from automation.content_summarizer import generate_summary
    from automation.xianyu_publisher import publish_to_xianyu
    import time

    console.print("[bold blue]开始一键处理...[/bold blue]\n")

    books = scan_input_directory()

    if not books:
        console.print("[yellow]未发现新书籍[/yellow]")
        return

    console.print(f"[bold]发现 {len(books)} 本新书籍，开始处理...[/bold]\n")

    db = DatabaseManager()
    success_count = 0
    fail_count = 0
    processed_books = []

    for i, book in enumerate(books, 1):
        title = book.get('title', 'Unknown')
        filename = book.get('filename', '')
        console.print(f"\n[bold cyan]处理第 {i}/{len(books)} 本: {title}[/bold cyan]")

        book_id = db.create_book(filename, title, book.get('author', '')).id

        start_time = time.time()
        db.update_book_status(book_id, "processing")

        try:
            input_path = Path(config.input_dir) / filename
            db.create_book_output(book_id)

            if not skip_translate:
                console.print(f"[dim]翻译并生成PDF...[/dim]")
                if not translate_book(book_id, str(input_path), skip_cache=skip_cache):
                    raise Exception("翻译失败")
            else:
                console.print(f"[dim]跳过翻译步骤[/dim]")

            if not skip_summarize:
                console.print(f"[dim]生成精简版...[/dim]")
                generate_summary(book_id, str(input_path))
            else:
                console.print(f"[dim]跳过精简版步骤[/dim]")

            if not skip_images:
                console.print(f"[dim]生成主图...[/dim]")
                from automation.image_generator import generate_main_image
                generate_main_image(book_id)

                console.print(f"[dim]提取图片...[/dim]")
                base_name = Path(input_path).stem
                pdf_path = Path(config.output_dir) / base_name / "PDF" / f"中英双语-{base_name}.pdf"
                extract_images(book_id, str(input_path), str(pdf_path) if pdf_path.exists() else None)
            else:
                console.print(f"[dim]跳过图片提取步骤[/dim]")

            if not skip_copywriting:
                console.print(f"[dim]生成文案...[/dim]")
                book_obj = db.get_book_by_id(book_id)
                generate_copywriting(book_id, {
                    'title': book_obj.title,
                    'author': book_obj.author,
                    'summary': book_obj.summary_text or ''
                })
            else:
                console.print(f"[dim]跳过文案生成步骤[/dim]")

            if not skip_publish:
                console.print(f"[dim]发布到闲鱼...[/dim]")
                publish_to_xianyu(book_id)

            elapsed = time.time() - start_time
            db.update_book_status(book_id, "completed")
            console.print(f"[bold green]✓ {title} 处理完成 ({elapsed:.1f}秒)[/bold green]")
            steps = db.get_token_summary(book_id)
            if steps:
                console.print(format_token_summary(steps))
            success_count += 1
            book_obj = db.get_book_by_id(book_id)
            processed_books.append(book_obj)

        except Exception as e:
            db.update_book_status(book_id, "failed", str(e))
            console.print(f"[bold red]✗ {title} 处理失败: {e}[/bold red]")
            fail_count += 1

    console.print(f"\n[bold]===== 处理完成 =====[/bold]")
    console.print(f"[green]成功: {success_count}[/green]")
    if fail_count > 0:
        console.print(f"[red]失败: {fail_count}[/red]")

    if success_count > 0:
        console.print("\n[bold]===== 翻译质量报告汇总 =====[/bold]")
        report_table = Table(title="翻译质量报告")
        report_table.add_column("书名", style="cyan")
        report_table.add_column("总分", justify="right")
        report_table.add_column("等级", style="yellow")
        report_table.add_column("主要问题")

        for book in processed_books:
            report_data = db.get_book_quality_report(book.id)
            if report_data:
                report = json.loads(report_data)
                issues = []
                for dim_name, dim_result in report.get("dimensions", {}).items():
                    issues.extend(dim_result.get("issues", []))
                main_issues = "；".join(issues[:3]) if issues else "无"
                report_table.add_row(
                    book.title or "Unknown",
                    str(report.get("overall_score", "")),
                    report.get("overall_grade", ""),
                    main_issues
                )

        console.print(report_table)


@app.command()
def test(
    skip_translate: bool = typer.Option(False, help="跳过翻译步骤"),
    skip_summarize: bool = typer.Option(False, help="跳过生成精简版"),
    skip_images: bool = typer.Option(False, help="跳过图片提取"),
    skip_copywriting: bool = typer.Option(False, help="跳过文案生成"),
    skip_cache: bool = typer.Option(False, help="跳过翻译缓存，强制重新翻译")
):
    """测试模式：直接从 test_input_dir 读取文件处理（跳过闲鱼发布）"""
    from automation.translation_processor import translate_book
    from automation.image_extractor import extract_images
    from automation.ai_copywriter import generate_copywriting
    from automation.content_summarizer import generate_summary
    from automation.utils import is_valid_epub
    import time

    test_dir = Path(config.test_input_dir)
    console.print(f"[bold yellow]测试模式[/bold yellow]")
    console.print(f"[dim]输入目录: {test_dir}[/dim]")
    console.print(f"[dim]输出目录: {config.output_dir}[/dim]\n")

    if not test_dir.exists():
        console.print(f"[bold red]测试目录不存在: {test_dir}[/bold red]")
        console.print(f"[yellow]请创建目录 {test_dir} 并放入 .epub 文件[/yellow]")
        raise typer.Exit(1)

    epub_files = sorted(test_dir.glob("*.epub"))
    if not epub_files:
        console.print(f"[yellow]测试目录中未找到 .epub 文件: {test_dir}[/yellow]")
        return

    console.print(f"[bold]发现 {len(epub_files)} 个测试文件，开始处理...[/bold]\n")

    db = DatabaseManager()
    success_count = 0
    fail_count = 0

    for i, epub_path in enumerate(epub_files, 1):
        filename = epub_path.name
        title = extract_title_from_filename(filename)
        console.print(f"\n[bold cyan][测试 {i}/{len(epub_files)}] {title}[/bold cyan]")
        console.print(f"[dim]文件: {epub_path}[/dim]")

        if not is_valid_epub(str(epub_path)):
            console.print(f"[bold red]无效的EPUB文件，跳过: {filename}[/bold red]")
            fail_count += 1
            continue

        import shutil
        base_name = epub_path.stem
        book_output_dir = Path(config.output_dir) / base_name
        if book_output_dir.exists():
            shutil.rmtree(book_output_dir)

        metadata = extract_epub_metadata(epub_path)
        final_title = metadata.get('title') or title
        author = metadata.get('author') or "Unknown"
        book_id = db.create_book(filename, f"[TEST] {final_title}", author).id
        start_time = time.time()
        db.update_book_status(book_id, "processing")

        try:
            db.create_book_output(book_id)

            if not skip_translate:
                if skip_cache:
                    console.print(f"  [dim]→ 翻译并生成PDF（跳过缓存）...[/dim]")
                else:
                    console.print(f"  [dim]→ 翻译并生成PDF...[/dim]")
                if not translate_book(book_id, str(epub_path), skip_cache=skip_cache):
                    raise Exception("翻译失败")
            else:
                console.print(f"  [dim]→ 跳过翻译步骤[/dim]")

            if not skip_summarize:
                console.print(f"  [dim]→ 生成精简版...[/dim]")
                generate_summary(book_id, str(epub_path))
            else:
                console.print(f"  [dim]→ 跳过精简版步骤[/dim]")

            if not skip_images:
                console.print(f"  [dim]→ 生成主图...[/dim]")
                from automation.image_generator import generate_main_image
                generate_main_image(book_id)

                console.print(f"  [dim]→ 提取图片...[/dim]")
                base_name = epub_path.stem
                pdf_path = Path(config.output_dir) / base_name / "PDF" / f"中英双语-{base_name}.pdf"
                extract_images(book_id, str(epub_path), str(pdf_path) if pdf_path.exists() else None)
            else:
                console.print(f"  [dim]→ 跳过图片提取步骤[/dim]")

            if not skip_copywriting:
                console.print(f"  [dim]→ 生成文案...[/dim]")
                book_obj = db.get_book_by_id(book_id)
                generate_copywriting(book_id, {
                    'title': book_obj.title,
                    'author': book_obj.author,
                    'summary': book_obj.summary_text or ''
                })
            else:
                console.print(f"  [dim]→ 跳过文案生成步骤[/dim]")

            console.print(f"  [dim]→ 跳过闲鱼发布（测试模式）[/dim]")

            elapsed = time.time() - start_time
            db.update_book_status(book_id, "completed")
            console.print(f"[bold green]✓ [测试] {title} 处理完成 ({elapsed:.1f}秒)[/bold green]")
            steps = db.get_token_summary(book_id)
            if steps:
                console.print(format_token_summary(steps))
            success_count += 1

        except Exception as e:
            db.update_book_status(book_id, "failed", str(e))
            console.print(f"[bold red]✗ [测试] {title} 处理失败: {e}[/bold red]")
            fail_count += 1
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")

    console.print(f"\n[bold]===== 测试处理完成 =====[/bold]")
    console.print(f"[green]成功: {success_count}[/green]")
    if fail_count > 0:
        console.print(f"[red]失败: {fail_count}[/red]")


def format_token_summary(steps):
    """将 token 汇总数据格式化为可读字符串"""
    if not steps:
        return "暂无Token消耗记录"

    step_labels = {
        "translation": "翻译",
        "summarizing": "摘要",
        "copywriting_xianyu": "闲鱼文案",
        "copywriting_xiaohongshu": "小红书文案",
    }

    table = Table(title="Token 消耗汇总")
    table.add_column("步骤", style="cyan")
    table.add_column("输入 Tokens", justify="right")
    table.add_column("输出 Tokens", justify="right")
    table.add_column("总 Tokens", justify="right")
    table.add_column("费用", justify="right")

    total_input = total_output = total_tokens = 0
    total_cost = 0.0

    for step_key, data in steps.items():
        label = step_labels.get(step_key, step_key)
        input_t = data.get("input_tokens", 0)
        output_t = data.get("output_tokens", 0)
        total_t = data.get("total_tokens", input_t + output_t)
        cost = data.get("cost", 0.0)

        table.add_row(
            label,
            f"{input_t:,}",
            f"{output_t:,}",
            f"{total_t:,}",
            f"¥{cost:.4f}",
        )

        total_input += input_t
        total_output += output_t
        total_tokens += total_t
        total_cost += cost

    table.add_row(
        "[bold]合计[/bold]",
        f"[bold]{total_input:,}[/bold]",
        f"[bold]{total_output:,}[/bold]",
        f"[bold]{total_tokens:,}[/bold]",
        f"[bold]¥{total_cost:.4f}[/bold]",
    )

    table.caption = f"总计费用: ¥{total_cost:.4f} (输入: {total_input:,} / 输出: {total_output:,})"

    from rich.console import Console
    c = Console()
    with c.capture() as capture:
        c.print(table)
    return capture.get()


@app.command()
def stats(book_id: str):
    """查看Token消耗统计"""
    db = DatabaseManager()
    steps = db.get_token_summary(book_id)
    console.print(format_token_summary(steps))


@app.command()
def init():
    """初始化数据库"""
    db = DatabaseManager()
    console.print("[bold green]数据库初始化完成[/bold green]")


@app.command()
def regenerate_images(
    keyword: str = typer.Argument(None, help="书籍标题关键词"),
    book_id: str = typer.Option(None, "--book-id", help="指定书籍ID（优先于关键词）"),
):
    """复用已有摘要重新生成主图（修改提示词后测试用）"""
    from automation.image_generator import generate_main_image

    db = DatabaseManager()

    if book_id:
        book = db.get_book_by_id(book_id)
        if not book:
            console.print(f"[red]未找到指定书籍: {book_id}[/red]")
            raise typer.Exit(1)
        if not book.summary_text:
            console.print(f"[red]书籍 {book.title} 无摘要，无法生成主图[/red]")
            raise typer.Exit(1)
        target_books = [book]
    else:
        if not keyword:
            console.print("[red]请提供关键词或 --book-id[/red]")
            raise typer.Exit(1)
        matched = []
        for book in db.get_all_books():
            if book.summary_text and keyword.lower() in (book.title or "").lower():
                matched.append(book)

        if not matched:
            console.print("[yellow]未找到匹配的有摘要的书籍[/yellow]")
            raise typer.Exit(1)

        if len(matched) > 1:
            console.print("[yellow]找到多本匹配书籍，请用 --book-id 指定:[/yellow]")
            for b in matched:
                console.print(f"  {b.id} - {b.title}")
            raise typer.Exit(1)

        target_books = matched

    for book in target_books:
        console.print(f"\n[bold cyan]重新生成主图: {book.title}[/bold cyan]")
        if generate_main_image(book.id):
            console.print(f"  [green]✓[/green] 主图生成完成")
        else:
            console.print(f"  [red]✗[/red] 主图生成失败")


if __name__ == "__main__":
    app()
