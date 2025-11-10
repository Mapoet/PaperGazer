#!/usr/bin/env python3
"""
论文摘要导出脚本
查询指定时间段的论文，支持作者和关键词过滤，导出为 Markdown 格式
"""

import argparse
import asyncio
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from papergazer.config import load_config
from papergazer.store.db import PaperItem, get_session, init_db
from papergazer.utils import setup_logging
from rich.console import Console
from rich.progress import Progress

console = Console()


def query_papers_with_filters(
    since: date,
    until: date,
    author: str | None = None,
    keyword: str | None = None,
    sources: list[str] | None = None,
    venues: list[str] | None = None,
    db_path: str | Path | None = None,
) -> list[dict]:
    """
    查询论文（带过滤条件）

    Args:
        since: 起始日期
        until: 结束日期
        author: 作者名称（可选）
        keyword: 关键词（可选）
        sources: 数据源列表（可选）
        venues: 期刊名称列表（可选）
        db_path: 数据库路径（可选）

    Returns:
        论文列表
    """
    if db_path:
        init_db(db_path)

    session = get_session()
    try:
        # 基础查询：按日期范围
        query = session.query(PaperItem).filter(
            PaperItem.published_date >= since,
            PaperItem.published_date <= until,
        )

        # 作者过滤
        if author:
            query = query.filter(PaperItem.authors_json.ilike(f"%{author}%"))

        # 关键词过滤（标题或摘要）
        if keyword:
            from sqlalchemy import or_

            query = query.filter(
                or_(
                    PaperItem.title.ilike(f"%{keyword}%"),
                    PaperItem.abstract_jats.ilike(f"%{keyword}%"),
                )
            )

        # 数据源过滤
        if sources:
            query = query.filter(PaperItem.source.in_(sources))

        # 期刊名称过滤
        if venues:
            from sqlalchemy import or_

            venue_filters = [PaperItem.venue.ilike(f"%{v}%") for v in venues]
            query = query.filter(or_(*venue_filters))

        # 排序：按发布日期降序
        query = query.order_by(PaperItem.published_date.desc())

        items = query.all()
        papers = []

        for item in items:
            authors = []
            if item.authors_json:
                try:
                    authors_data = json.loads(item.authors_json)
                    authors = [a.get("name", "") for a in authors_data]
                except (json.JSONDecodeError, TypeError):
                    pass

            papers.append(
                {
                    "id": item.id,
                    "source": item.source,
                    "title": item.title,
                    "doi": item.doi,
                    "identifier": item.identifier,
                    "authors": authors,
                    "venue": item.venue,
                    "published_date": item.published_date,
                    "updated_date": item.updated_date,
                    "abstract": item.abstract_jats,
                    "is_oa": item.is_oa,
                    "oa_source": item.oa_source,
                    "pdf_path": item.pdf_path,
                    "url_landing": item.url_landing,
                }
            )

        return papers
    finally:
        session.close()


def format_paper_markdown(paper: dict, index: int) -> str:
    """
    将论文格式化为 Markdown

    Args:
        paper: 论文信息
        index: 序号

    Returns:
        Markdown 格式的字符串
    """
    md = []

    # 标题和序号
    md.append(f"## {index}. {paper['title']}")
    md.append("")

    # 基本信息
    if paper["authors"]:
        authors_str = ", ".join(paper["authors"][:10])  # 最多显示10个作者
        if len(paper["authors"]) > 10:
            authors_str += f" *et al.* ({len(paper['authors'])} authors)"
        md.append(f"**作者**: {authors_str}")
        md.append("")

    if paper["venue"]:
        md.append(f"**期刊**: {paper['venue']}")
        md.append("")

    if paper["published_date"]:
        md.append(f"**发表日期**: {paper['published_date'].strftime('%Y-%m-%d')}")
        md.append("")

    # DOI 和链接
    if paper["doi"]:
        md.append(f"**DOI**: [{paper['doi']}](https://doi.org/{paper['doi']})")
        md.append("")
    elif paper["source"] == "arxiv" and paper["identifier"]:
        arxiv_url = f"https://arxiv.org/abs/{paper['identifier']}"
        md.append(f"**arXiv**: [{paper['identifier']}]({arxiv_url})")
        md.append("")

    # OA 状态
    if paper["is_oa"]:
        oa_info = f"✅ Open Access"
        if paper["oa_source"]:
            oa_info += f" (来源: {paper['oa_source']})"
        if paper["pdf_path"]:
            oa_info += f" - 已下载"
        md.append(f"**状态**: {oa_info}")
        md.append("")

    # 摘要
    if paper["abstract"]:
        md.append("**摘要**:")
        md.append("")
        # 清理摘要文本（移除多余的空白）
        abstract = paper["abstract"].strip()
        # 处理 JATS XML 标签（简单处理）
        abstract = abstract.replace("<jats:p>", "").replace("</jats:p>", "")
        abstract = abstract.replace("<p>", "").replace("</p>", "")
        md.append(abstract)
        md.append("")
    else:
        md.append("*摘要暂不可用*")
        md.append("")

    # 分隔线
    md.append("---")
    md.append("")

    return "\n".join(md)


