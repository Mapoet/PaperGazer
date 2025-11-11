#!/usr/bin/env python3
"""
引用网络构建示例脚本
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from papergazer.analytics.citation import build_citation_graph  # type: ignore[import]  # noqa: E402
from papergazer.config import load_config  # noqa: E402
from papergazer.utils import setup_logging  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="根据 references_json 构建引用网络",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/build_citation_graph.py --since-days 30
  python scripts/build_citation_graph.py --resolve-local --dry-run
        """,
    )
    parser.add_argument("--config", type=str, help="配置文件路径")
    parser.add_argument("--since-days", type=int, help="仅处理最近 N 天的论文")
    parser.add_argument("--limit", type=int, help="限制处理的论文数量")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["arxiv", "crossref", "eupmc", "unpaywall"],
        help="按数据源过滤",
    )
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写入数据库")
    parser.add_argument("--force", action="store_true", help="先删除已有引用边再重建")
    parser.add_argument("--resolve-local", action="store_true", help="尝试根据 DOI 关联本地论文")
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

    stats = build_citation_graph(
        config,
        since_days=args.since_days,
        sources=args.sources,
        limit=args.limit,
        dry_run=args.dry_run,
        force=args.force,
        resolve_local=args.resolve_local,
    )

    table = Table(title="引用网络结果")
    table.add_column("指标", style="cyan")
    table.add_column("数值", style="green", justify="right")

    table.add_row("候选论文数", str(stats["papers"]))
    table.add_row("新增引用边", str(stats["edges"]))
    table.add_row("关联本地条数", str(stats["resolved"]))
    table.add_row("跳过论文", str(stats["skipped"]))
    table.add_row("dry_run", str(args.dry_run))

    console.print(table)


if __name__ == "__main__":
    main()

