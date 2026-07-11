"""
数据库操作：SQLAlchemy ORM 模型与 CRUD
"""

import json
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from papergazer.models import Author, PaperMetadata


class Base(DeclarativeBase):
    """SQLAlchemy Base"""

    pass


class PaperItem(Base):
    """论文主表"""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    authors_json: Mapped[str | None] = mapped_column(Text)
    venue: Mapped[str | None] = mapped_column(String(255))
    issn_print: Mapped[str | None] = mapped_column(String(20))
    issn_online: Mapped[str | None] = mapped_column(String(20))
    published_date: Mapped[date | None] = mapped_column(Date, index=True)
    updated_date: Mapped[datetime | None] = mapped_column(DateTime)
    doi: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    url_landing: Mapped[str | None] = mapped_column(Text)
    is_oa: Mapped[bool] = mapped_column(Boolean, default=False)
    oa_source: Mapped[str | None] = mapped_column(String(50))
    oa_pdf_url: Mapped[str | None] = mapped_column(Text)
    pdf_path: Mapped[str | None] = mapped_column(Text)
    tei_path: Mapped[str | None] = mapped_column(Text)
    abstract_jats: Mapped[str | None] = mapped_column(Text)
    figures_json: Mapped[str | None] = mapped_column(Text)
    tables_json: Mapped[str | None] = mapped_column(Text)
    crossref_json: Mapped[str | None] = mapped_column(Text)
    openalex_json: Mapped[str | None] = mapped_column(Text)
    unpaywall_json: Mapped[str | None] = mapped_column(Text)
    references_json: Mapped[str | None] = mapped_column(Text)
    funder_json: Mapped[str | None] = mapped_column(Text)
    license_json: Mapped[str | None] = mapped_column(Text)
    concepts_json: Mapped[str | None] = mapped_column(Text)
    host_venue_json: Mapped[str | None] = mapped_column(Text)
    referenced_work_ids_json: Mapped[str | None] = mapped_column(Text)
    oa_status: Mapped[str | None] = mapped_column(String(50))
    oa_license: Mapped[str | None] = mapped_column(String(100))
    cited_by_count: Mapped[int | None] = mapped_column(Integer)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), index=True
    )
    hash: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        UniqueConstraint("source", "identifier", name="uq_source_identifier"),
        Index("idx_source_published", "source", "published_date"),
    )

    def to_metadata(self) -> PaperMetadata:
        """转换为 PaperMetadata"""
        authors = []
        if self.authors_json:
            try:
                authors_data = json.loads(self.authors_json)
                authors = [Author(**a) for a in authors_data]
            except (json.JSONDecodeError, TypeError):
                pass

        return PaperMetadata(
            source=self.source,
            identifier=self.identifier,
            title=self.title or "",
            authors=authors,
            venue=self.venue,
            issn_print=self.issn_print,
            issn_online=self.issn_online,
            published_date=self.published_date,
            updated_date=self.updated_date,
            doi=self.doi,
            url_landing=self.url_landing,
            abstract=self.abstract_jats,
        )

    @classmethod
    def from_metadata(cls, metadata: PaperMetadata) -> "PaperItem":
        """从 PaperMetadata 创建 PaperItem"""
        authors_json = json.dumps(
            [{"name": a.name, "affiliation": a.affiliation} for a in metadata.authors]
        )

        return cls(
            source=metadata.source,
            identifier=metadata.identifier,
            title=metadata.title,
            authors_json=authors_json,
            venue=metadata.venue,
            issn_print=metadata.issn_print,
            issn_online=metadata.issn_online,
            published_date=metadata.published_date,
            updated_date=metadata.updated_date,
            doi=metadata.doi,
            url_landing=metadata.url_landing,
            abstract_jats=metadata.abstract,
        )


class RunRecord(Base):
    """巡检记录表"""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    last_checkpoint: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    items_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    cursor: Mapped[str | None] = mapped_column(Text)
    summary_json: Mapped[str | None] = mapped_column(Text)


