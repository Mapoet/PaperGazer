#!/usr/bin/env python3
"""
每日巡检脚本
执行所有数据源的增量抓取任务
"""

import argparse
import asyncio
import sys
from datetime import date, datetime, timedelta, timezone
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

  # 查询最近30天的论文（忽略检查点，更新已有论文）
  # 注意：如果时间跨度 > 3天，会自动分批处理以避免数据量过大
  python scripts/daily_ingest.py --days 30

  # 查询指定日期范围的论文（忽略检查点）
  # 如果时间跨度大于3天，将自动分批处理（每批3天）
  python scripts/daily_ingest.py --since 2025-01-01 --until 2025-01-31

  # 查询指定时间范围的论文（忽略检查点）
  python scripts/daily_ingest.py --since 2025-01-01T00:00:00 --until 2025-01-31T23:59:59

  # 使用指定的配置文件
  python scripts/daily_ingest.py --config configs/my_config.yaml
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
    parser.add_argument(
        "--since",
        type=str,
        help="起始时间/日期（格式: YYYY-MM-DD 或 YYYY-MM-DDTHH:MM:SS），如果指定则忽略检查点过滤",
    )
    parser.add_argument(
        "--until",
        type=str,
        help="结束时间/日期（格式: YYYY-MM-DD 或 YYYY-MM-DDTHH:MM:SS），默认为当前时间",
    )
    parser.add_argument(
        "--days",
        type=int,
        help="查询最近 N 天的论文（等同于 --since 为 N 天前，会忽略检查点过滤）",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="配置文件路径（默认: configs/config.test.yaml 或 configs/config.yaml）",
    )

    args = parser.parse_args()
    
    # 检查参数冲突
    if args.days is not None and args.since is not None:
        console.print("[bold yellow]警告: 同时指定了 --days 和 --since，将使用 --days 参数[/bold yellow]")
    
    # 解析时间范围参数
    since = None
    until = None
    
    if args.days is not None:
        # 如果指定了 --days，计算起始时间
        since = datetime.now(timezone.utc) - timedelta(days=args.days)
        console.print(f"[yellow]指定了 --days {args.days}，将忽略检查点过滤，查询从 {since.date()} 开始的论文[/yellow]")
    elif args.since is not None:
        # 解析 --since 参数
        try:
            if "T" in args.since or " " in args.since:
                since = datetime.fromisoformat(args.since.replace(" ", "T"))
            else:
                since = datetime.combine(date.fromisoformat(args.since), datetime.min.time())
            if since.tzinfo is None:
                since = since.replace(tzinfo=timezone.utc)
            console.print(f"[yellow]指定了起始时间: {since}，将忽略检查点过滤[/yellow]")
        except ValueError as e:
            console.print(f"[bold red]错误: 无法解析 --since 参数: {e}[/bold red]")
            console.print("格式应为: YYYY-MM-DD 或 YYYY-MM-DDTHH:MM:SS")
            return
    
    if args.until is not None:
        # 解析 --until 参数
        try:
            if "T" in args.until or " " in args.until:
                until = datetime.fromisoformat(args.until.replace(" ", "T"))
            else:
                until = datetime.combine(date.fromisoformat(args.until), datetime.max.time())
            if until.tzinfo is None:
                until = until.replace(tzinfo=timezone.utc)
            console.print(f"[yellow]指定了结束时间: {until}[/yellow]")
        except ValueError as e:
            console.print(f"[bold red]错误: 无法解析 --until 参数: {e}[/bold red]")
            console.print("格式应为: YYYY-MM-DD 或 YYYY-MM-DDTHH:MM:SS")
            return

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
    if args.config:
        # 用户指定了配置文件
        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = project_root / config_path
    else:
        # 使用默认配置文件（优先使用 config.test.yaml）
        config_path = project_root / "configs" / "config.test.yaml"
        if not config_path.exists():
            config_path = project_root / "configs" / "config.yaml"
    
    if not config_path.exists():
        console.print(f"[bold red]配置文件不存在: {config_path}[/bold red]")
        console.print("[yellow]提示: 请复制 configs/config.yaml.example 为 configs/config.yaml 并修改相应配置[/yellow]")
        return

    try:
        console.print(f"[cyan]使用配置文件: {config_path}[/cyan]")
        config = load_config(config_path)
        setup_logging(config.logging)

        # 初始化数据库
        init_db(config.store.db_path)
        console.print(f"[green]数据库已初始化: {config.store.db_path}[/green]")

        # 检查时间跨度，如果太长则分批处理
        batch_size_days = 3  # 每批处理 3 天
        
        if since is not None and until is not None:
            time_span = (until - since).days
        elif since is not None:
            time_span = (datetime.now(timezone.utc) - since).days
        else:
            time_span = 0
        
        # 如果时间跨度大于 batch_size_days 天，进行分批处理
        if time_span > batch_size_days:
            console.print(f"[yellow]时间跨度为 {time_span} 天，将分批处理（每批 {batch_size_days} 天）以避免数据量过大[/yellow]")
            
            # 初始化合并结果
            merged_results = {
                "results": {},
                "total_count": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            # 计算批次
            start_time = since if since else datetime.now(timezone.utc) - timedelta(days=time_span)
            end_time = until if until else datetime.now(timezone.utc)
            
            current_start = start_time
            batch_num = 0
            
            while current_start < end_time:
                batch_num += 1
                current_end = min(current_start + timedelta(days=batch_size_days), end_time)
                
                console.print(f"\n[cyan]批次 {batch_num}: {current_start.date()} 至 {current_end.date()}[/cyan]")
                
                # 执行当前批次的巡检
                if sources:
                    batch_results = await daily_ingest_sources(config, sources, since=current_start, until=current_end)
                else:
                    batch_results = await daily_ingest_all(config, since=current_start, until=current_end)
                
                # 合并结果
                for source, result in batch_results["results"].items():
                    if source not in merged_results["results"]:
                        merged_results["results"][source] = {
                            "status": result.get("status"),
                            "count": 0,
                            "stats": {},
                            "error": result.get("error"),
                        }
                    
                    # 累加计数
                    if result.get("status") == "success":
                        merged_results["results"][source]["count"] = (
                            merged_results["results"][source].get("count", 0) + result.get("count", 0)
                        )
                        
                        # 如果有 stats（如 unpaywall），合并统计信息
                        if "stats" in result:
                            if not merged_results["results"][source].get("stats"):
                                merged_results["results"][source]["stats"] = {}
                            
                            for key, value in result["stats"].items():
                                merged_results["results"][source]["stats"][key] = (
                                    merged_results["results"][source]["stats"].get(key, 0) + value
                                )
                
                merged_results["total_count"] += batch_results.get("total_count", 0)
                
                # 移动到下一批
                current_start = current_end
            
            console.print(f"\n[bold green]分批处理完成，共 {batch_num} 批[/bold green]")
            results = merged_results
        else:
            # 时间跨度不大，正常执行
            if sources:
                results = await daily_ingest_sources(config, sources, since=since, until=until)
            else:
                results = await daily_ingest_all(config, since=since, until=until)

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

