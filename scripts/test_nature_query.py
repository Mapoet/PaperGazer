#!/usr/bin/env python3
"""
测试脚本：查询近五天的 Nature 论文信息
"""

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from papergazer.config import load_config
from papergazer.core.ingest import ingest_crossref
from papergazer.store.db import init_db, get_session, PaperItem
from papergazer.utils import setup_logging
from rich.console import Console
from rich.table import Table

console = Console()


async def test_nature_query(days: int = 5):
    """
    查询近 N 天的 Nature 论文

    Args:
        days: 查询天数（默认 5 天）
    """
    console.print(f"[bold green]开始查询近 {days} 天的 Nature 论文...[/bold green]")

    # 加载配置
    config_path = project_root / "configs" / "config.test.yaml"
    if not config_path.exists():
        console.print(f"[bold red]配置文件不存在: {config_path}[/bold red]")
        console.print("[yellow]提示：请先创建 configs/config.test.yaml[/yellow]")
        return

    try:
        config = load_config(config_path)
        setup_logging(config.logging)

        # 初始化数据库
        init_db(config.store.db_path)
        console.print(f"[green]数据库已初始化: {config.store.db_path}[/green]")

        # 手动设置检查点（5 天前）
        from papergazer.store.db import update_checkpoint, get_session
        from datetime import datetime, timezone

        session = get_session()
        checkpoint = datetime.now(timezone.utc) - timedelta(days=days)
        # 清除旧的检查点记录，设置新的
        from papergazer.store.db import RunRecord
        session.query(RunRecord).filter_by(source="crossref").delete()
        session.commit()
        update_checkpoint(session, "crossref", checkpoint, 0)
        session.commit()
        session.close()

        console.print(f"[green]检查点已设置: {checkpoint.date()}[/green]")

        # 执行 Crossref 巡检（仅 Nature）
        console.print("[yellow]正在查询 Crossref API...[/yellow]")
        count = await ingest_crossref(config)

        console.print(f"[green]查询完成，找到 {count} 条记录[/green]")

        # 查询数据库中的 Nature 论文
        session = get_session()
        from sqlalchemy import or_

        items = (
            session.query(PaperItem)
            .filter_by(source="crossref")
            .filter(
                or_(
                    PaperItem.issn_print == "0028-0836",
                    PaperItem.issn_online == "1476-4687",
                    PaperItem.issn_print == "1476-4687",
                    PaperItem.issn_online == "0028-0836",
                )
            )
            .order_by(PaperItem.published_date.desc())
            .limit(20)
            .all()
        )
        session.close()

        # 显示结果
        if items:
            table = Table(title=f"Nature 论文（近 {days} 天）")
            table.add_column("标题", style="cyan", no_wrap=False, max_width=50)
            table.add_column("DOI", style="magenta")
            table.add_column("发布日期", style="green")
            table.add_column("作者", style="yellow", max_width=30)

            for item in items:
                title = item.title or "无标题"
                if len(title) > 50:
                    title = title[:47] + "..."
                doi = item.doi or "无 DOI"
                pub_date = str(item.published_date) if item.published_date else "未知"
                authors = "N/A"
                if item.authors_json:
                    import json

                    try:
                        authors_data = json.loads(item.authors_json)
                        if authors_data:
                            authors = authors_data[0].get("name", "N/A")
                            if len(authors) > 30:
                                authors = authors[:27] + "..."
                    except:
                        pass

                table.add_row(title, doi, pub_date, authors)

            console.print(table)
            console.print(f"[green]共显示 {len(items)} 条记录（最多 20 条）[/green]")
        else:
            console.print("[yellow]未找到 Nature 论文记录[/yellow]")
            console.print("[yellow]可能原因：[/yellow]")
            console.print("  1. 近 5 天内没有新的 Nature 论文")
            console.print("  2. API 查询失败或超时")
            console.print("  3. 检查点设置问题")

    except Exception as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        import traceback

        console.print(traceback.format_exc())
        raise


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    asyncio.run(test_nature_query(days))

