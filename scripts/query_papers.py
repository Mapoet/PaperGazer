#!/usr/bin/env python3
"""
统一论文查询脚本
支持多数据源的论文查询功能
支持按天数、作者、期刊、关键词查询
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.table import Table

from papergazer.config import load_config
from papergazer.utils import (
    query_all_sources_by_days,
    search_papers_by_author,
    search_papers_by_keyword,
    search_papers_by_venue,
    setup_logging,
)

console = Console()


def print_usage():
    """打印使用说明"""
    console.print("[bold yellow]用法:[/bold yellow]")
    console.print("  python scripts/query_papers.py <mode> [options]")
    console.print("\n[bold cyan]查询模式:[/bold cyan]")
    console.print("  days <days> [--ingest] [sources...]")
    console.print("    - 按天数查询论文")
    console.print("    - days: 查询天数（必需）")
    console.print("    - --ingest: 是否执行 ingest 过程（抓取新数据），默认只查询已有数据")
    console.print("    - sources: 数据源列表，可选值：arxiv, crossref, eupmc, unpaywall")
    console.print("\n  author <author_name> [--limit N] [sources...]")
    console.print("    - 按作者名称搜索论文")
    console.print("    - author_name: 作者名称（支持部分匹配）")
    console.print("    - --limit N: 限制返回数量（默认不限制）")
    console.print("    - sources: 数据源列表")
    console.print("\n  venue <venue_name> [--limit N] [sources...]")
    console.print("    - 按期刊/会议名称搜索论文")
    console.print("    - venue_name: 期刊/会议名称（支持部分匹配）")
    console.print("    - --limit N: 限制返回数量（默认不限制）")
    console.print("    - sources: 数据源列表")
    console.print("\n  keyword <keyword> [--in title|abstract|both] [--limit N] [sources...]")
    console.print("    - 按关键词搜索论文（标题和/或摘要）")
    console.print("    - keyword: 搜索关键词（支持部分匹配）")
    console.print(
        "    - --in: 搜索范围，可选：title（仅标题）、abstract（仅摘要）、both（标题和摘要，默认）"
    )
    console.print("    - --limit N: 限制返回数量（默认不限制）")
    console.print("    - sources: 数据源列表")
    console.print("\n[bold cyan]示例:[/bold cyan]")
    console.print("  python scripts/query_papers.py days 7")
    console.print("  python scripts/query_papers.py days 7 --ingest")
    console.print('  python scripts/query_papers.py author "Einstein" --limit 10')
    console.print('  python scripts/query_papers.py venue "Nature" --limit 20')
    console.print(
        '  python scripts/query_papers.py keyword "machine learning" --in both --limit 50'
    )
    console.print('  python scripts/query_papers.py keyword "GNSS" --in title arxiv crossref')


async def query_by_days(args):
    """按天数查询"""
    if len(args) < 1:
        console.print("[bold red]错误: 缺少天数参数[/bold red]")
        return

    try:
        days = int(args[0])
    except ValueError:
        console.print(f"[bold red]错误: 无效的天数: {args[0]}[/bold red]")
        return

    # 解析参数
    ingest = False
    sources = []
    for arg in args[1:]:
        if arg == "--ingest":
            ingest = True
        else:
            sources.append(arg)

    sources = sources if sources else None

    if ingest:
        console.print(f"[bold green]开始抓取并查询最近 {days} 天的论文...[/bold green]")
    else:
        console.print(f"[bold green]开始查询数据库中最近 {days} 天的论文...[/bold green]")

    # 加载配置
    config_path = project_root / "configs" / "config.test.yaml"
    if not config_path.exists():
        config_path = project_root / "configs" / "config.yaml"

    if not config_path.exists():
        console.print("[bold red]配置文件不存在[/bold red]")
        return

    try:
        config = load_config(config_path)
        setup_logging(config.logging)

        # 执行查询
        results = await query_all_sources_by_days(
            config,
            days=days,
            sources=sources,
            max_results={"eupmc": 1000, "unpaywall": 100},
            ingest=ingest,
        )

        # 显示结果
        table = Table(title=f"论文查询结果（最近 {days} 天）")
        table.add_column("数据源", style="cyan")
        table.add_column("状态", style="green")
        table.add_column("记录数", style="yellow")
        table.add_column("备注", style="blue", no_wrap=False, max_width=40)

        for source, result in results.items():
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
        total_count = sum(
            r.get("count", 0) if r.get("status") == "success" else 0
            for r in results.values()
            if r.get("status") == "success" and "count" in r
        )

        console.print(f"\n[bold cyan]总计: {total_count} 条记录[/bold cyan]")

    except Exception as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        import traceback

        console.print(traceback.format_exc())


def query_by_author(args):
    """按作者查询"""
    if len(args) < 1:
        console.print("[bold red]错误: 缺少作者名称参数[/bold red]")
        return

    author_name = args[0]

    # 解析参数
    limit = None
    sources = []
    i = 1
    while i < len(args):
        if args[i] == "--limit" and i + 1 < len(args):
            try:
                limit = int(args[i + 1])
                i += 2
            except ValueError:
                console.print(f"[bold red]错误: 无效的限制数量: {args[i + 1]}[/bold red]")
                return
        else:
            sources.append(args[i])
            i += 1

    sources = sources if sources else None

    console.print(f"[bold green]搜索作者: {author_name}[/bold green]")

    # 加载配置
    config_path = project_root / "configs" / "config.test.yaml"
    if not config_path.exists():
        config_path = project_root / "configs" / "config.yaml"

    if not config_path.exists():
        console.print("[bold red]配置文件不存在[/bold red]")
        return

    try:
        config = load_config(config_path)
        setup_logging(config.logging)

        # 初始化数据库
        from papergazer.store.db import init_db

        init_db(config.store.db_path)

        # 执行搜索
        papers = search_papers_by_author(
            author_name=author_name,
            sources=sources,
            limit=limit,
            db_path=config.store.db_path,
        )

        # 显示结果
        if papers:
            table = Table(title=f"作者搜索结果: {author_name}")
            table.add_column("标题", style="cyan", no_wrap=False, max_width=50)
            table.add_column("来源", style="blue")
            table.add_column("作者", style="yellow", no_wrap=False, max_width=30)
            table.add_column("期刊", style="magenta", max_width=25)
            table.add_column("发布日期", style="green")
            table.add_column("OA", style="yellow")

            for paper in papers:
                title = paper["title"] or "无标题"
                if len(title) > 50:
                    title = title[:47] + "..."
                authors_str = ", ".join(paper["authors"][:3])
                if len(paper["authors"]) > 3:
                    authors_str += "..."
                venue = paper["venue"] or "未知"
                if len(venue) > 25:
                    venue = venue[:22] + "..."
                oa_status = "✅" if paper["is_oa"] else ("❌" if paper["is_oa"] is False else "?")

                table.add_row(
                    title,
                    paper["source"].upper(),
                    authors_str,
                    venue,
                    paper["published_date"] or "未知",
                    oa_status,
                )

            console.print(table)
            console.print(f"\n[bold cyan]共找到 {len(papers)} 篇论文[/bold cyan]")
        else:
            console.print("[yellow]未找到匹配的论文[/yellow]")

    except Exception as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        import traceback

        console.print(traceback.format_exc())


def query_by_venue(args):
    """按期刊查询"""
    if len(args) < 1:
        console.print("[bold red]错误: 缺少期刊名称参数[/bold red]")
        return

    venue_name = args[0]

    # 解析参数
    limit = None
    sources = []
    i = 1
    while i < len(args):
        if args[i] == "--limit" and i + 1 < len(args):
            try:
                limit = int(args[i + 1])
                i += 2
            except ValueError:
                console.print(f"[bold red]错误: 无效的限制数量: {args[i + 1]}[/bold red]")
                return
        else:
            sources.append(args[i])
            i += 1

    sources = sources if sources else None

    console.print(f"[bold green]搜索期刊: {venue_name}[/bold green]")

    # 加载配置
    config_path = project_root / "configs" / "config.test.yaml"
    if not config_path.exists():
        config_path = project_root / "configs" / "config.yaml"

    if not config_path.exists():
        console.print("[bold red]配置文件不存在[/bold red]")
        return

    try:
        config = load_config(config_path)
        setup_logging(config.logging)

        # 初始化数据库
        from papergazer.store.db import init_db

        init_db(config.store.db_path)

        # 执行搜索
        papers = search_papers_by_venue(
            venue_name=venue_name,
            sources=sources,
            limit=limit,
            db_path=config.store.db_path,
        )

        # 显示结果
        if papers:
            table = Table(title=f"期刊搜索结果: {venue_name}")
            table.add_column("标题", style="cyan", no_wrap=False, max_width=50)
            table.add_column("来源", style="blue")
            table.add_column("作者", style="yellow", no_wrap=False, max_width=30)
            table.add_column("发布日期", style="green")
            table.add_column("OA", style="yellow")

            for paper in papers:
                title = paper["title"] or "无标题"
                if len(title) > 50:
                    title = title[:47] + "..."
                authors_str = ", ".join(paper["authors"][:3])
                if len(paper["authors"]) > 3:
                    authors_str += "..."
                oa_status = "✅" if paper["is_oa"] else ("❌" if paper["is_oa"] is False else "?")

                table.add_row(
                    title,
                    paper["source"].upper(),
                    authors_str,
                    paper["published_date"] or "未知",
                    oa_status,
                )

            console.print(table)
            console.print(f"\n[bold cyan]共找到 {len(papers)} 篇论文[/bold cyan]")
        else:
            console.print("[yellow]未找到匹配的论文[/yellow]")

    except Exception as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        import traceback

        console.print(traceback.format_exc())


def query_by_keyword(args):
    """按关键词查询"""
    if len(args) < 1:
        console.print("[bold red]错误: 缺少关键词参数[/bold red]")
        return

    keyword = args[0]

    # 解析参数
    search_in = "both"
    limit = None
    sources = []
    i = 1
    while i < len(args):
        if args[i] == "--in" and i + 1 < len(args):
            search_in = args[i + 1]
            if search_in not in ("title", "abstract", "both"):
                console.print(f"[bold red]错误: 无效的搜索范围: {search_in}[/bold red]")
                return
            i += 2
        elif args[i] == "--limit" and i + 1 < len(args):
            try:
                limit = int(args[i + 1])
                i += 2
            except ValueError:
                console.print(f"[bold red]错误: 无效的限制数量: {args[i + 1]}[/bold red]")
                return
        else:
            sources.append(args[i])
            i += 1

    sources = sources if sources else None

    search_in_text = {"title": "标题", "abstract": "摘要", "both": "标题和摘要"}[search_in]
    console.print(f"[bold green]搜索关键词: {keyword} (范围: {search_in_text})[/bold green]")

    # 加载配置
    config_path = project_root / "configs" / "config.test.yaml"
    if not config_path.exists():
        config_path = project_root / "configs" / "config.yaml"

    if not config_path.exists():
        console.print("[bold red]配置文件不存在[/bold red]")
        return

    try:
        config = load_config(config_path)
        setup_logging(config.logging)

        # 初始化数据库
        from papergazer.store.db import init_db

        init_db(config.store.db_path)

        # 执行搜索
        papers = search_papers_by_keyword(
            keyword=keyword,
            sources=sources,
            search_in=search_in,
            limit=limit,
            db_path=config.store.db_path,
        )

        # 显示结果
        if papers:
            table = Table(title=f"关键词搜索结果: {keyword}")
            table.add_column("标题", style="cyan", no_wrap=False, max_width=50)
            table.add_column("来源", style="blue")
            table.add_column("作者", style="yellow", no_wrap=False, max_width=30)
            table.add_column("期刊", style="magenta", max_width=25)
            table.add_column("发布日期", style="green")
            table.add_column("OA", style="yellow")
            table.add_column("摘要", style="cyan")

            for paper in papers:
                title = paper["title"] or "无标题"
                if len(title) > 50:
                    title = title[:47] + "..."
                authors_str = ", ".join(paper["authors"][:3])
                if len(paper["authors"]) > 3:
                    authors_str += "..."
                venue = paper["venue"] or "未知"
                if len(venue) > 25:
                    venue = venue[:22] + "..."
                oa_status = "✅" if paper["is_oa"] else ("❌" if paper["is_oa"] is False else "?")
                has_abstract = "✓" if paper["has_abstract"] else "✗"

                table.add_row(
                    title,
                    paper["source"].upper(),
                    authors_str,
                    venue,
                    paper["published_date"] or "未知",
                    oa_status,
                    has_abstract,
                )

            console.print(table)
            console.print(f"\n[bold cyan]共找到 {len(papers)} 篇论文[/bold cyan]")
        else:
            console.print("[yellow]未找到匹配的论文[/yellow]")

    except Exception as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        import traceback

        console.print(traceback.format_exc())


async def main():
    """主函数"""
    if len(sys.argv) < 2:
        print_usage()
        return

    mode = sys.argv[1].lower()
    args = sys.argv[2:]

    if mode == "days":
        await query_by_days(args)
    elif mode == "author":
        query_by_author(args)
    elif mode == "venue":
        query_by_venue(args)
    elif mode == "keyword":
        query_by_keyword(args)
    else:
        console.print(f"[bold red]错误: 未知的查询模式: {mode}[/bold red]")
        print_usage()


if __name__ == "__main__":
    asyncio.run(main())
