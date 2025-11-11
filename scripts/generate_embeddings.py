#!/usr/bin/env python3
"""
语义向量批量生成示例脚本
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from papergazer.config import load_config  # noqa: E402
from papergazer.core.embeddings import generate_embeddings_for_papers  # noqa: E402
from papergazer.utils import setup_logging  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="批量生成论文语义向量（调用核心模块）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/generate_embeddings.py --model sentence-transformers/all-MiniLM-L6-v2
  python scripts/generate_embeddings.py --fields title abstract tei --since-days 30 --limit 100
  python scripts/generate_embeddings.py --force --dry-run
        """,
    )
    parser.add_argument("--config", type=str, help="配置文件路径（默认自动检测）")
    parser.add_argument("--model", type=str, default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument(
        "--fields",
        nargs="+",
        default=["title", "abstract"],
        help="拼接文本字段（title / abstract / tei）",
    )
    parser.add_argument("--batch-size", type=int, default=32, help="模型编码批次大小")
    parser.add_argument("--since-days", type=int, help="仅处理最近 N 天的论文")
    parser.add_argument("--limit", type=int, help="限制处理的论文数量")
    parser.add_argument("--force", action="store_true", help="重新生成已存在的向量")
    parser.add_argument("--max-chars", type=int, default=4096, help="单篇文本截断长度")
    parser.add_argument("--dry-run", action="store_true", help="仅统计，不写入数据库")
    parser.add_argument("--verbose", action="store_true", help="输出详细日志")
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

    result = generate_embeddings_for_papers(
        config,
        model_name=args.model,
        fields=args.fields,
        batch_size=args.batch_size,
        since_days=args.since_days,
        limit=args.limit,
        force=args.force,
        max_chars=args.max_chars,
        dry_run=args.dry_run,
    )

    table = Table(title="语义向量生成结果")
    table.add_column("指标", style="cyan")
    table.add_column("数值", style="green", justify="right")
    table.add_row("候选论文数", str(result["papers"]))
    table.add_row("已处理", str(result["processed"]))
    table.add_row("成功写入", str(result["embedded"]))
    table.add_row("跳过", str(result["skipped"]))
    table.add_row("dry_run", str(result["dry_run"]))
    table.add_row("模型", result["model"])
    console.print(table)


if __name__ == "__main__":
    main()

