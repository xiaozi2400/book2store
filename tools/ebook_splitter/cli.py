"""
CLI entry point for EPUB splitter tool.
"""
import os
import sys
import typer
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ebook_splitter.epub_splitter import EPUBSplitter

app = typer.Typer(help="EPUB 提取工具 - 提取 EPUB 文件前 1/20 的内容")


@app.command()
def split(
    input_path: str = typer.Argument(..., help="输入 EPUB 文件路径或包含 EPUB 文件的目录"),
    output_dir: Optional[str] = typer.Option(None, help="输出目录（默认：输入文件同目录下的 output 文件夹）"),
):
    """
    提取 EPUB 文件的前 1/20 内容。
    """
    input_path = Path(input_path)
    if not input_path.exists():
        typer.echo(f"[red]错误：路径不存在: {input_path}[/red]", err=True)
        raise typer.Exit(1)

    if output_dir is None:
        output_dir = input_path.parent / "output" if input_path.is_file() else input_path / "output"
    else:
        output_dir = Path(output_dir)

    os.makedirs(output_dir, exist_ok=True)

    if input_path.is_dir():
        epub_files = list(input_path.glob("*.epub"))
        if not epub_files:
            typer.echo(f"[yellow]未找到 EPUB 文件: {input_path}[/yellow]", err=True)
            raise typer.Exit(0)
    else:
        epub_files = [input_path]

    typer.echo(f"[bold blue]开始处理 {len(epub_files)} 个 EPUB 文件...[/bold blue]")
    typer.echo(f"输出目录: {output_dir}\n")

    success_count = 0
    fail_count = 0

    for epub_file in epub_files:
        typer.echo(f"[cyan]处理: {epub_file.name}[/cyan]")
        try:
            splitter = EPUBSplitter(str(epub_file))
            info = splitter.analyze()
            typer.echo(f"  标题: {info['title']}")
            typer.echo(f"  作者: {info['author']}")
            typer.echo(f"  章节数: {info['doc_count']}")

            paths = splitter.split(str(output_dir))
            typer.echo(f"  [green]成功生成: {paths[0]}[/green]\n")
            success_count += 1
        except Exception as e:
            typer.echo(f"  [red]失败: {e}[/red]\n")
            fail_count += 1

    typer.echo(f"[bold]完成！成功: {success_count}, 失败: {fail_count}[/bold]")


if __name__ == "__main__":
    app()
