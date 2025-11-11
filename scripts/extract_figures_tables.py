#!/usr/bin/env python3
"""
图表抽取示例脚本
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from papergazer.config import load_config  # noqa: E402
from papergazer.core.figures import extract_figures_and_tables  # noqa: E402
from papergazer.utils import setup_logging  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="从 TEI 文件抽取图表信息（调用核心模块）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/extract_figures_tables.py --since-days 7
  python scripts/extract_figures_tables.py --sources crossref --dry-run
  python scripts/extract_figures_tables.py --force --include-existing
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
    parser.add_argument("--force", action="store_true", help="强制重新抽取图表")
    parser.add_argument(
        "--only-missing",
        dest="only_missing",
        action="store_true",
        help="仅处理缺少图表数据的论文（默认）",
    )
    parser.add_argument(
        "--include-existing",
        dest="only_missing",
        action="store_false",
        help="包含已存在图表数据的论文",
    )
    parser.set_defaults(only_missing=True)
    parser.add_argument(
        "--max-per-paper",
        type=int,
        help="覆盖配置中的单篇图表数量上限",
    )
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

    stats = extract_figures_and_tables(
        config,
        since_days=args.since_days,
        limit=args.limit,
        sources=args.sources,
        dry_run=args.dry_run,
        force=args.force,
        only_missing=args.only_missing,
        max_per_paper=args.max_per_paper,
    )

    table = Table(title="图表抽取结果")
    table.add_column("指标", style="cyan")
    table.add_column("数值", style="green", justify="right")

    table.add_row("候选论文数", str(stats["papers"]))
    table.add_row("已处理论文", str(stats["processed"]))
    table.add_row("跳过论文", str(stats["skipped"]))
    table.add_row("图数量", str(stats["figures"]))
    table.add_row("表数量", str(stats["tables"]))
    table.add_row("dry_run", str(stats["dry_run"]))

    console.print(table)


if __name__ == "__main__":
    main()