def export_to_markdown(
    papers: list[dict],
    output_file: Path,
    since: date,
    until: date,
    author: str | None = None,
    keyword: str | None = None,
) -> None:
    """
    导出论文到 Markdown 文件

    Args:
        papers: 论文列表
        output_file: 输出文件路径
        since: 起始日期
        until: 结束日期
        author: 作者过滤条件
        keyword: 关键词过滤条件
    """
    md_content = []

    # 标题和统计信息
    md_content.append(f"# 论文摘要汇总")
    md_content.append("")
    md_content.append(f"**时间范围**: {since.strftime('%Y-%m-%d')} 至 {until.strftime('%Y-%m-%d')}")
    md_content.append("")

    # 过滤条件
    filters = []
    if author:
        filters.append(f"作者: {author}")
    if keyword:
        filters.append(f"关键词: {keyword}")

    if filters:
        md_content.append(f"**过滤条件**: {', '.join(filters)}")
        md_content.append("")

    # 统计信息
    md_content.append(f"**论文总数**: {len(papers)}")
    md_content.append("")

    # 按期刊分类统计
    venue_counts = {}
    oa_count = 0
    for paper in papers:
        venue = paper["venue"] or "未知"
        venue_counts[venue] = venue_counts.get(venue, 0) + 1
        if paper["is_oa"]:
            oa_count += 1

    md_content.append(f"**开放获取论文**: {oa_count}/{len(papers)} ({oa_count*100//len(papers) if papers else 0}%)")
    md_content.append("")

    # 期刊分布（前10个）
    if venue_counts:
        md_content.append("**期刊分布**（前10个）:")
        md_content.append("")
        sorted_venues = sorted(venue_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        for venue, count in sorted_venues:
            md_content.append(f"- {venue}: {count} 篇")
        md_content.append("")

    # 目录
    md_content.append("## 目录")
    md_content.append("")
    for idx, paper in enumerate(papers, 1):
        title = paper["title"]
        # 转换标题为 Markdown 锚点
        anchor = title.lower().replace(" ", "-").replace(".", "").replace(",", "")[:50]
        md_content.append(f"{idx}. [{title}](#{idx}-{anchor})")
    md_content.append("")
    md_content.append("---")
    md_content.append("")

    # 论文详情
    for idx, paper in enumerate(papers, 1):
        md_content.append(format_paper_markdown(paper, idx))

    # 写入文件
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md_content))


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="查询并导出论文摘要为 Markdown 格式",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 查询最近30天的所有论文
  python scripts/export_abstracts.py --days 30 --output abstracts.md

  # 查询指定日期范围的论文
  python scripts/export_abstracts.py --since 2025-01-01 --until 2025-01-31 --output jan2025.md

  # 按作者过滤
  python scripts/export_abstracts.py --days 30 --author "Zhang" --output zhang_papers.md

  # 按关键词过滤
  python scripts/export_abstracts.py --days 30 --keyword "machine learning" --output ml_papers.md

  # 组合过滤
  python scripts/export_abstracts.py --since 2025-01-01 --until 2025-01-31 \\
      --author "Zhang" --keyword "deep learning" --output results.md

  # 指定期刊
  python scripts/export_abstracts.py --days 30 --venues "Nature" "Science" --output cns_papers.md

  # 使用自定义配置文件
  python scripts/export_abstracts.py --days 30 --config configs/my_config.yaml --output papers.md
        """,
    )

    parser.add_argument(
        "--since",
        type=str,
        help="起始日期（格式: YYYY-MM-DD）",
    )
    parser.add_argument(
        "--until",
        type=str,
        help="结束日期（格式: YYYY-MM-DD）",
    )
    parser.add_argument(
        "--days",
        type=int,
        help="查询最近 N 天的论文（等同于 --since 为 N 天前）",
    )
    parser.add_argument(
        "--author",
        type=str,
        help="按作者名称过滤",
    )
    parser.add_argument(
        "--keyword",
        type=str,
        help="按关键词过滤（搜索标题和摘要）",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["arxiv", "crossref", "eupmc"],
        help="指定数据源",
    )
    parser.add_argument(
        "--venues",
        nargs="+",
        help="按期刊名称过滤（支持部分匹配）",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        required=True,
        help="输出文件路径（.md）",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="配置文件路径（默认: configs/config.test.yaml 或 configs/config.yaml）",
    )

    args = parser.parse_args()

    # 检查参数冲突
    if args.days is not None and args.since is not None:
        console.print(
            "[bold yellow]警告: 同时指定了 --days 和 --since，将使用 --days 参数[/bold yellow]"
        )

    # 解析日期范围
    if args.days is not None:
        until_date = date.today()
        since_date = until_date - timedelta(days=args.days)
        console.print(
            f"[cyan]查询时间范围: {since_date} 至 {until_date} (最近 {args.days} 天)[/cyan]"
        )
    elif args.since is not None:
        try:
            since_date = date.fromisoformat(args.since)
            if args.until:
                until_date = date.fromisoformat(args.until)
            else:
                until_date = date.today()
            console.print(f"[cyan]查询时间范围: {since_date} 至 {until_date}[/cyan]")
        except ValueError as e:
            console.print(f"[bold red]错误: 无法解析日期: {e}[/bold red]")
            console.print("日期格式应为: YYYY-MM-DD")
            return
    else:
        console.print("[bold red]错误: 必须指定 --days 或 --since 参数[/bold red]")
        return

    # 加载配置
    if args.config:
        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = project_root / config_path
    else:
        config_path = project_root / "configs" / "config.test.yaml"
        if not config_path.exists():
            config_path = project_root / "configs" / "config.yaml"

    if not config_path.exists():
        console.print(f"[bold red]配置文件不存在: {config_path}[/bold red]")
        console.print(
            "[yellow]提示: 请复制 configs/config.yaml.example 为 configs/config.yaml 并修改相应配置[/yellow]"
        )
        return

    try:
        config = load_config(config_path)
        setup_logging(config.logging)

        # 初始化数据库
        init_db(config.store.db_path)
        console.print(f"[green]数据库已初始化: {config.store.db_path}[/green]")

        # 显示过滤条件
        if args.author:
            console.print(f"[cyan]作者过滤: {args.author}[/cyan]")
        if args.keyword:
            console.print(f"[cyan]关键词过滤: {args.keyword}[/cyan]")
        if args.sources:
            console.print(f"[cyan]数据源: {', '.join(args.sources)}[/cyan]")
        if args.venues:
            console.print(f"[cyan]期刊: {', '.join(args.venues)}[/cyan]")

        # 查询论文
        console.print("\n[bold green]正在查询论文...[/bold green]")
        papers = query_papers_with_filters(
            since=since_date,
            until=until_date,
            author=args.author,
            keyword=args.keyword,
            sources=args.sources,
            venues=args.venues,
            db_path=config.store.db_path,
        )

        console.print(f"[green]找到 {len(papers)} 篇论文[/green]")

        if not papers:
            console.print("[yellow]未找到符合条件的论文[/yellow]")
            return

        # 导出到 Markdown
        output_file = Path(args.output)
        console.print(f"\n[bold green]正在导出到 {output_file}...[/bold green]")

        export_to_markdown(
            papers=papers,
            output_file=output_file,
            since=since_date,
            until=until_date,
            author=args.author,
            keyword=args.keyword,
        )

        console.print(f"[bold green]✅ 导出完成！[/bold green]")
        console.print(f"[cyan]文件: {output_file.absolute()}[/cyan]")

        # 统计信息
        oa_count = sum(1 for p in papers if p["is_oa"])
        console.print(f"\n[bold cyan]统计信息:[/bold cyan]")
        console.print(f"  总论文数: {len(papers)}")
        console.print(
            f"  开放获取: {oa_count} ({oa_count*100//len(papers) if papers else 0}%)"
        )

    except Exception as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        import traceback

        console.print(traceback.format_exc())
        raise


if __name__ == "__main__":
    from datetime import timedelta

    main()