class AuthorIdentity(Base):
    """作者标准化标识"""

    __tablename__ = "identities_author"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    local_index: Mapped[int] = mapped_column(Integer, nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(String(255))
    orcid: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[str | None] = mapped_column(String(32))
    metadata_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint("paper_id", "local_index", name="uq_author_identity_unique"),
    )


class AffiliationIdentity(Base):
    """机构标准化标识"""

    __tablename__ = "identities_affiliation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    local_index: Mapped[int] = mapped_column(Integer, nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(String(255))
    ror_id: Mapped[str | None] = mapped_column(String(64))
    country_code: Mapped[str | None] = mapped_column(String(8))
    latitude: Mapped[str | None] = mapped_column(String(32))
    longitude: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[str | None] = mapped_column(String(32))
    metadata_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint("paper_id", "local_index", name="uq_affiliation_identity_unique"),
    )


class CitationEdge(Base):
    """引用关系"""

    __tablename__ = "graphs_citation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    cited_paper_id: Mapped[int | None] = mapped_column(Integer, index=True)
    cited_doi: Mapped[str | None] = mapped_column(String(255), index=True)
    relation_type: Mapped[str | None] = mapped_column(String(64))
    weight: Mapped[int] = mapped_column(Integer, default=1)
    raw_reference_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), index=True
    )


class ConceptMetric(Base):
    """概念统计指标"""

    __tablename__ = "analytics_concepts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    concept_id: Mapped[str | None] = mapped_column(String(255), index=True)
    concept_name: Mapped[str] = mapped_column(String(255), nullable=False)
    concept_level: Mapped[int | None] = mapped_column(Integer)
    paper_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_score: Mapped[str | None] = mapped_column(String(32))
    window_start: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), index=True
    )
    metadata_json: Mapped[str | None] = mapped_column(Text)


class OAMetric(Base):
    """开放获取与 FAIR 指标"""

    __tablename__ = "analytics_oa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    window_start: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    source: Mapped[str | None] = mapped_column(String(64), index=True)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    oa_count: Mapped[int] = mapped_column(Integer, default=0)
    gold_count: Mapped[int] = mapped_column(Integer, default=0)
    green_count: Mapped[int] = mapped_column(Integer, default=0)
    bronze_count: Mapped[int] = mapped_column(Integer, default=0)
    license_json: Mapped[str | None] = mapped_column(Text)
    data_link_count: Mapped[int] = mapped_column(Integer, default=0)
    code_link_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), index=True
    )
    metadata_json: Mapped[str | None] = mapped_column(Text)


class PaperEmbedding(Base):
    """论文语义向量"""

    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    vector_json: Mapped[str] = mapped_column(Text, nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    source_fields: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), index=True
    )

    __table_args__ = (UniqueConstraint("paper_id", "model_name", name="uq_embedding_paper_model"),)


class PipelineRun(Base):
    """Auditable execution of one or more pipeline stages."""

    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_uid: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    requested_stages_json: Mapped[str] = mapped_column(Text, nullable=False)
    scope_json: Mapped[str | None] = mapped_column(Text)
    config_digest: Mapped[str | None] = mapped_column(String(64), index=True)
    config_summary_json: Mapped[str | None] = mapped_column(Text)
    code_revision: Mapped[str | None] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    summary_json: Mapped[str | None] = mapped_column(Text)
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), index=True
    )


class PipelineJob(Base):
    """Recoverable per-paper unit of pipeline work."""

    __tablename__ = "pipeline_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    paper_id: Mapped[int | None] = mapped_column(Integer, index=True)
    stage: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_category: Mapped[str | None] = mapped_column(String(64), index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[str | None] = mapped_column(Text)
    result_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), index=True
    )

    __table_args__ = (
        UniqueConstraint("run_id", "paper_id", "stage", name="uq_pipeline_job_unit"),
        Index("idx_pipeline_job_resume", "run_id", "stage", "status", "next_retry_at"),
    )


