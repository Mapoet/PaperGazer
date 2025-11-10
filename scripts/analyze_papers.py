#!/usr/bin/env python3
"""
论文分析脚本
支持摘要、作者、OA状态、期刊等分析功能
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from papergazer.config import load_config
from papergazer.utils import (
    analyze_abstracts_by_days,
    analyze_authors_by_days,
    analyze_oa_status_by_days,
    analyze_venues_by_days,
    get_papers_by_days,
)
from papergazer.utils import setup_logging
from rich.console import Console
from rich.table import Table

console = Console()


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器
    
    Returns:
        argparse.ArgumentParser: 配置好的参数解析器
    """
    parser = argparse.ArgumentParser(
        description="论文分析脚本 - 支持摘要、作者、OA状态、期刊等分析功能",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 作者分析（最近7天）
  %(prog)s authors 7
  
  # 摘要分析（最近30天，仅arxiv和crossref）
  %(prog)s abstracts 30 --sources arxiv crossref
  
  # OA状态分析（最近7天）
  %(prog)s oa 7
  
  # 期刊/会议分析（最近30天）
  %(prog)s venues 30 --top 20
  
  # 论文列表（最近7天，限制100条）
  %(prog)s list 7 --limit 100
  
  # 指定配置文件
  %(prog)s authors 7 --config configs/config.prod.yaml
""",
    )

    # 分析类型（必需位置参数）
    parser.add_argument(
        "analysis_type",
        type=str,
        choices=["authors", "abstracts", "oa", "venues", "list"],
        help="分析类型: authors(作者), abstracts(摘要), oa(开放获取), venues(期刊/会议), list(论文列表)",
    )

    # 天数（必需位置参数）
    parser.add_argument(
        "days",
        type=int,
        help="查询天数（正整数）",
    )

    # 数据源（可选参数）
    parser.add_argument(
        "-s",
        "--sources",
        type=str,
        nargs="+",
        choices=["arxiv", "crossref", "eupmc"],
        default=None,
        help="指定数据源列表（默认：所有数据源）",
    )

    # 限制数量（可选参数，主要用于list类型）
    parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=100,
        help="限制返回数量（默认：100，仅用于list类型）",
    )

    # Top N（可选参数，用于authors和venues类型）
    parser.add_argument(
        "-t",
        "--top",
        type=int,
        default=10,
        help="显示Top N结果（默认：10，用于authors和venues类型）",
    )

    # 配置文件路径（可选参数）
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="配置文件路径（默认：自动查找config.test.yaml或config.yaml）",
    )

    # 输出格式（可选参数）
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        choices=["table", "json", "csv"],
        default="table",
        help="输出格式（默认：table）",
    )

    # 详细输出（可选参数）
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="详细输出模式",
    )

    return parser


def validate_args(args: argparse.Namespace) -> None:
    """验证参数有效性
    
    Args:
        args: 解析后的参数
        
    Raises:
        ValueError: 参数无效时抛出
    """
    if args.days <= 0:
        raise ValueError(f"天数必须为正整数，当前值: {args.days}")
    
    if args.limit is not None and args.limit <= 0:
        raise ValueError(f"限制数量必须为正整数，当前值: {args.limit}")
    
    if args.top <= 0:
        raise ValueError(f"Top N必须为正整数，当前值: {args.top}")


def main():
    """主函数"""
    # 创建并解析参数
    parser = create_parser()
    args = parser.parse_args()

    try:
        # 验证参数
        validate_args(args)
    except ValueError as e:
        console.print(f"[bold red]参数错误: {e}[/bold red]")
        parser.print_help()
        return 1

    # 提取参数
    analysis_type = args.analysis_type.lower()
    days = args.days
    sources = args.sources
    limit = args.limit
    top_n = args.top
    output_format = args.output
    verbose = args.verbose

    if verbose:
        console.print(f"[dim]分析类型: {analysis_type}[/dim]")
        console.print(f"[dim]查询天数: {days}[/dim]")
        console.print(f"[dim]数据源: {sources or '全部'}[/dim]")
        console.print(f"[dim]输出格式: {output_format}[/dim]")

    console.print(f"[bold green]开始分析最近 {days} 天的论文...[/bold green]")

    # 加载配置并初始化数据库
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            console.print(f"[bold red]指定的配置文件不存在: {config_path}[/bold red]")
            return 1
    else:
        config_path = project_root / "configs" / "config.test.yaml"
        if not config_path.exists():
            config_path = project_root / "configs" / "config.yaml"
        
        if not config_path.exists():
            console.print(f"[bold red]配置文件不存在，请先创建配置文件[/bold red]")
            console.print(f"参考: configs/config.yaml.example")
            return 1

    try:
        config = load_config(config_path)
        setup_logging(config.logging)
        
        # 初始化数据库
        from papergazer.store.db import init_db
        init_db(config.store.db_path)
        
        if verbose:
            console.print(f"[dim]配置文件: {config_path}[/dim]")
            console.print(f"[dim]数据库路径: {config.store.db_path}[/dim]")
        
    except Exception as e:
        console.print(f"[bold red]配置加载失败: {e}[/bold red]")
        return 1

    try:
        if analysis_type == "authors":
            result = analyze_authors_by_days(days, sources, top_n=top_n)

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
            result = analyze_venues_by_days(days, sources, top_n=top_n)

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

            display_papers = papers[:limit] if limit else papers
            
            for paper in display_papers:
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
            console.print(f"\n[cyan]共显示 {len(display_papers)} 条记录[/cyan]")
            if len(papers) > len(display_papers):
                console.print(f"[dim]（实际查询到 {len(papers)} 条，已限制显示）[/dim]")

        else:
            console.print(f"[bold red]未知的分析类型: {analysis_type}[/bold red]")
            console.print("支持的类型: authors, abstracts, oa, venues, list")
            return 1

    except Exception as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

