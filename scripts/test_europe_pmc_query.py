#!/usr/bin/env python3
"""
测试脚本：查询最近 N 天的 Europe PMC 文章
"""

import asyncio
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from papergazer.config import load_config
from papergazer.models import Author, PaperMetadata
from papergazer.sources.europe_pmc import search_articles_by_date
from papergazer.store.db import init_db, get_session, upsert_paper, PaperItem
from papergazer.utils import setup_logging
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

logger = logging.getLogger(__name__)
console = Console()


async def test_europe_pmc_query(days: int = 7, limit: int = 20):
    """
    查询最近 N 天的 Europe PMC 文章

    Args:
        days: 查询天数（默认 7 天）
        limit: 显示结果数量限制（默认 20）
    """
    console.print(f"[bold green]开始查询最近 {days} 天的 Europe PMC 文章...[/bold green]")

    config_path = project_root / "configs" / "config.test.yaml"
    if not config_path.exists():
        console.print(f"[bold red]配置文件不存在: {config_path}[/bold red]")
        console.print("[yellow]提示：请先创建 configs/config.test.yaml[/yellow]")
        return

    try:
        config = load_config(config_path)
        setup_logging(config.logging)

        # 计算日期范围
        to_date = datetime.now(timezone.utc).date()
        from_date = to_date - timedelta(days=days)

        console.print(f"[cyan]查询日期范围: {from_date} 至 {to_date}[/cyan]")
        console.print(f"[cyan]最大结果数: {limit}[/cyan]")

        # 初始化数据库
        init_db(config.store.db_path)
        console.print(f"[green]数据库已初始化: {config.store.db_path}[/green]")

        # 查询 Europe PMC API 并保存到数据库
        results = []
        total_count = 0
        saved_count = 0
        session = get_session()

        def europe_pmc_to_metadata(article: dict) -> PaperMetadata:
            """将 Europe PMC 文章数据转换为 PaperMetadata"""
            # 提取标题
            title = article.get("title", "") or ""

            # 提取作者
            authors = []
            if "authorList" in article and article["authorList"].get("author"):
                author_list = article["authorList"]["author"]
                if isinstance(author_list, list):
                    for author in author_list:
                        if isinstance(author, dict):
                            given = author.get("firstName", "")
                            last = author.get("lastName", "")
                            name = f"{given} {last}".strip()
                            if name:
                                affiliation = None
                                if "affiliation" in author:
                                    aff_data = author["affiliation"]
                                    if isinstance(aff_data, list) and len(aff_data) > 0:
                                        affiliation = aff_data[0] if isinstance(aff_data[0], str) else aff_data[0].get("name", "")
                                    elif isinstance(aff_data, str):
                                        affiliation = aff_data
                                authors.append(Author(name=name, affiliation=affiliation))
            elif "authorString" in article:
                # 如果没有详细作者列表，使用 authorString
                author_string = article["authorString"]
                if author_string:
                    # 简单解析：按逗号分割
                    for name in author_string.split(","):
                        name = name.strip()
                        if name:
                            authors.append(Author(name=name))

            # 提取DOI
            doi = article.get("doi", "").strip() if article.get("doi") else None

            # 提取PMCID作为identifier（如果没有DOI）
            pmcid = article.get("pmcid", "")
            if pmcid and not pmcid.startswith("PMC"):
                pmcid = f"PMC{pmcid}"
            identifier = doi.lower().strip() if doi else pmcid

            # 提取发布日期
            published_date = None
            if "firstPublicationDate" in article:
                try:
                    date_str = article["firstPublicationDate"]
                    # 格式可能是 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS
                    published_date = datetime.strptime(date_str.split()[0], "%Y-%m-%d").date()
                except (ValueError, AttributeError):
                    pass
            elif "pubYear" in article:
                try:
                    year = int(article["pubYear"])
                    published_date = date(year, 1, 1)
                except (ValueError, TypeError):
                    pass

            # 提取期刊名称
            venue = None
            if "journalTitle" in article:
                venue = article["journalTitle"]
            elif "source" in article:
                venue = article["source"]

            # 提取摘要
            abstract = None
            # Europe PMC API 可能返回的摘要字段
            if "abstractText" in article and article["abstractText"]:
                abstract = article["abstractText"]
            elif "abstract" in article and article["abstract"]:
                abstract = article["abstract"]
            # 有些情况下摘要可能在嵌套结构中
            elif "abstractText" in article and isinstance(article["abstractText"], dict):
                abstract = article["abstractText"].get("text") or article["abstractText"].get("value")

            # 提取URL
            url_landing = None
            if "pmcid" in article:
                pmcid_for_url = article["pmcid"]
                if not pmcid_for_url.startswith("PMC"):
                    pmcid_for_url = f"PMC{pmcid_for_url}"
                url_landing = f"https://europepmc.org/article/MED/{pmcid_for_url}"

            return PaperMetadata(
                source="eupmc",
                identifier=identifier,
                title=title,
                authors=authors,
                venue=venue,
                published_date=published_date,
                updated_date=datetime.now(timezone.utc) if published_date else None,
                doi=doi,
                url_landing=url_landing,
                abstract=abstract,
            )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]查询 Europe PMC API 并保存到数据库...", total=None)

            async for article in search_articles_by_date(
                from_date=from_date,
                to_date=to_date,
                page_size=25,
                max_results=limit,
            ):
                total_count += 1
                results.append(article)
                
                # 转换为 PaperMetadata 并保存到数据库
                try:
                    metadata = europe_pmc_to_metadata(article)
                    item = upsert_paper(session, metadata)
                    # 设置OA相关字段
                    item.is_oa = True
                    item.oa_source = "eupmc"
                    # 如果有PMCID，可以保存到某个字段（目前identifier已包含）
                    session.commit()
                    saved_count += 1
                except Exception as e:
                    logger.warning(f"保存文章失败: {e}")
                    session.rollback()
                
                progress.update(task, description=f"[cyan]已获取 {total_count} 条，已保存 {saved_count} 条...")

                if total_count >= limit:
                    break

        session.close()

        # 显示结果
        if results:
            table = Table(title=f"Europe PMC 文章（最近 {days} 天）")
            table.add_column("标题", style="cyan", no_wrap=False, max_width=40)
            table.add_column("DOI", style="magenta", max_width=30)
            table.add_column("PMCID", style="green")
            table.add_column("发布日期", style="yellow")
            table.add_column("期刊", style="blue", max_width=20)
            table.add_column("作者", style="yellow", max_width=20)

            for article in results[:limit]:
                title = article.get("title", "无标题") or "无标题"
                if len(title) > 40:
                    title = title[:37] + "..."

                doi = article.get("doi", "无 DOI") or "无 DOI"
                if len(doi) > 30:
                    doi = doi[:27] + "..."

                pmcid = article.get("pmcid", "无") or "无"
                if pmcid and not pmcid.startswith("PMC"):
                    pmcid = f"PMC{pmcid}"

                # 处理发布日期
                pub_date = "未知"
                if "firstPublicationDate" in article:
                    pub_date = article["firstPublicationDate"]
                elif "pubYear" in article:
                    pub_date = str(article["pubYear"])

                # 处理期刊名称
                journal = "未知"
                if "journalTitle" in article:
                    journal = article["journalTitle"]
                elif "source" in article:
                    journal = article["source"]
                if len(journal) > 20:
                    journal = journal[:17] + "..."

                # 处理作者
                authors = "未知"
                if "authorString" in article:
                    authors = article["authorString"]
                    if len(authors) > 20:
                        authors = authors[:17] + "..."
                elif "authorList" in article and article["authorList"].get("author"):
                    author_list = article["authorList"]["author"]
                    if isinstance(author_list, list) and len(author_list) > 0:
                        first_author = author_list[0]
                        if isinstance(first_author, dict):
                            given = first_author.get("firstName", "")
                            last = first_author.get("lastName", "")
                            authors = f"{given} {last}".strip()
                        else:
                            authors = str(first_author)
                    if len(authors) > 20:
                        authors = authors[:17] + "..."

                table.add_row(title, doi, pmcid, pub_date, journal, authors)

            console.print(table)
            console.print(f"[green]共显示 {len(results)} 条记录（最多 {limit} 条）[/green]")
        else:
            console.print("[yellow]未找到 Europe PMC 文章[/yellow]")
            console.print("[yellow]可能原因：[/yellow]")
            console.print("  1. 最近 7 天内没有新的 Europe PMC 文章")
            console.print("  2. API 查询失败或超时")
            console.print("  3. 查询条件过于严格")

        # 显示统计信息
        console.print(f"\n[bold cyan]统计信息：[/bold cyan]")
        console.print(f"  查询日期范围: {from_date} 至 {to_date}")
        console.print(f"  获取记录数: {total_count}")
        console.print(f"  💾 已保存到数据库: {saved_count} 条记录")

        # 统计有DOI的记录
        with_doi = sum(1 for r in results if r.get("doi"))
        console.print(f"  有DOI的记录: {with_doi}")

        # 统计有PMCID的记录
        with_pmcid = sum(1 for r in results if r.get("pmcid"))
        console.print(f"  有PMCID的记录: {with_pmcid}")

        # 验证数据库中的保存结果
        verify_session = get_session()
        saved_eupmc_count = verify_session.query(PaperItem).filter_by(source="eupmc").count()
        verify_session.close()
        console.print(f"\n[green]数据库验证：已保存 {saved_eupmc_count} 条Europe PMC记录[/green]")

    except Exception as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        import traceback

        console.print(traceback.format_exc())
        raise


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    asyncio.run(test_europe_pmc_query(days, limit))