class DataQualitySnapshot(Base):
    """Versioned inventory-quality measurement with explicit denominator."""

    __tablename__ = "data_quality_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int | None] = mapped_column(Integer, index=True)
    metric_name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    numerator: Mapped[int] = mapped_column(Integer, nullable=False)
    denominator: Mapped[int] = mapped_column(Integer, nullable=False)
    metric_value: Mapped[str] = mapped_column(String(64), nullable=False)
    dimensions_json: Mapped[str | None] = mapped_column(Text)
    schema_version: Mapped[str] = mapped_column(String(32), default="1", nullable=False)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), index=True
    )


class ManualCorrection(Base):
    """User-authored override that always takes precedence over automation."""

    __tablename__ = "manual_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[int | None] = mapped_column(Integer, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    entity_key: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    corrected_value_json: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), index=True
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)

    __table_args__ = (
        Index(
            "idx_manual_correction_lookup",
            "paper_id",
            "entity_type",
            "entity_key",
            "field_name",
            "superseded_at",
        ),
    )


# 全局变量
_engine = None
_SessionLocal = None


def init_db(db_path: str | Path) -> None:
    """
    初始化数据库

    Args:
        db_path: 数据库文件路径
    """
    global _engine, _SessionLocal

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # 创建引擎
    _engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},  # SQLite 需要
    )

    # 创建表
    Base.metadata.create_all(_engine)

    _ensure_schema(_engine)

    # Record and apply versioned migrations after the pre-Alembic compatibility
    # bridge has normalized legacy databases.
    from papergazer.store.migrations import upgrade_database

    upgrade_database(db_path)

    # 创建会话工厂
    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def get_session() -> Session:
    """
    获取数据库会话

    Returns:
        Session 实例

    Raises:
        RuntimeError: 如果数据库未初始化
    """
    if _SessionLocal is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")

    return _SessionLocal()


