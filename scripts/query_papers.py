#!/usr/bin/env python3
"""
统一论文查询脚本
支持多数据源的论文查询功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from papergazer.config import load_config
from papergazer.utils import query_all_sources_by_days
from papergazer.utils import setup_logging
from rich.console import Console
from rich.table import Table

console = Console()


async def main():
    """主函数"""
    if len(sys.argv) < 2:
        console.print("[bold yellow]用法:[/bold yellow]")
        console.print("  python scripts/query_papers.py <days> [sources...]")
        console.print("\n[bold cyan]参数:[/bold cyan]")
        console.print("  days: 查询天数（必需）")
        console.print("  sources: 数据源列表，可选值：arxiv, crossref, eupmc, unpaywall")
        console.print("          如果不指定，则查询所有数据源")
        console.print("\n[bold cyan]示例:[/bold cyan]")
        console.print("  python scripts/query_papers.py 7")
        console.print("  python scripts/query_papers.py 7 arxiv crossref")
        console.print("  python scripts/query_papers.py 30 eupmc")
        return

    days = int(sys.argv[1])
    sources = sys.argv[2:] if len(sys.argv) > 2 else None

    console.print(f"[bold green]开始查询最近 {days} 天的论文...[/bold green]")

    # 加载配置
    config_path = project_root / "configs" / "config.test.yaml"
    if not config_path.exists():
        console.print(f"[bold red]配置文件不存在: {config_path}[/bold red]")
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
        raise


if __name__ == "__main__":
    asyncio.run(main())

