#!/usr/bin/env python3
"""
开放获取 / FAIR 指标示例脚本
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from papergazer.analytics.oa import monitor_oa  # type: ignore[import]  # noqa: E402
from papergazer.config import load_config  # noqa: E402
from papergazer.utils import setup_logging  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="统计 OA 与 FAIR 指标",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/monitor_oa.py --window-days 30
  python scripts/monitor_oa.py --persist --sources crossref
        """,
    )
    parser.add_argument("--config", type=str, help="配置文件路径")
    parser.add_argument("--window-days", type=int, default=30, help="统计窗口大小（天）")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["arxiv", "crossref", "eupmc", "unpaywall"],
        help="按数据源过滤",
    )
    parser.add_argument("--persist", action="store_true", help="写入 analytics_oa 表")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不写入数据库")
    return parser.parse_args()


def resolve_config_path(raw: str | None) -> Path:
    if raw:
        path = Path(raw)
        if not path.is_absolute():
            path = project_root / path
        return path

    test_path = project_root / "configs" / "config.test.yaml"
    if test_path.exists():
        return test_path
    return project_root / "configs" / "config.yaml"


def main() -> None:
    args = parse_args()
    config_path = resolve_config_path(args.config)

    if not config_path.exists():
        console.print(f"[bold red]配置文件不存在: {config_path}[/bold red]")
        raise SystemExit(1)

    config = load_config(config_path)
    setup_logging(config.logging)

    result = monitor_oa(
        config,
        window_days=args.window_days,
        sources=args.sources,
        persist=args.persist,
        dry_run=args.dry_run,
    )

    table = Table(title=f"OA 指标：{result['window_start'].date()} ~ {result['window_end'].date()}")
    table.add_column("指标", style="cyan")
    table.add_column("数值", style="green", justify="right")

    table.add_row("论文总数", str(result["total_count"]))
    table.add_row("OA 总数", str(result["oa_count"]))
    table.add_row("Gold/Hybrid", str(result["gold_count"]))
    table.add_row("Green", str(result["green_count"]))
    table.add_row("Bronze", str(result["bronze_count"]))
    table.add_row("数据链接数", str(result["data_link_count"]))
    table.add_row("代码链接数", str(result["code_link_count"]))
    table.add_row("dry_run", str(args.dry_run))

    console.print(table)

    if result.get("license_counter"):
        license_table = Table(title="常见许可")
        license_table.add_column("License/URL", style="yellow")
        license_table.add_column("Count", style="green", justify="right")
        for name, cnt in result["license_counter"].most_common(10):
            license_table.add_row(name, str(cnt))
        console.print(license_table)

    if result.get("oa_status_counter"):
        status_table = Table(title="OA 状态分布")
        status_table.add_column("Status", style="magenta")
        status_table.add_column("Count", style="green", justify="right")
        for name, cnt in result["oa_status_counter"].most_common():
            status_table.add_row(name, str(cnt))
        console.print(status_table)

    if result.get("persisted"):
        console.print("[green]已写入 analytics_oa 表。[/green]")
    else:
        console.print(f"[cyan]persist={args.persist}, dry_run={args.dry_run}[/cyan]")


if __name__ == "__main__":
    main()

