#!/usr/bin/env python3
"""
作者/机构身份标准化示例脚本
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from papergazer.config import load_config  # noqa: E402
from papergazer.core.identity_enrich import enrich_identities  # noqa: E402
from papergazer.utils import setup_logging  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ORCID/ROR 身份匹配（调用核心模块）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/enrich_identities.py --since-days 7
  python scripts/enrich_identities.py --dry-run --limit 5
  python scripts/enrich_identities.py --force --skip-orcid
        """,
    )
    parser.add_argument("--config", type=str, help="配置文件路径")
    parser.add_argument("--since-days", type=int, help="仅处理最近 N 天的论文")
    parser.add_argument("--limit", type=int, help="限制论文数量")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["arxiv", "crossref", "eupmc", "unpaywall"],
        help="按数据源过滤",
    )
    parser.add_argument("--dry-run", action="store_true", help="只预览结果，不写入数据库")
    parser.add_argument("--force", action="store_true", help="强制重新匹配并覆盖旧结果")
    parser.add_argument("--skip-orcid", action="store_true", help="跳过 ORCID 匹配")
    parser.add_argument("--skip-ror", action="store_true", help="跳过 ROR 匹配")
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

    stats = enrich_identities(
        config,
        since_days=args.since_days,
        limit=args.limit,
        sources=args.sources,
        dry_run=args.dry_run,
        force=args.force,
        skip_orcid=args.skip_orcid,
        skip_ror=args.skip_ror,
    )

    table = Table(title="身份匹配结果")
    table.add_column("指标", style="cyan")
    table.add_column("数值", style="green", justify="right")

    table.add_row("候选论文数", str(stats["papers"]))
    table.add_row("作者记录", str(stats["authors"]))
    table.add_row("机构记录", str(stats["affiliations"]))
    table.add_row("跳过论文", str(stats["skipped"]))
    table.add_row("dry_run", str(args.dry_run))

    console.print(table)


if __name__ == "__main__":
    main()

