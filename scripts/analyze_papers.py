#!/usr/bin/env python3
"""
论文分析脚本
支持摘要、作者、OA状态、期刊等分析功能
"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.table import Table
from rich.text import Text

from papergazer.analytics.citation import (  # type: ignore[import]
    analyze_collaboration_network as analyze_collab_module,
)
from papergazer.analytics.citation import (
    summarize_citation_network as summarize_citation_module,
)
from papergazer.analytics.concepts import (
    analyze_concepts as analyze_concepts_module,  # type: ignore[import]
)
from papergazer.analytics.oa import monitor_oa as monitor_oa_module  # type: ignore[import]
from papergazer.analytics.topics import (
    analyze_topic_trends as analyze_topics_module,  # type: ignore[import]
)
from papergazer.config import load_config
from papergazer.utils import (
    analyze_abstracts_by_days,
    analyze_authors_by_days,
    analyze_venues_by_days,
    get_papers_by_days,
    setup_logging,
)

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

  # 同时执行作者与期刊分析（最近30天）
  %(prog)s authors venues 30 --top 20

  # 概念热度与 OA 仪表盘（窗口 60 天）
  %(prog)s concepts oa 30 --window-days 60 --concept-persist

  # 论文列表（最近7天，限制100条）
  %(prog)s list 7 --limit 100

  # 指定配置文件
  %(prog)s authors 7 --config configs/config.prod.yaml
""",
    )

    # 分析类型（必需位置参数）
    parser.add_argument(
        "analysis_types",
        type=str,
        nargs="+",
        choices=[
            "authors",
            "abstracts",
            "oa",
            "venues",
            "list",
            "concepts",
            "topics",
            "citation",
            "collaboration",
        ],
        help="指定要执行的一个或多个分析类型",
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

    # 限制数量（可选参数，主要用于 list / concepts 类型）
    parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=100,
        help="限制返回数量（默认：100，用于 list 类型，可作为概念分析默认 limit）",
    )

    parser.add_argument(
        "--concept-limit",
        type=int,
        help="概念分析处理的最大论文数量（覆盖 --limit）",
    )

    # Top N（可选参数，用于 authors / venues / concepts 类型）
    parser.add_argument(
        "-t",
        "--top",
        type=int,
        default=10,
        help="显示 Top N 结果（默认：10，用于 authors / venues / concepts）",
    )

    parser.add_argument(
        "--window-days",
        type=int,
        help="高级分析窗口大小（概念热度 / OA 仪表盘，默认同 days）",
    )

    parser.add_argument(
        "--concept-dry-run",
        action="store_true",
        help="概念分析 dry-run，不写入数据库",
    )

    parser.add_argument(
        "--concept-persist",
        action="store_true",
        help="将概念热度写入 analytics_concepts",
    )

    parser.add_argument(
        "--oa-dry-run",
        action="store_true",
        help="OA 仪表盘 dry-run，不写入数据库",
    )

    parser.add_argument(
        "--oa-persist",
        action="store_true",
        help="将 OA 指标写入 analytics_oa",
    )

    parser.add_argument(
        "--oa-window-days",
        type=int,
        help="OA 仪表盘的窗口大小（覆盖 --window-days）",
    )

    parser.add_argument(
        "--topics-granularity",
        choices=["year", "quarter"],
        default="year",
        help="主题趋势时间粒度（year/quarter）",
    )
    parser.add_argument(
        "--topics-since-years",
        type=int,
        default=3,
        help="主题趋势统计跨度（单位：年）",
    )
    parser.add_argument(
        "--citation-since-days",
        type=int,
        help="引用网络统计近 N 天产生的引用边",
    )
    parser.add_argument(
        "--citation-top",
        type=int,
        default=10,
        help="引用网络输出 Top-N 节点数量（默认 10）",
    )
    parser.add_argument(
        "--collab-since-days",
        type=int,
        help="机构合作网络统计近 N 天新增论文",
    )
    parser.add_argument(
        "--collab-min-weight",
        type=int,
        default=1,
        help="机构合作最少出现次数（默认 1）",
    )
    parser.add_argument(
        "--collab-top",
        type=int,
        default=20,
        help="机构合作输出 Top-N 边数量（默认 20）",
    )

    # 配置文件路径（可选参数）
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="配置文件路径（默认：自动查找 config.test.yaml 或 config.yaml）",
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

    analysis_types = [atype.lower() for atype in args.analysis_types]
    days = args.days
    sources = args.sources
    limit = args.limit
    top_n = args.top
    output_format = args.output
    verbose = args.verbose

    if verbose:
        console.print(f"[dim]分析类型: {', '.join(analysis_types)}[/dim]")
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
            console.print("[bold red]配置文件不存在，请先创建配置文件[/bold red]")
            console.print("参考: configs/config.yaml.example")
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
        for analysis_type in analysis_types:
            console.print(f"\n[bold green]>>> 开始 {analysis_type} 分析[/bold green]")

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
                        avg_len = stats["total_length"] / stats["with"] if stats["with"] > 0 else 0
                        table.add_row(
                            source.upper(),
                            str(stats["with"]),
                            str(stats["without"]),
                            f"{avg_len:.0f}",
                        )

                    console.print(table)

            elif analysis_type == "oa":
                oa_window = args.oa_window_days or args.window_days or days
                oa_result = monitor_oa_module(
                    config,
                    window_days=oa_window,
                    sources=sources,
                    persist=args.oa_persist,
                    dry_run=args.oa_dry_run,
                )

                table = Table(
                    title=f"OA 指标：{oa_result['window_start'].date()} ~ {oa_result['window_end'].date()}"
                )
                table.add_column("指标", style="cyan")
                table.add_column("数值", style="green", justify="right")

                table.add_row("论文总数", str(oa_result["total_count"]))
                table.add_row("OA 总数", str(oa_result["oa_count"]))
                table.add_row("Gold/Hybrid", str(oa_result["gold_count"]))
                table.add_row("Green", str(oa_result["green_count"]))
                table.add_row("Bronze", str(oa_result["bronze_count"]))
                table.add_row("数据链接数", str(oa_result["data_link_count"]))
                table.add_row("代码链接数", str(oa_result["code_link_count"]))
                table.add_row("dry_run", str(args.oa_dry_run))

                console.print(table)

                if oa_result.get("license_counter"):
                    license_table = Table(title="常见许可")
                    license_table.add_column("License/URL", style="yellow")
                    license_table.add_column("Count", style="green", justify="right")
                    for name, cnt in oa_result["license_counter"].most_common(10):
                        license_table.add_row(name, str(cnt))
                    console.print(license_table)

                if oa_result.get("oa_status_counter"):
                    status_table = Table(title="OA 状态分布")
                    status_table.add_column("Status", style="magenta")
                    status_table.add_column("Count", style="green", justify="right")
                    for status_name, cnt in oa_result["oa_status_counter"].most_common():
                        status_table.add_row(status_name, str(cnt))
                    console.print(status_table)

                if oa_result.get("persisted"):
                    console.print("[green]已写入 analytics_oa 表。[/green]")
                else:
                    console.print(
                        f"[cyan]persist={args.oa_persist}, dry_run={args.oa_dry_run}[/cyan]"
                    )

            elif analysis_type == "venues":
                result = analyze_venues_by_days(days, sources, top_n=top_n)

                table = Table(title=f"期刊/会议分析（最近 {days} 天）")
                table.add_column("排名", style="cyan", justify="right")
                table.add_column("期刊/会议", style="yellow")
                table.add_column("论文数", style="green", justify="right")
                table.add_column("数据源", style="blue")

                for idx, venue_info in enumerate(result["top_venues"], 1):
                    sources_str = ", ".join(venue_info["sources"])
                    venue_text = Text(venue_info["venue"], style="yellow")
                    table.add_row(
                        str(idx),
                        venue_text,
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
                    oa_status = (
                        "✅" if paper["is_oa"] else ("❌" if paper["is_oa"] is False else "?")
                    )
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

            elif analysis_type == "concepts":
                concept_limit = args.concept_limit if args.concept_limit is not None else limit
                window_days = args.window_days or days
                concept_result = analyze_concepts_module(
                    config,
                    window_days=window_days,
                    since_days=None,
                    limit=concept_limit,
                    sources=sources,
                    top=top_n,
                    persist=args.concept_persist,
                    dry_run=args.concept_dry_run,
                )

                concepts = concept_result.get("concepts", [])
                if not concepts:
                    console.print(
                        "[yellow]未解析到有效的概念信息，请确认已补齐 OpenAlex 元数据。[/yellow]"
                    )
                else:
                    table = Table(
                        title=f"概念热度：{concept_result['window_start'].date()} ~ {concept_result['window_end'].date()}"
                    )
                    table.add_column("Rank", style="cyan", justify="right")
                    table.add_column("Concept", style="green")
                    table.add_column("Count", style="magenta", justify="right")
                    table.add_column("Avg Score", style="yellow", justify="right")
                    table.add_column("Level", style="blue", justify="right")

                    for idx, entry in enumerate(concepts, start=1):
                        level_display = (
                            entry["concept_level"] if entry["concept_level"] is not None else "-"
                        )
                        table.add_row(
                            str(idx),
                            entry["concept_name"],
                            str(entry["paper_count"]),
                            f"{entry['avg_score']:.3f}",
                            str(level_display),
                        )

                    console.print(table)

                if concept_result.get("persisted"):
                    console.print("[green]已写入 analytics_concepts 表。[/green]")
                else:
                    console.print(
                        f"[cyan]persist={args.concept_persist}, dry_run={args.concept_dry_run}[/cyan]"
                    )

            elif analysis_type == "topics":
                topic_result = analyze_topics_module(
                    config,
                    granularity=args.topics_granularity,
                    since_years=args.topics_since_years,
                    top=top_n,
                    sources=sources,
                )
                concepts = topic_result.get("concepts", [])
                if not concepts:
                    console.print("[yellow]未找到满足条件的主题趋势数据。[/yellow]")
                else:
                    table = Table(
                        title=f"主题趋势 Top {len(concepts)}（粒度：{topic_result['granularity']}）"
                    )
                    table.add_column("Concept", style="green")
                    table.add_column("Latest", style="cyan")
                    table.add_column("Prev", style="magenta")
                    table.add_column("Growth", style="yellow", justify="right")
                    for entry in concepts:
                        table.add_row(
                            entry["concept_name"],
                            f"{entry['latest_period']} ({entry['latest_count']})",
                            f"{entry['previous_period']} ({entry['previous_count']})",
                            f"{entry['growth_rate']:.2f}",
                        )
                    console.print(table)
                console.print(
                    f"[cyan]统计论文数: {topic_result['papers']}，起始: {topic_result['since']}[/cyan]"
                )

            elif analysis_type == "citation":
                citation_result = summarize_citation_module(
                    config,
                    since_days=args.citation_since_days,
                    max_nodes=args.citation_top,
                )

                table = Table(title="引用网络 PageRank Top")
                table.add_column("Rank", style="cyan", justify="right")
                table.add_column("Node", style="yellow")
                table.add_column("Score", style="green", justify="right")
                for idx, entry in enumerate(citation_result["pagerank"], start=1):
                    table.add_row(str(idx), entry["label"], f"{entry['score']:.4f}")
                console.print(table)

                indegree_table = Table(title="引用网络 In-degree Top")
                indegree_table.add_column("Rank", style="cyan", justify="right")
                indegree_table.add_column("Node", style="yellow")
                indegree_table.add_column("Weight", style="green", justify="right")
                for idx, entry in enumerate(citation_result["in_degree"], start=1):
                    indegree_table.add_row(str(idx), entry["label"], f"{entry['score']:.2f}")
                console.print(indegree_table)

                console.print(
                    f"[cyan]节点: {citation_result['nodes']}，边: {citation_result['edges']}，since={citation_result['since']}[/cyan]"
                )

            elif analysis_type == "collaboration":
                collab_result = analyze_collab_module(
                    config,
                    since_days=args.collab_since_days,
                    min_weight=args.collab_min_weight,
                    top=args.collab_top,
                )
                edges = collab_result.get("edges", [])
                if not edges:
                    console.print("[yellow]未找到符合条件的合作边。[/yellow]")
                else:
                    table = Table(title=f"机构合作网络 Top {len(edges)}")
                    table.add_column("Rank", style="cyan", justify="right")
                    table.add_column("Source", style="green")
                    table.add_column("Target", style="green")
                    table.add_column("Weight", style="yellow", justify="right")
                    for idx, entry in enumerate(edges, start=1):
                        table.add_row(
                            str(idx), entry["source"], entry["target"], str(entry["weight"])
                        )
                    console.print(table)
                console.print(
                    f"[cyan]统计论文数: {collab_result['papers']}，since={collab_result['since']}[/cyan]"
                )

        return 0

    except Exception as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        if verbose:
            import traceback

            console.print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
