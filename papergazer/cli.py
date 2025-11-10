"""
命令行接口：基于 Typer
"""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from papergazer.config import load_config, Settings
from papergazer.core import fetch_by_identifier, run_daily_check
from papergazer.store.db import init_db
from papergazer.utils import setup_logging

app = typer.Typer(help="PaperGazer: CNS + arXiv 每日巡检与 OA 全文抓取系统")
console = Console()


@app.command()
def check(
    config_path: str = typer.Option(
        "configs/config.yaml",
        "--config",
        "-c",
        help="配置文件路径",
    ),
) -> None:
    """
    执行每日巡检（arXiv + CNS via Crossref）
    """
    try:
        # 加载配置
        config = load_config(config_path)
        setup_logging(config.logging)

        # 初始化数据库
        init_db(config.store.db_path)

        # 执行巡检
        console.print("[bold green]开始每日巡检...[/bold green]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("巡检中...", total=None)
            results = asyncio.run(run_daily_check(config))
            progress.update(task, completed=100)

        # 显示结果
        table = Table(title="巡检结果")
        table.add_column("数据源", style="cyan")
        table.add_column("处理记录数", style="magenta")

        for source, count in results.items():
            table.add_row(source, str(count))

        console.print(table)
        console.print("[bold green]巡检完成！[/bold green]")

    except Exception as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        raise typer.Exit(1)


@app.command()
def fetch(
    identifier: str = typer.Argument(..., help="DOI 或 arXiv id"),
    config_path: str = typer.Option(
        "configs/config.yaml",
        "--config",
        "-c",
        help="配置文件路径",
    ),
) -> None:
    """
    按需抓取 OA 全文或回退摘要
    """
    try:
        # 加载配置
        config = load_config(config_path)
        setup_logging(config.logging)

        # 初始化数据库
        init_db(config.store.db_path)

        # 执行抓取
        console.print(f"[bold green]开始抓取: {identifier}[/bold green]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("抓取中...", total=None)
            result = asyncio.run(fetch_by_identifier(identifier, config))
            progress.update(task, completed=100)

        # 显示结果
        if result["success"]:
            console.print("[bold green]抓取成功！[/bold green]")
            console.print(f"数据源: {result['source']}")

            if result["pdf_path"]:
                console.print(f"PDF 路径: {result['pdf_path']}")
            if result["xml_path"]:
                console.print(f"XML 路径: {result['xml_path']}")
            if result["abstract_only"]:
                console.print("[yellow]仅获取到摘要（非 OA）[/yellow]")
        else:
            console.print(f"[bold red]抓取失败: {result.get('error', '未知错误')}[/bold red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        raise typer.Exit(1)


@app.command()
def search(
    query: str = typer.Option(..., "--query", "-q", help="搜索查询"),
    config_path: str = typer.Option(
        "configs/config.yaml",
        "--config",
        "-c",
        help="配置文件路径",
    ),
) -> None:
    """
    搜索论文（透传 Crossref / arXiv 查询）
    """
    console.print("[yellow]搜索功能待实现[/yellow]")
    # TODO: 实现搜索功能


@app.command()
def export(
    since: str = typer.Option(..., "--since", help="起始日期（YYYY-MM-DD）"),
    format: str = typer.Option("csv", "--format", "-f", help="导出格式（csv/json）"),
    config_path: str = typer.Option(
        "configs/config.yaml",
        "--config",
        "-c",
        help="配置文件路径",
    ),
) -> None:
    """
    导出新论文清单
    """
    console.print("[yellow]导出功能待实现[/yellow]")
    # TODO: 实现导出功能


if __name__ == "__main__":
    app()