def _ensure_schema(engine) -> None:
    """
    确保数据库表包含最新的列（用于轻量级 schema 迁移）
    """

    # Schema changes must be committed atomically.  ``engine.connect()`` rolls
    # back an open SQLAlchemy 2.x transaction when the connection closes.
    with engine.begin() as conn:
        result = conn.execute(text("PRAGMA table_info(items)"))
        columns = {row[1] for row in result}

        def add_column(name: str, col_type: str) -> None:
            nonlocal columns
            if name not in columns:
                conn.execute(text(f"ALTER TABLE items ADD COLUMN {name} {col_type}"))
                columns.add(name)

        # Pre-Alembic releases did not have a formal baseline.  Normalize all
        # historical variants before stamping the versioned schema.
        add_column("authors_json", "TEXT")
        add_column("venue", "TEXT")
        add_column("issn_print", "TEXT")
        add_column("issn_online", "TEXT")
        add_column("published_date", "DATE")
        add_column("updated_date", "DATETIME")
        add_column("doi", "TEXT")
        add_column("url_landing", "TEXT")
        add_column("is_oa", "BOOLEAN DEFAULT 0")
        add_column("oa_source", "TEXT")
        add_column("oa_pdf_url", "TEXT")
        add_column("pdf_path", "TEXT")
        add_column("abstract_jats", "TEXT")
        add_column("ingested_at", "DATETIME")
        add_column("hash", "TEXT")
        add_column("tei_path", "TEXT")
        add_column("crossref_json", "TEXT")
        add_column("openalex_json", "TEXT")
        add_column("unpaywall_json", "TEXT")
        add_column("references_json", "TEXT")
        add_column("funder_json", "TEXT")
        add_column("license_json", "TEXT")
        add_column("concepts_json", "TEXT")
        add_column("host_venue_json", "TEXT")
        add_column("referenced_work_ids_json", "TEXT")
        add_column("oa_status", "TEXT")
        add_column("oa_license", "TEXT")
        add_column("cited_by_count", "INTEGER")
        add_column("figures_json", "TEXT")
        add_column("tables_json", "TEXT")

        # 更新 runs 表结构
        result = conn.execute(text("PRAGMA table_info(runs)"))
        # 初始化身份识别表
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS identities_author (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id INTEGER NOT NULL,
                    local_index INTEGER NOT NULL,
                    source_name TEXT NOT NULL,
                    normalized_name TEXT,
                    orcid TEXT,
                    confidence TEXT,
                    metadata_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(paper_id, local_index)
                )
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS identities_affiliation (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id INTEGER NOT NULL,
                    local_index INTEGER NOT NULL,
                    source_name TEXT NOT NULL,
                    normalized_name TEXT,
                    ror_id TEXT,
                    country_code TEXT,
                    latitude TEXT,
                    longitude TEXT,
                    confidence TEXT,
                    metadata_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(paper_id, local_index)
                )
                """
            )
        )
        run_columns = {row[1] for row in result}

        def add_run_column(name: str, col_type: str) -> None:
            nonlocal run_columns
            if name not in run_columns:
                conn.execute(text(f"ALTER TABLE runs ADD COLUMN {name} {col_type}"))
                run_columns.add(name)

        add_run_column("cursor", "TEXT")
        add_run_column("summary_json", "TEXT")


def upsert_paper(session: Session, metadata: PaperMetadata) -> PaperItem:
    """
    插入或更新论文记录

    Args:
        session: 数据库会话
        metadata: 论文元数据

    Returns:
        PaperItem 实例
    """
    # 查找现有记录（优先使用 DOI，否则使用 identifier）
    existing = None
    if metadata.doi:
        existing = session.query(PaperItem).filter_by(doi=metadata.doi).first()
    if not existing:
        existing = (
            session.query(PaperItem)
            .filter_by(source=metadata.source, identifier=metadata.identifier)
            .first()
        )

    if existing:
        # 更新现有记录
        existing.title = metadata.title
        existing.authors_json = json.dumps(
            [{"name": a.name, "affiliation": a.affiliation} for a in metadata.authors]
        )
        existing.venue = metadata.venue
        existing.issn_print = metadata.issn_print
        existing.issn_online = metadata.issn_online
        existing.published_date = metadata.published_date
        existing.updated_date = metadata.updated_date
        existing.doi = metadata.doi
        existing.url_landing = metadata.url_landing
        existing.abstract_jats = metadata.abstract
        return existing
    else:
        # 插入新记录
        item = PaperItem.from_metadata(metadata)
        session.add(item)
        return item


def get_last_checkpoint(session: Session, source: str) -> datetime | None:
    """
    获取上次巡检检查点

    Args:
        session: 数据库会话
        source: 数据源（'arxiv' 或 'crossref'）

    Returns:
        上次检查点时间或 None
    """
    record = (
        session.query(RunRecord)
        .filter_by(source=source)
        .order_by(RunRecord.created_at.desc())
        .first()
    )
    return record.last_checkpoint if record else None


def get_last_run(session: Session, source: str) -> RunRecord | None:
    """
    获取最新的运行记录

    Args:
        session: 数据库会话
        source: 数据源

    Returns:
        RunRecord 或 None
    """
    return (
        session.query(RunRecord)
        .filter_by(source=source)
        .order_by(RunRecord.created_at.desc())
        .first()
    )


def update_checkpoint(
    session: Session,
    source: str,
    checkpoint: datetime,
    items_count: int = 0,
    *,
    cursor: str | None = None,
    summary_json: str | None = None,
) -> None:
    """
    更新巡检检查点

    Args:
        session: 数据库会话
        source: 数据源
        checkpoint: 检查点时间
        items_count: 本次巡检抓取的项目数
    """
    record = RunRecord(
        source=source,
        last_checkpoint=checkpoint,
        items_count=items_count,
        cursor=cursor,
        summary_json=summary_json,
    )
    session.add(record)
