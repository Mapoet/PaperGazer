#!/usr/bin/env python3
"""
概念热度分析示例脚本
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from papergazer.analytics.concepts import analyze_concepts  # type: ignore[import]  # noqa: E402
from papergazer.config import load_config  # noqa: E402
from papergazer.utils import setup_logging  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="基于 OpenAlex 概念的热度统计",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/analyze_concepts.py --window-days 30 --top 10
  python scripts/analyze_concepts.py --persist --dry-run
        """,
    )
    parser.add_argument("--config", type=str, help="配置文件路径")
    parser.add_argument("--window-days", type=int, default=30, help="统计窗口大小（天）")
    parser.add_argument("--since-days", type=int, help="仅统计最近 N 天的论文（覆盖窗口）")
    parser.add_argument("--limit", type=int, help="限制论文数量")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["arxiv", "crossref", "eupmc", "unpaywall"],
        help="按数据源过滤",
    )
    parser.add_argument("--top", type=int, default=20, help="输出前 N 个概念")
    parser.add_argument("--persist", action="store_true", help="写入 analytics_concepts 表")
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

    result = analyze_concepts(
        config,
        window_days=args.window_days,
        since_days=args.since_days,
        limit=args.limit,
        sources=args.sources,
        top=args.top,
        persist=args.persist,
        dry_run=args.dry_run,
    )

    concepts = result.get("concepts", [])
    if not concepts:
        console.print("[yellow]未解析到有效的概念信息，请确认已补齐 OpenAlex 元数据。[/yellow]")
        return

    table = Table(title=f"概念热度：{result['window_start'].date()} ~ {result['window_end'].date()}")
    table.add_column("Rank", style="cyan", justify="right")
    table.add_column("Concept", style="green")
    table.add_column("Count", style="magenta", justify="right")
    table.add_column("Avg Score", style="yellow", justify="right")
    table.add_column("Level", style="blue", justify="right")

    for idx, entry in enumerate(concepts, start=1):
        level = entry["concept_level"] if entry["concept_level"] is not None else "-"
        table.add_row(
            str(idx),
            entry["concept_name"],
            str(entry["paper_count"]),
            f"{entry['avg_score']:.3f}",
            str(level),
        )

    console.print(table)
    if result.get("persisted"):
        console.print("[green]已写入 analytics_concepts 表。[/green]")
    else:
        console.print(f"[cyan]persist={args.persist}, dry_run={args.dry_run}[/cyan]")


if __name__ == "__main__":
    main()

