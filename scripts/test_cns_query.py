#!/usr/bin/env python3
"""
测试脚本：查询近N天的CNS期刊论文信息
支持 Nature、Science、Cell
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from papergazer.config import load_config
from papergazer.core.ingest import ingest_crossref
from papergazer.store.db import init_db, get_session, PaperItem, RunRecord, update_checkpoint
from papergazer.utils import setup_logging
from rich.console import Console
from rich.table import Table
from sqlalchemy import or_

console = Console()

# CNS期刊ISSN映射
CNS_ISSN = {
    "nature": {
        "name": "Nature",
        "print": "0028-0836",
        "online": "1476-4687",
    },
    "science": {
        "name": "Science",
        "print": "0036-8075",
        "online": "1095-9203",
    },
    "cell": {
        "name": "Cell",
        "print": "0092-8674",
        "online": "1097-4172",
    },
}


async def test_cns_query(journal: str, days: int = 5):
    """
    查询近 N 天的指定CNS期刊论文

    Args:
        journal: 期刊名称（nature, science, cell）
        days: 查询天数（默认 5 天）
    """
    journal_lower = journal.lower()
    if journal_lower not in CNS_ISSN:
        console.print(f"[bold red]不支持的期刊: {journal}[/bold red]")
        console.print(f"[yellow]支持的期刊: {', '.join(CNS_ISSN.keys())}[/yellow]")
        return

    journal_info = CNS_ISSN[journal_lower]
    journal_name = journal_info["name"]
    print_issn = journal_info["print"]
    online_issn = journal_info["online"]

    console.print(f"[bold green]开始查询近 {days} 天的 {journal_name} 论文...[/bold green]")

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

        # 手动设置检查点（N 天前）
        session = get_session()
        checkpoint = datetime.now(timezone.utc) - timedelta(days=days)
        # 清除旧的检查点记录，设置新的
        session.query(RunRecord).filter_by(source="crossref").delete()
        session.commit()
        update_checkpoint(session, "crossref", checkpoint, 0)
        session.commit()
        session.close()

        console.print(f"[green]检查点已设置: {checkpoint.date()}[/green]")

        # 执行 Crossref 巡检
        console.print(f"[yellow]正在查询 Crossref API（{journal_name}）...[/yellow]")
        count = await ingest_crossref(config)

        console.print(f"[green]查询完成，找到 {count} 条记录[/green]")

        # 查询数据库中的指定期刊论文
        session = get_session()

        items = (
            session.query(PaperItem)
            .filter_by(source="crossref")
            .filter(
                or_(
                    PaperItem.issn_print == print_issn,
                    PaperItem.issn_online == online_issn,
                    # 考虑到 ISSN 字段可能互换，增加双向匹配
                    PaperItem.issn_print == online_issn,
                    PaperItem.issn_online == print_issn,
                )
            )
            .order_by(PaperItem.published_date.desc())
            .limit(20)
            .all()
        )
        session.close()

        # 显示结果
        if items:
            table = Table(title=f"{journal_name} 论文（近 {days} 天）")
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
            console.print(f"[yellow]未找到 {journal_name} 论文记录[/yellow]")
            console.print("[yellow]可能原因：[/yellow]")
            console.print(f"  1. 近 {days} 天内没有新的 {journal_name} 论文")
            console.print("  2. API 查询失败或超时")
            console.print("  3. 检查点设置问题")

    except Exception as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        import traceback

        console.print(traceback.format_exc())
        raise


async def test_all_cns(days: int = 5):
    """
    查询所有CNS期刊的近N天论文

    Args:
        days: 查询天数（默认 5 天）
    """
    console.print(f"[bold green]开始查询所有CNS期刊的近 {days} 天论文...[/bold green]")

    for journal in ["nature", "science", "cell"]:
        console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
        await test_cns_query(journal, days)
        console.print(f"[bold cyan]{'='*60}[/bold cyan]\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        journal = sys.argv[1].lower()
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 5

        if journal == "all":
            asyncio.run(test_all_cns(days))
        else:
            asyncio.run(test_cns_query(journal, days))
    else:
        console.print("[bold yellow]用法:[/bold yellow]")
        console.print("  python scripts/test_cns_query.py <journal> [days]")
        console.print("  python scripts/test_cns_query.py all [days]")
        console.print("\n[bold cyan]示例:[/bold cyan]")
        console.print("  python scripts/test_cns_query.py nature 5")
        console.print("  python scripts/test_cns_query.py science 5")
        console.print("  python scripts/test_cns_query.py cell 5")
        console.print("  python scripts/test_cns_query.py all 5")

