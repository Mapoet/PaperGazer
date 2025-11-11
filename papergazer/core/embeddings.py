"""
语义向量生成核心逻辑。

默认使用 sentence-transformers 提供的语义模型，将标题 / 摘要 /
（可选）TEI 全文压缩为固定长度向量，写入 `embeddings` 表。
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from papergazer.config import Settings
from papergazer.store.db import (
    PaperEmbedding,
    PaperItem,
    get_session,
    init_db,
)
from papergazer.utils.db_filters import get_effective_date_filter

logger = logging.getLogger(__name__)

FIELD_ALIAS = {
    "title": "title",
    "abstract": "abstract_jats",
    "abstract_jats": "abstract_jats",
    "tei": "tei_path",
}

TAG_CLEANER = re.compile(r"<[^>]+>")


def _load_model(model_name: str):
    """延迟导入 embedding 模型，避免无用依赖。"""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover - 仅在缺失依赖时触发
        raise RuntimeError(
            "生成语义向量需要安装 sentence-transformers，请执行 "
            "`pip install sentence-transformers` 后重试。"
        ) from exc

    return SentenceTransformer(model_name)


def _clean_markup(text: str) -> str:
    """去除简单 XML/HTML 标签并压缩空白。"""
    stripped = TAG_CLEANER.sub(" ", text)
    return re.sub(r"\s+", " ", stripped).strip()


def _compose_text(paper: PaperItem, fields: Sequence[str], max_chars: int) -> str:
    """根据配置字段拼接文本内容。"""
    fragments: List[str] = []

    for field in fields:
        attr = FIELD_ALIAS.get(field, field)
        value = getattr(paper, attr, None)
        if not value:
            continue

        if attr == "tei_path":
            path = Path(value)
            if path.is_file():
                try:
                    tei_text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    logger.debug("读取 TEI 失败，忽略：%s", path)
                    continue
                fragments.append(_clean_markup(tei_text))
        elif attr == "abstract_jats":
            fragments.append(_clean_markup(value))
        else:
            fragments.append(value.strip())

    text = " ".join(fragment for fragment in fragments if fragment)
    if max_chars and len(text) > max_chars:
        text = text[:max_chars]
    return text.strip()


def _chunk(items: Sequence[PaperItem], size: int) -> Iterable[Sequence[PaperItem]]:
    """按固定批次切片（避免外部依赖）。"""
    total = len(items)
    if total == 0:
        return
    for start in range(0, total, size):
        yield items[start : start + size]


def generate_embeddings_for_papers(
    config: Settings,
    *,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    fields: Sequence[str] = ("title", "abstract"),
    batch_size: int = 32,
    since_days: Optional[int] = None,
    limit: Optional[int] = None,
    force: bool = False,
    max_chars: int = 4096,
    dry_run: bool = False,
) -> dict:
    """
    为论文生成语义向量并写入数据库。

    Args:
        config: 全局配置
        model_name: sentence-transformers 模型名称
        fields: 参与拼接的字段（title / abstract / tei）
        batch_size: 模型编码批次大小
        since_days: 仅处理最近 N 天的论文
        limit: 限制处理论文数量
        force: 覆盖已有向量
        max_chars: 每篇文章截断长度，避免内存膨胀
        dry_run: 仅统计，不写入数据库
    """
    init_db(config.store.db_path)
    session = get_session()

    stats = {
        "papers": 0,
        "processed": 0,
        "embedded": 0,
        "skipped": 0,
        "dry_run": dry_run,
        "model": model_name,
    }

    now = datetime.now(timezone.utc)

    try:
        query = session.query(PaperItem)

        if since_days is not None:
            cutoff = now - timedelta(days=since_days)
            query = query.filter(get_effective_date_filter(cutoff))

        query = query.order_by(PaperItem.ingested_at.desc().nullslast())

        if limit:
            query = query.limit(limit)

        papers = query.all()
        stats["papers"] = len(papers)

        if not papers:
            logger.info("没有符合条件的论文需要生成语义向量。")
            return stats

        logger.info(
            "准备为 %s 篇论文生成语义向量（model=%s，dry-run=%s）",
            len(papers),
            model_name,
            dry_run,
        )

        existing_ids = set()
        if not force:
            existing_rows = (
                session.query(PaperEmbedding.paper_id)
                .filter(
                    PaperEmbedding.model_name == model_name,
                    PaperEmbedding.paper_id.in_([paper.id for paper in papers]),
                )
                .all()
            )
            existing_ids = {row[0] for row in existing_rows}

        model = None

        for chunk in _chunk(papers, batch_size=batch_size):
            texts: List[str] = []
            to_embed: List[PaperItem] = []

            for paper in chunk:
                stats["processed"] += 1

                if not force and paper.id in existing_ids:
                    stats["skipped"] += 1
                    continue

                text = _compose_text(paper, fields, max_chars)
                if not text:
                    stats["skipped"] += 1
                    continue

                texts.append(text)
                to_embed.append(paper)

            if not texts:
                continue

            if dry_run:
                stats["embedded"] += len(texts)
                continue

            if model is None:
                model = _load_model(model_name)

            embeddings = model.encode(
                texts,
                batch_size=min(batch_size, len(texts)),
                show_progress_bar=False,
            )

            for paper, vector in zip(to_embed, embeddings):
                vector_list = vector.tolist() if hasattr(vector, "tolist") else list(vector)
                dimension = len(vector_list)

                session.merge(
                    PaperEmbedding(
                        paper_id=paper.id,
                        model_name=model_name,
                        vector_json=json.dumps(vector_list, ensure_ascii=False),
                        dimension=dimension,
                        source_fields=",".join(fields),
                    )
                )

            session.commit()
            stats["embedded"] += len(to_embed)

    finally:
        session.close()

    logger.info(
        "语义向量生成完成：处理 %s，成功 %s，跳过 %s（dry-run=%s）",
        stats["processed"],
        stats["embedded"],
        stats["skipped"],
        dry_run,
    )
    return stats
