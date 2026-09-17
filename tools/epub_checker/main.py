"""Typer CLI 入口。"""
from __future__ import annotations

import subprocess
from pathlib import Path

import typer

from . import __version__
from .config import Config
from .discovery import EpubCheckNotFound, _resolve_epubcheck_cmd
from .parser import parse_epubcheck_output
from .report import render_console, render_json, render_markdown
from .runner import run_epubcheck


app = typer.Typer(
    name="epub-checker",
    help="检查 EPUB 文件是否符合 EPUB 3.3 出版社标准（基于 EPUBCheck）。",
    add_completion=False,
)


EXIT_OK = 0
EXIT_WARNING_STRICT = 1
EXIT_ERROR = 2
EXIT_FATAL = 3
EXIT_TOOL_ERROR = 4


def _compute_exit_code(counts: dict[str, int], strict: bool) -> int:
    if counts.get("FATAL", 0) > 0:
        return EXIT_FATAL
    if counts.get("ERROR", 0) > 0:
        return EXIT_ERROR
    if strict and counts.get("WARNING", 0) > 0:
        return EXIT_WARNING_STRICT
    return EXIT_OK


def _check_single(
    epub_path: Path,
    config: Config,
    *,
    profile: str | None,
    mode: str | None,
    as_json: bool,
    md_path: Path | None,
    strict: bool,
) -> int:
    """检查单个文件。返回退出码。"""
    rc, stdout = run_epubcheck(epub_path, config, profile=profile, mode=mode)
    result = parse_epubcheck_output(stdout, epub_path)

    if as_json:
        typer.echo(render_json(result))
    else:
        render_console(result, strict)

    if md_path:
        md_path.write_text(render_markdown(result, strict), encoding="utf-8")
        if not as_json:
            typer.echo(f"Markdown report: {md_path}")

    return _compute_exit_code(result.counts, strict)


@app.command()
def check(
    path: Path = typer.Argument(..., help="EPUB 文件或包含 EPUB 的目录"),
    json_output: bool = typer.Option(False, "--json", help="输出 JSON 格式"),
    md: Path | None = typer.Option(None, "--md", help="额外写一份 Markdown 报告到指定路径"),
    strict: bool = typer.Option(False, "--strict", help="WARNING 也算不通过"),
    profile: str = typer.Option("default", "--profile", help="EPUBCheck profile: default/dict/docs/edupub/idx/fix"),
    mode: str = typer.Option("exp", "--mode", help="EPUBCheck mode: exp/mo"),
    config_path: Path = typer.Option(
        Path("config.yaml"), "--config", help="config.yaml 路径"
    ),
) -> None:
    """检查一个或多个 EPUB 文件。"""
    if not path.exists():
        typer.echo(f"文件不存在: {path}", err=True)
        raise typer.Exit(EXIT_TOOL_ERROR)

    config = Config.from_yaml(config_path)

    try:
        _ = _resolve_epubcheck_cmd(config)
    except EpubCheckNotFound as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(EXIT_TOOL_ERROR)

    if path.is_dir():
        epub_files = sorted(path.glob("*.epub"))
        if not epub_files:
            typer.echo(f"目录 {path} 下没有 .epub 文件", err=True)
            raise typer.Exit(EXIT_OK)
        worst = EXIT_OK
        for epub in epub_files:
            typer.echo(f"\n=== {epub.name} ===")
            rc = _check_single(
                epub, config,
                profile=profile, mode=mode,
                as_json=json_output, md_path=md, strict=strict,
            )
            worst = max(worst, rc)
        raise typer.Exit(worst)

    rc = _check_single(
        path, config,
        profile=profile, mode=mode,
        as_json=json_output, md_path=md, strict=strict,
    )
    raise typer.Exit(rc)


@app.command()
def version() -> None:
    """打印工具版本和底层 EPUBCheck 版本。"""
    typer.echo(f"epub-checker: {__version__}")
    try:
        config = Config.from_yaml(Path("config.yaml"))
        cmd = _resolve_epubcheck_cmd(config)
        proc = subprocess.run(
            [*cmd, "--version"],
            capture_output=True, text=True, timeout=10,
        )
        typer.echo(proc.stdout.strip() or proc.stderr.strip())
    except Exception as e:
        typer.echo(f"EPUBCheck 不可用: {e}", err=True)


if __name__ == "__main__":
    app()
