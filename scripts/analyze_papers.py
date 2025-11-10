#!/usr/bin/env python3
"""
论文分析脚本
支持摘要、作者、OA状态、期刊等分析功能
"""

import json
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from papergazer.utils import (
    analyze_abstracts_by_days,
    analyze_authors_by_days,
    analyze_oa_status_by_days,
    analyze_venues_by_days,
    get_papers_by_days,
)
from rich.console import Console
from rich.table import Table

console = Console()


def main():
    """主函数"""
    if len(sys.argv) < 3:
        console.print("[bold yellow]用法:[/bold yellow]")
        console.print("  python scripts/analyze_papers.py <analysis_type> <days> [sources...]")
        console.print("\n[bold cyan]分析类型:[/bold cyan]")
        console.print("  authors    - 作者分析")
        console.print("  abstracts  - 摘要分析")
        console.print("  oa         - OA状态分析")
        console.print("  venues     - 期刊/会议分析")
        console.print("  list       - 论文列表")
        console.print("\n[bold cyan]参数:[/bold cyan]")
        console.print("  days: 查询天数（必需）")
        console.print("  sources: 数据源列表，可选值：arxiv, crossref, eupmc")
        console.print("          如果不指定，则分析所有数据源")
        console.print("\n[bold cyan]示例:[/bold cyan]")
        console.print("  python scripts/analyze_papers.py authors 7")
        console.print("  python scripts/analyze_papers.py abstracts 30 arxiv crossref")
        console.print("  python scripts/analyze_papers.py oa 7")
        console.print("  python scripts/analyze_papers.py venues 30")
        console.print("  python scripts/analyze_papers.py list 7 10")
        return

    analysis_type = sys.argv[1].lower()
    days = int(sys.argv[2])
    sources = sys.argv[3:] if len(sys.argv) > 3 else None
    limit = int(sys.argv[4]) if len(sys.argv) > 4 and analysis_type == "list" else None

    console.print(f"[bold green]开始分析最近 {days} 天的论文...[/bold green]")

    try:
        if analysis_type == "authors":
            result = analyze_authors_by_days(days, sources, top_n=10)

            table = Table(title=f"作者分析（最近 {days} 天）")
            table.add_column("排名", style="cyan")
            table.add_column("作者", style="yellow")
            table.add_column("论文数", style="green")
            table.add_column("机构", style="blue", max_width=30)

            for idx, author in enumerate(result["top_authors"], 1):
                affiliations = ", ".join(author["affiliations"][:2])
                if len(author["affiliations"]) > 2:
                    affiliations += "..."
                table.add_row(
                    str(idx),
                    author["name"],
                    str(author["count"]),
                    affiliations or "未知",
                )

            console.print(table)
            console.print(f"\n[cyan]总作者数: {result['total_authors']}[/cyan]")
            console.print(f"[cyan]总论文数: {result['total_papers']}[/cyan]")

        elif analysis_type == "abstracts":
            result = analyze_abstracts_by_days(days, sources)

            console.print(f"\n[bold cyan]摘要分析（最近 {days} 天）[/bold cyan]")
            console.print(f"  总论文数: {result['total_papers']}")
            console.print(f"  有摘要: {result['abstracts_with']}")
            console.print(f"  无摘要: {result['abstracts_without']}")
            console.print(f"  覆盖率: {result['coverage_rate']:.2%}")
            console.print(f"  平均长度: {result['average_length']:.0f} 字符")
            console.print(f"  最短: {result['min_length']} 字符")
            console.print(f"  最长: {result['max_length']} 字符")

            if result["source_stats"]:
                table = Table(title="各数据源摘要统计")
                table.add_column("数据源", style="cyan")
                table.add_column("有摘要", style="green")
                table.add_column("无摘要", style="yellow")
                table.add_column("平均长度", style="blue")

                for source, stats in result["source_stats"].items():
                    avg_len = (
                        stats["total_length"] / stats["with"]
                        if stats["with"] > 0
                        else 0
                    )
                    table.add_row(
                        source.upper(),
                        str(stats["with"]),
                        str(stats["without"]),
                        f"{avg_len:.0f}",
                    )

                console.print(table)

        elif analysis_type == "oa":
            result = analyze_oa_status_by_days(days, sources)

            console.print(f"\n[bold cyan]OA状态分析（最近 {days} 天）[/bold cyan]")
            console.print(f"  总论文数: {result['total_papers']}")
            console.print(f"  开放获取: {result['oa_count']}")
            console.print(f"  非开放获取: {result['non_oa_count']}")
            console.print(f"  未知: {result['unknown_count']}")
            console.print(f"  OA率: {result['oa_rate']:.2%}")

            if result["oa_sources"]:
                console.print(f"\n[cyan]OA来源分布:[/cyan]")
                for source, count in result["oa_sources"].items():
                    console.print(f"  {source}: {count}")

            if result["source_stats"]:
                table = Table(title="各数据源OA统计")
                table.add_column("数据源", style="cyan")
                table.add_column("OA", style="green")
                table.add_column("非OA", style="yellow")
                table.add_column("未知", style="blue")
                table.add_column("总计", style="magenta")

                for source, stats in result["source_stats"].items():
                    table.add_row(
                        source.upper(),
                        str(stats["oa"]),
                        str(stats["non_oa"]),
                        str(stats["unknown"]),
                        str(stats["total"]),
                    )

                console.print(table)

        elif analysis_type == "venues":
            result = analyze_venues_by_days(days, sources, top_n=10)

            table = Table(title=f"期刊/会议分析（最近 {days} 天）")
            table.add_column("排名", style="cyan")
            table.add_column("期刊/会议", style="yellow", no_wrap=False, max_width=40)
            table.add_column("论文数", style="green")
            table.add_column("数据源", style="blue")

            for idx, venue_info in enumerate(result["top_venues"], 1):
                sources_str = ", ".join(venue_info["sources"])
                table.add_row(
                    str(idx),
                    venue_info["venue"],
                    str(venue_info["count"]),
                    sources_str,
                )

            console.print(table)
            console.print(f"\n[cyan]总期刊/会议数: {result['total_venues']}[/cyan]")
            console.print(f"[cyan]总论文数: {result['total_papers']}[/cyan]")

        elif analysis_type == "list":
            papers = get_papers_by_days(days, sources, limit=limit)

            table = Table(title=f"论文列表（最近 {days} 天）")
            table.add_column("标题", style="cyan", no_wrap=False, max_width=40)
            table.add_column("来源", style="blue")
            table.add_column("DOI", style="magenta", max_width=25)
            table.add_column("发布日期", style="green")
            table.add_column("OA", style="yellow")
            table.add_column("摘要", style="cyan")

            for paper in papers[:limit if limit else 20]:
                title = paper["title"] or "无标题"
                if len(title) > 40:
                    title = title[:37] + "..."
                doi = paper["doi"] or "无"
                if len(doi) > 25:
                    doi = doi[:22] + "..."
                oa_status = "✅" if paper["is_oa"] else ("❌" if paper["is_oa"] is False else "?")
                has_abstract = "✓" if paper["has_abstract"] else "✗"

                table.add_row(
                    title,
                    paper["source"].upper(),
                    doi,
                    paper["published_date"] or "未知",
                    oa_status,
                    has_abstract,
                )

            console.print(table)
            console.print(f"\n[cyan]共显示 {len(papers)} 条记录[/cyan]")

        else:
            console.print(f"[bold red]未知的分析类型: {analysis_type}[/bold red]")
            console.print("支持的类型: authors, abstracts, oa, venues, list")

    except Exception as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        import traceback

        console.print(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()

