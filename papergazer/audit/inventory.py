"""Reproducible full-inventory quality measurements."""

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy import func

from papergazer.store.db import (
    AffiliationIdentity,
    AuthorIdentity,
    CitationEdge,
    DataQualitySnapshot,
    PaperEmbedding,
    PaperItem,
    get_session,
)

SCHEMA_VERSION = "1"


class QualityMetric(BaseModel):
    name: str
    numerator: int
    denominator: int
    dimensions: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @property
    def ratio(self) -> float:
        return self.numerator / self.denominator if self.denominator else 0.0


class InventoryAudit(BaseModel):
    generated_at: datetime
    schema_version: str = SCHEMA_VERSION
    total_papers: int
    source_counts: dict[str, int]
    metrics: list[QualityMetric]
    missing_local_files: list[str]
    orphan_local_files: list[str]

    def metric(self, name: str) -> QualityMetric:
        return next(metric for metric in self.metrics if metric.name == name)

    def to_markdown(self) -> str:
        lines = [
            "# PaperGazer 全库存数据质量报告",
            "",
            f"- 生成时间：{self.generated_at.isoformat()}",
            f"- Schema：{self.schema_version}",
            f"- 论文总量：{self.total_papers}",
            "",
            "## 来源分布",
            "",
            "| 来源 | 数量 |",
            "|---|---:|",
        ]
        lines.extend(
            f"| {source} | {count} |" for source, count in sorted(self.source_counts.items())
        )
        lines.extend(
            [
                "",
                "## 完整性指标",
                "",
                "| 指标 | 分子 | 分母 | 比例 |",
                "|---|---:|---:|---:|",
            ]
        )
        lines.extend(
            f"| {metric.name} | {metric.numerator} | {metric.denominator} | {metric.ratio:.2%} |"
            for metric in self.metrics
        )
        lines.extend(
            [
                "",
                "## 文件一致性",
                "",
                f"- 数据库指向但本地缺失：{len(self.missing_local_files)}",
                f"- 本地存在但数据库未引用：{len(self.orphan_local_files)}",
                "",
            ]
        )
        return "\n".join(lines)


def _count_present(session, column) -> int:
    return int(
        session.query(func.count(PaperItem.id)).filter(column.isnot(None), column != "").scalar()
        or 0
    )


def _local_file_consistency(
    papers: list[PaperItem], papers_dir: Path
) -> tuple[list[str], list[str]]:
    referenced: set[Path] = set()
    missing: list[str] = []
    for paper in papers:
        for raw_path in (paper.pdf_path, paper.tei_path):
            if not raw_path:
                continue
            path = Path(raw_path).resolve()
            referenced.add(path)
            if not path.exists():
                missing.append(str(path))

    local_files = {
        path.resolve()
        for pattern in ("*.pdf", "*.tei.xml", "*.xml")
        for path in papers_dir.rglob(pattern)
        if path.is_file()
    }
    return sorted(set(missing)), sorted(str(path) for path in local_files - referenced)


def run_inventory_audit(
    papers_dir: str | Path,
    *,
    persist: bool = True,
    run_id: int | None = None,
) -> InventoryAudit:
    """Measure the complete current inventory with explicit denominators."""
    session = get_session()
    try:
        total = int(session.query(func.count(PaperItem.id)).scalar() or 0)
        source_rows = session.query(PaperItem.source, func.count(PaperItem.id)).group_by(
            PaperItem.source
        )
        source_counts = {str(source): int(count) for source, count in source_rows.all()}
        papers = session.query(PaperItem).all()

        metrics = [
            QualityMetric(
                name="doi_coverage",
                numerator=_count_present(session, PaperItem.doi),
                denominator=total,
            ),
            QualityMetric(
                name="abstract_coverage",
                numerator=_count_present(session, PaperItem.abstract_jats),
                denominator=total,
            ),
            QualityMetric(
                name="authors_coverage",
                numerator=_count_present(session, PaperItem.authors_json),
                denominator=total,
            ),
            QualityMetric(
                name="published_date_coverage",
                numerator=_count_present(session, PaperItem.published_date),
                denominator=total,
            ),
            QualityMetric(
                name="crossref_enrichment_coverage",
                numerator=_count_present(session, PaperItem.crossref_json),
                denominator=total,
            ),
            QualityMetric(
                name="openalex_enrichment_coverage",
                numerator=_count_present(session, PaperItem.openalex_json),
                denominator=total,
            ),
            QualityMetric(
                name="unpaywall_enrichment_coverage",
                numerator=_count_present(session, PaperItem.unpaywall_json),
                denominator=total,
            ),
            QualityMetric(
                name="pdf_coverage",
                numerator=_count_present(session, PaperItem.pdf_path),
                denominator=total,
            ),
            QualityMetric(
                name="tei_coverage",
                numerator=_count_present(session, PaperItem.tei_path),
                denominator=total,
            ),
            QualityMetric(
                name="figures_coverage",
                numerator=_count_present(session, PaperItem.figures_json),
                denominator=total,
            ),
            QualityMetric(
                name="concepts_coverage",
                numerator=_count_present(session, PaperItem.concepts_json),
                denominator=total,
            ),
            QualityMetric(
                name="author_identity_coverage",
                numerator=int(
                    session.query(func.count(func.distinct(AuthorIdentity.paper_id))).scalar() or 0
                ),
                denominator=total,
            ),
            QualityMetric(
                name="affiliation_identity_coverage",
                numerator=int(
                    session.query(func.count(func.distinct(AffiliationIdentity.paper_id))).scalar()
                    or 0
                ),
                denominator=total,
            ),
            QualityMetric(
                name="citation_edge_coverage",
                numerator=int(
                    session.query(func.count(func.distinct(CitationEdge.paper_id))).scalar() or 0
                ),
                denominator=total,
            ),
            QualityMetric(
                name="embedding_coverage",
                numerator=int(
                    session.query(func.count(func.distinct(PaperEmbedding.paper_id))).scalar() or 0
                ),
                denominator=total,
            ),
        ]
        missing, orphan = _local_file_consistency(papers, Path(papers_dir))
        audit = InventoryAudit(
            generated_at=datetime.now(UTC),
            total_papers=total,
            source_counts=source_counts,
            metrics=metrics,
            missing_local_files=missing,
            orphan_local_files=orphan,
        )

        if persist:
            for metric in metrics:
                session.add(
                    DataQualitySnapshot(
                        run_id=run_id,
                        metric_name=metric.name,
                        numerator=metric.numerator,
                        denominator=metric.denominator,
                        metric_value=f"{metric.ratio:.12f}",
                        dimensions_json=json.dumps(metric.dimensions, ensure_ascii=False),
                        schema_version=SCHEMA_VERSION,
                    )
                )
            session.commit()
        return audit
    finally:
        session.close()


def write_inventory_audit(audit: InventoryAudit, output_dir: str | Path) -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "data_quality.json"
    markdown_path = output / "data_quality.md"
    json_path.write_text(audit.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(audit.to_markdown(), encoding="utf-8")
    return json_path, markdown_path
