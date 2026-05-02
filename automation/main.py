"""
命令行主入口 - 电子书自动化处理系统
"""
import os
import sys
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

app = typer.Typer(help="电子书自动化处理系统")
console = Console()


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
        translate_book(book_id, str(input_path))

        progress.update(task, description="生成精简版...")
        generate_summary(book_id, str(input_path))

        progress.update(task, description="提取图片...")
        base_name = Path(input_path).stem
        pdf_path = Path(config.output_dir) / base_name / "PDF" / f"中英双语-{base_name}.pdf"
        extract_images(book_id, str(input_path), str(pdf_path) if pdf_path.exists() else None)

        progress.update(task, description="生成文案...")
        generate_copywriting(book_id, {
            'title': book_obj.title,
            'author': book_obj.author
        })

        if not skip_publish:
            progress.update(task, description="发布到闲鱼...")
            publish_to_xianyu(book_id)

        progress.update(task, description="完成!", completed=True)

    console.print(f"[bold green]处理完成: {book_id}[/bold green]")


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
    skip_publish: bool = typer.Option(False, help="跳过发布步骤")
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

            console.print(f"[dim]翻译并生成PDF...[/dim]")
            translate_book(book_id, str(input_path))

            console.print(f"[dim]生成精简版...[/dim]")
            generate_summary(book_id, str(input_path))

            console.print(f"[dim]提取图片...[/dim]")
            base_name = Path(input_path).stem
            pdf_path = Path(config.output_dir) / base_name / "PDF" / f"中英双语-{base_name}.pdf"
            extract_images(book_id, str(input_path), str(pdf_path) if pdf_path.exists() else None)

            console.print(f"[dim]生成文案...[/dim]")
            book_obj = db.get_book_by_id(book_id)
            generate_copywriting(book_id, {'title': book_obj.title, 'author': book_obj.author})

            if not skip_publish:
                console.print(f"[dim]发布到闲鱼...[/dim]")
                publish_to_xianyu(book_id)

            elapsed = time.time() - start_time
            db.update_book_status(book_id, "completed")
            console.print(f"[bold green]✓ {title} 处理完成 ({elapsed:.1f}秒)[/bold green]")
            success_count += 1

        except Exception as e:
            db.update_book_status(book_id, "failed", str(e))
            console.print(f"[bold red]✗ {title} 处理失败: {e}[/bold red]")
            fail_count += 1

    console.print(f"\n[bold]===== 处理完成 =====[/bold]")
    console.print(f"[green]成功: {success_count}[/green]")
    if fail_count > 0:
        console.print(f"[red]失败: {fail_count}[/red]")


@app.command()
def init():
    """初始化数据库"""
    db = DatabaseManager()
    console.print("[bold green]数据库初始化完成[/bold green]")


if __name__ == "__main__":
    app()
