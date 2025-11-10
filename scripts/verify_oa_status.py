#!/usr/bin/env python3
"""
验证脚本：查看数据库中的OA状态信息
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from papergazer.store.db import init_db, get_session, PaperItem
from rich.console import Console
from rich.table import Table
from sqlalchemy import and_

console = Console()


def verify_oa_status(db_path: str = None):
    """
    验证数据库中的OA状态信息

    Args:
        db_path: 数据库路径，如果为None则使用默认路径
    """
    if db_path is None:
        db_path = "./data/test/test.db"

    console.print(f"[bold green]检查数据库: {db_path}[/bold green]")

    # 初始化数据库
    init_db(db_path)
    session = get_session()

    try:
        # 查询所有有DOI的记录
        items_with_doi = (
            session.query(PaperItem)
            .filter(PaperItem.doi.isnot(None))
            .filter(PaperItem.doi != "")
            .all()
        )

        console.print(f"[cyan]找到 {len(items_with_doi)} 条有DOI的记录[/cyan]")

        # 查询有OA信息的记录
        items_with_oa = (
            session.query(PaperItem)
            .filter(PaperItem.oa_source.isnot(None))
            .all()
        )

        console.print(f"[cyan]找到 {len(items_with_oa)} 条有OA信息的记录[/cyan]")

        if items_with_oa:
            table = Table(title="数据库中的OA状态信息")
            table.add_column("ID", style="cyan")
            table.add_column("标题", style="yellow", no_wrap=False, max_width=40)
            table.add_column("DOI", style="magenta", max_width=30)
            table.add_column("来源", style="blue")
            table.add_column("OA状态", style="green")
            table.add_column("OA来源", style="cyan")
            table.add_column("OA URL", style="yellow", max_width=40)

            for item in items_with_oa:
                title = item.title or "无标题"
                if len(title) > 40:
                    title = title[:37] + "..."
                doi = item.doi or "无"
                if len(doi) > 30:
                    doi = doi[:27] + "..."
                oa_status = "✅ 是" if item.is_oa else "❌ 否"
                oa_source = item.oa_source or "未知"
                oa_url = item.oa_pdf_url or "无"
                if len(oa_url) > 40:
                    oa_url = oa_url[:37] + "..."

                table.add_row(
                    str(item.id),
                    title,
                    doi,
                    item.source or "未知",
                    oa_status,
                    oa_source,
                    oa_url,
                )

            console.print(table)

        # 统计信息
        total = session.query(PaperItem).count()
        with_doi = session.query(PaperItem).filter(PaperItem.doi.isnot(None)).filter(PaperItem.doi != "").count()
        is_oa = session.query(PaperItem).filter(PaperItem.is_oa == True).count()
        unpaywall = session.query(PaperItem).filter(PaperItem.oa_source == "unpaywall").count()

        console.print(f"\n[bold cyan]统计信息：[/bold cyan]")
        console.print(f"  总记录数: {total}")
        console.print(f"  有DOI的记录: {with_doi}")
        console.print(f"  开放获取记录: {is_oa}")
        console.print(f"  Unpaywall来源: {unpaywall}")

        # 检查有DOI但没有OA信息的记录
        items_without_oa = (
            session.query(PaperItem)
            .filter(and_(
                PaperItem.doi.isnot(None),
                PaperItem.doi != "",
                PaperItem.oa_source.is_(None)
            ))
            .count()
        )

        if items_without_oa > 0:
            console.print(f"\n[yellow]提示：有 {items_without_oa} 条有DOI的记录尚未查询OA状态[/yellow]")
            console.print(f"[yellow]可以运行: python scripts/test_unpaywall_query.py 7[/yellow]")

    finally:
        session.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else None
    verify_oa_status(db_path)

