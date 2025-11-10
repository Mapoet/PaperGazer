#!/usr/bin/env python3
"""
测试脚本：查询最近N天论文的Unpaywall开放获取状态
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from papergazer.config import load_config
from papergazer.sources.unpaywall import best_oa
from papergazer.sources.crossref import fetch_crossref_by_doi
from papergazer.store.db import init_db, get_session, PaperItem
from papergazer.utils import setup_logging
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

logger = logging.getLogger(__name__)
console = Console()


async def test_unpaywall_query(days: int = 7, limit: int = 20):
    """
    查询最近 N 天论文的 Unpaywall 开放获取状态

    Args:
        days: 查询天数（默认 7 天）
        limit: 限制查询的论文数量（默认 20）
    """
    console.print(f"[bold green]开始查询最近 {days} 天论文的 Unpaywall 开放获取状态...[/bold green]")

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

        # 查询最近N天的论文（有DOI的）
        session = get_session()
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        items = (
            session.query(PaperItem)
            .filter(PaperItem.doi.isnot(None))
            .filter(PaperItem.doi != "")
            .filter(PaperItem.updated_date >= cutoff_date)
            .order_by(PaperItem.updated_date.desc())
            .limit(limit)
            .all()
        )
        session.close()

        if not items:
            console.print("[yellow]未找到符合条件的论文（有DOI且最近更新）[/yellow]")
            console.print("[yellow]提示：请先运行 arXiv 或 Crossref 巡检以获取论文数据[/yellow]")
            return

        console.print(f"[cyan]找到 {len(items)} 篇论文，开始查询 Unpaywall API...[/cyan]")

        # 查询 Unpaywall API
        results = []
        oa_count = 0
        non_oa_count = 0
        error_count = 0
        abstract_fetched_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]查询 Unpaywall API...", total=len(items))

            # 打开数据库会话用于更新
            update_session = get_session()
            
            for item in items:
                try:
                    oa_info = await best_oa(item.doi, config.mailto)
                    results.append({
                        "item": item,
                        "oa_info": oa_info,
                        "error": None,
                    })
                    
                    # 更新数据库中的OA信息
                    db_item = update_session.query(PaperItem).filter_by(id=item.id).first()
                    if db_item:
                        db_item.is_oa = oa_info.is_oa
                        if oa_info.is_oa and oa_info.best_oa_location:
                            db_item.oa_source = "unpaywall"
                            # 保存PDF URL（优先）或landing page URL
                            db_item.oa_pdf_url = (
                                oa_info.best_oa_location.get("url_for_pdf")
                                or oa_info.best_oa_location.get("url_for_landing_page")
                                or oa_info.best_oa_location.get("url")
                            )
                        else:
                            # 如果不是OA，清除OA相关字段
                            db_item.oa_source = None
                            db_item.oa_pdf_url = None
                        
                        # 如果数据库中没有摘要，尝试从Crossref获取（特别是非OA论文）
                        if not db_item.abstract_jats or db_item.abstract_jats.strip() == "":
                            try:
                                work = await fetch_crossref_by_doi(item.doi, config.mailto)
                                if work and work.abstract:
                                    db_item.abstract_jats = work.abstract
                                    abstract_fetched_count += 1
                                    logger.info(f"已从Crossref获取摘要: {item.doi}")
                            except Exception as e:
                                logger.debug(f"无法从Crossref获取摘要 {item.doi}: {e}")
                        
                        update_session.commit()
                    
                    if oa_info.is_oa:
                        oa_count += 1
                    else:
                        non_oa_count += 1
                except Exception as e:
                    error_msg = str(e)
                    # 简化错误信息显示
                    if "422" in error_msg or "email" in error_msg.lower():
                        error_msg = "邮箱验证失败（请使用真实邮箱）"
                    results.append({
                        "item": item,
                        "oa_info": None,
                        "error": error_msg,
                    })
                    error_count += 1

                progress.update(task, advance=1)
                # 添加小延迟，避免请求过快
                await asyncio.sleep(0.5)
            
            update_session.close()

        # 显示结果
        table = Table(title=f"Unpaywall 开放获取状态查询结果（最近 {days} 天）")
        table.add_column("标题", style="cyan", no_wrap=False, max_width=40)
        table.add_column("DOI", style="magenta", max_width=30)
        table.add_column("来源", style="blue")
        table.add_column("OA状态", style="green")
        table.add_column("OA位置", style="yellow", max_width=30)
        table.add_column("错误", style="red", max_width=20)

        for result in results:
            item = result["item"]
            oa_info = result["oa_info"]
            error = result["error"]

            title = item.title or "无标题"
            if len(title) > 40:
                title = title[:37] + "..."
            doi = item.doi or "无 DOI"
            if len(doi) > 30:
                doi = doi[:27] + "..."
            source = item.source or "未知"

            if error:
                oa_status = "错误"
                oa_location = error[:27] + "..." if len(error) > 30 else error
            elif oa_info:
                oa_status = "✅ 是" if oa_info.is_oa else "❌ 否"
                if oa_info.is_oa and oa_info.best_oa_location:
                    location = oa_info.best_oa_location.get("url_for_pdf") or oa_info.best_oa_location.get("url_for_landing_page", "未知")
                    if len(location) > 30:
                        location = location[:27] + "..."
                    oa_location = location
                else:
                    oa_location = "无"
            else:
                oa_status = "未知"
                oa_location = "无"

            table.add_row(title, doi, source, oa_status, oa_location, error or "")

        console.print(table)

        # 显示统计信息
        console.print(f"\n[bold cyan]统计信息：[/bold cyan]")
        console.print(f"  总查询数: {len(items)}")
        console.print(f"  ✅ 开放获取: {oa_count}")
        console.print(f"  ❌ 非开放获取: {non_oa_count}")
        console.print(f"  ⚠️  查询错误: {error_count}")
        console.print(f"  💾 已保存到数据库: {oa_count + non_oa_count} 条记录")
        if abstract_fetched_count > 0:
            console.print(f"  📄 从Crossref获取摘要: {abstract_fetched_count} 条")
        
        if error_count > 0 and "邮箱验证失败" in str([r["error"] for r in results if r["error"]]):
            console.print(f"\n[yellow]提示：Unpaywall API 要求使用真实邮箱地址。[/yellow]")
            console.print(f"[yellow]请修改 configs/config.test.yaml 中的 mailto 为您的真实邮箱。[/yellow]")
        
        # 验证数据库中的保存结果
        verify_session = get_session()
        saved_oa_count = verify_session.query(PaperItem).filter_by(is_oa=True, oa_source="unpaywall").count()
        verify_session.close()
        console.print(f"\n[green]数据库验证：已保存 {saved_oa_count} 条Unpaywall OA记录[/green]")

    except Exception as e:
        console.print(f"[bold red]错误: {e}[/bold red]")
        import traceback

        console.print(traceback.format_exc())
        raise


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    asyncio.run(test_unpaywall_query(days, limit))

