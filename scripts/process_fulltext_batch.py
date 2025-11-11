#!/usr/bin/env python3
"""
批量生成 TEI 示例脚本
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from papergazer.config import load_config  # noqa: E402
from papergazer.core.fulltext import generate_tei_for_papers  # type: ignore[import]  # noqa: E402
from papergazer.utils import setup_logging  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="批量生成 TEI（基于 GROBID 或已有文本/XML）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/process_fulltext_batch.py --limit 50
  python scripts/process_fulltext_batch.py --since-days 7 --dry-run
  python scripts/process_fulltext_batch.py --force --output-dir ./data/tei
        """,
    )
    parser.add_argument("--config", type=str, help="配置文件路径（默认自动检测）")
    parser.add_argument("--limit", type=int, help="处理的最大论文数量")
    parser.add_argument("--since-days", type=int, help="仅处理最近 N 天新增的论文")
    parser.add_argument("--force", action="store_true", help="即使已有 TEI 也重新生成")
    parser.add_argument("--dry-run", action="store_true", help="只输出计划，不写入数据库/文件")
    parser.add_argument("--output-dir", type=str, help="覆盖默认 TEI 输出目录")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    config_path = Path(args.config) if args.config else PROJECT_ROOT / "configs" / "config.test.yaml"
    if not config_path.exists():
        config_path = PROJECT_ROOT / "configs" / "config.yaml"
    if not config_path.exists():
        console.print(f"[bold red]配置文件不存在: {config_path}[/bold red]")
        console.print("参考: configs/config.yaml.example")
        raise SystemExit(1)

    config = load_config(config_path)
    setup_logging(config.logging)

    output_dir = Path(args.output_dir) if args.output_dir else None
    stats = await generate_tei_for_papers(
        config,
        limit=args.limit,
        since_days=args.since_days,
        force=args.force,
        dry_run=args.dry_run,
        output_dir=output_dir,
    )

    table = Table(title="TEI 生成结果")
    table.add_column("指标", style="cyan")
    table.add_column("数值", style="green", justify="right")

    table.add_row("候选论文数", str(stats["papers"]))
    table.add_row("已处理论文", str(stats["processed"]))
    table.add_row("成功数量", str(stats["success"]))
    table.add_row("跳过数量", str(stats["skipped"]))
    table.add_row("dry_run", str(stats["dry_run"]))

    console.print(table)


def main() -> None:
    args = parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()

