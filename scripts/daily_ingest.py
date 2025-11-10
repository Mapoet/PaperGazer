#!/usr/bin/env python3
"""
每日巡检脚本
执行所有数据源的增量抓取任务
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from papergazer.config import load_config
from papergazer.store.db import init_db
from papergazer.utils import (
    daily_ingest_all,
    daily_ingest_sources,
    download_all_papers,
    download_arxiv_papers,
    download_oa_papers,
)
from papergazer.utils import setup_logging
from rich.console import Console
from rich.table import Table

console = Console()

# 有效的数据源列表
VALID_SOURCES = ["arxiv", "crossref", "eupmc", "unpaywall"]


async def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="PaperGazer 每日巡检脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 执行所有数据源的巡检
  python scripts/daily_ingest.py

  # 执行指定数据源的巡检
  python scripts/daily_ingest.py --sources arxiv crossref

  # 执行巡检并下载论文
  python scripts/daily_ingest.py --download

  # 只下载 arXiv 论文
  python scripts/daily_ingest.py --download --download-arxiv-only

  # 只下载 OA 论文
  python scripts/daily_ingest.py --download --download-oa-only

  # 下载最近7天的论文，最多100篇
  python scripts/daily_ingest.py --download --download-days 7 --download-limit 100
        """,
    )

    parser.add_argument(
        "--sources",
        nargs="+",
        choices=VALID_SOURCES,
        help="指定要巡检的数据源（可多个）",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="巡检完成后下载论文（arXiv 和 OA 来源）",
    )
    parser.add_argument(
        "--download-arxiv-only",
        action="store_true",
        help="只下载 arXiv 论文（需要 --download）",
    )
    parser.add_argument(
        "--download-oa-only",
        action="store_true",
        help="只下载 OA 论文（需要 --download）",
    )
    parser.add_argument(
        "--download-days",
        type=int,
        help="下载最近 N 天的论文（默认：所有未下载的）。如果指定此参数，会自动启用 --download",
    )
    parser.add_argument(
        "--download-limit",
        type=int,
        help="限制下载数量（每个来源）。如果指定此参数，会自动启用 --download",
    )

    args = parser.parse_args()

    # 如果指定了下载相关参数但没有 --download，自动启用下载
    if not args.download and (args.download_days is not None or args.download_limit is not None 
                              or args.download_arxiv_only or args.download_oa_only):
        args.download = True
        console.print("[yellow]检测到下载相关参数，自动启用 --download[/yellow]")

    sources = args.sources

    if sources:
        console.print(f"[bold green]开始执行每日巡检任务（数据源: {', '.join(sources)}）...[/bold green]")
    else:
        console.print("[bold green]开始执行每日巡检任务（所有数据源）...[/bold green]")

    # 加载配置
    config_path = project_root / "configs" / "config.test.yaml"
    if not config_path.exists():
        console.print(f"[bold red]配置文件不存在: {config_path}[/bold red]")
        return

    try:
        config = load_config(config_path)
        setup_logging(config.logging)

        # 初始化数据库
        init_db(config.store.db_path)
        console.print(f"[green]数据库已初始化: {config.store.db_path}[/green]")

        # 执行巡检
        if sources:
            results = await daily_ingest_sources(config, sources)
        else:
            results = await daily_ingest_all(config)

        # 显示结果
        table = Table(title="每日巡检结果")
        table.add_column("数据源", style="cyan")
        table.add_column("状态", style="green")
        table.add_column("记录数", style="yellow")
        table.add_column("备注", style="blue", no_wrap=False, max_width=40)

        for source, result in results["results"].items():
            status = result.get("status", "unknown")
            if status == "success":
                if source == "unpaywall":
                    stats = result.get("stats", {})
                    count = stats.get("total", 0)
                    oa_count = stats.get("oa_count", 0)
                    note = f"OA: {oa_count}, 非OA: {stats.get('non_oa_count', 0)}"
                else:
                    count = result.get("count", 0)
                    note = ""
                status_display = "✅ 成功"
            else:
                count = 0
                error = result.get("error", "未知错误")
                note = error[:37] + "..." if len(error) > 40 else error
                status_display = "❌ 失败"

            table.add_row(source.upper(), status_display, str(count), note)

        console.print(table)

        # 统计信息
        total_count = results.get("total_count", 0)
        console.print(f"\n[bold cyan]总计: {total_count} 条记录[/bold cyan]")
        console.print(f"[cyan]执行时间: {results.get('timestamp', '未知')}[/cyan]")

        # 如果启用了下载功能
        if args.download:
            console.print("\n[bold green]开始下载论文...[/bold green]")

            include_arxiv = not args.download_oa_only
            include_oa = not args.download_arxiv_only

            download_stats = await download_all_papers(
                config,
                days=args.download_days,
                limit=args.download_limit,
                include_arxiv=include_arxiv,
                include_oa=include_oa,
            )

            # 显示下载结果
            download_table = Table(title="论文下载结果")
            download_table.add_column("来源", style="cyan")
            download_table.add_column("总数", style="yellow")
            download_table.add_column("成功", style="green")
            download_table.add_column("失败", style="red")

            for source, stats in download_stats["results"].items():
                download_table.add_row(
                    source.upper(),
                    str(stats.get("total", 0)),
                    str(stats.get("success", 0)),
                    str(stats.get("error", 0)),
                )

            console.print(download_table)
            console.print(
                f"\n[bold cyan]下载总计: 成功 {download_stats['total_success']} 篇, "
                f"失败 {download_stats['total_error']} 篇[/bold cyan]"
            )

    except Exception as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        import traceback

        console.print(traceback.format_exc())
        raise


if __name__ == "__main__":
    asyncio.run(main())

