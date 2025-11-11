"""
数据库操作：SQLAlchemy ORM 模型与 CRUD
"""

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    Index,
    text,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from papergazer.models import Author, PaperMetadata


class Base(DeclarativeBase):
    """SQLAlchemy Base"""

    pass


class PaperItem(Base):
    """论文主表"""

    __tablename__ = "items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False, index=True)  # 'arxiv' | 'crossref'
    identifier = Column(String(255), nullable=False)  # arxiv_id 或 doi
    title = Column(Text)
    authors_json = Column(Text)  # JSON 数组
    venue = Column(String(255))  # 期刊/会议名称
    issn_print = Column(String(20))
    issn_online = Column(String(20))
    published_date = Column(Date, index=True)
    updated_date = Column(DateTime)
    doi = Column(String(255), unique=True, index=True)
    url_landing = Column(Text)
    is_oa = Column(Boolean, default=False)
    oa_source = Column(String(50))  # 'unpaywall' | 'eupmc' | 'arxiv'
    oa_pdf_url = Column(Text)
    pdf_path = Column(Text)
    tei_path = Column(Text)
    abstract_jats = Column(Text)
    figures_json = Column(Text)
    tables_json = Column(Text)
    crossref_json = Column(Text)
    openalex_json = Column(Text)
    unpaywall_json = Column(Text)
    references_json = Column(Text)
    funder_json = Column(Text)
    license_json = Column(Text)
    concepts_json = Column(Text)
    host_venue_json = Column(Text)
    referenced_work_ids_json = Column(Text)
    oa_status = Column(String(50))
    oa_license = Column(String(100))
    cited_by_count = Column(Integer)
    ingested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    hash = Column(String(64))  # 文件哈希（SHA256）

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
        authors_json = json.dumps([{"name": a.name, "affiliation": a.affiliation} for a in metadata.authors])

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

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False, index=True)  # 'arxiv' | 'crossref'
    last_checkpoint = Column(DateTime, nullable=False)
    items_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    cursor = Column(Text)
    summary_json = Column(Text)


class AuthorIdentity(Base):
    """作者标准化标识"""

    __tablename__ = "identities_author"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(Integer, index=True, nullable=False)
    local_index = Column(Integer, nullable=False)
    source_name = Column(String(255), nullable=False)
    normalized_name = Column(String(255))
    orcid = Column(String(32))
    confidence = Column(String(32))
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("paper_id", "local_index", name="uq_author_identity_unique"),
    )


class AffiliationIdentity(Base):
    """机构标准化标识"""

    __tablename__ = "identities_affiliation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(Integer, index=True, nullable=False)
    local_index = Column(Integer, nullable=False)
    source_name = Column(String(255), nullable=False)
    normalized_name = Column(String(255))
    ror_id = Column(String(64))
    country_code = Column(String(8))
    latitude = Column(String(32))
    longitude = Column(String(32))
    confidence = Column(String(32))
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("paper_id", "local_index", name="uq_affiliation_identity_unique"),
    )


class CitationEdge(Base):
    """引用关系"""

    __tablename__ = "graphs_citation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(Integer, index=True, nullable=False)
    cited_paper_id = Column(Integer, index=True)
    cited_doi = Column(String(255), index=True)
    relation_type = Column(String(64))
    weight = Column(Integer, default=1)
    raw_reference_json = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class ConceptMetric(Base):
    """概念统计指标"""

    __tablename__ = "analytics_concepts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    concept_id = Column(String(255), index=True)
    concept_name = Column(String(255), nullable=False)
    concept_level = Column(Integer)
    paper_count = Column(Integer, default=0)
    avg_score = Column(String(32))
    window_start = Column(DateTime, index=True, nullable=False)
    window_end = Column(DateTime, index=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    metadata_json = Column(Text)


class OAMetric(Base):
    """开放获取与 FAIR 指标"""

    __tablename__ = "analytics_oa"

    id = Column(Integer, primary_key=True, autoincrement=True)
    window_start = Column(DateTime, index=True, nullable=False)
    window_end = Column(DateTime, index=True, nullable=False)
    source = Column(String(64), index=True)
    total_count = Column(Integer, default=0)
    oa_count = Column(Integer, default=0)
    gold_count = Column(Integer, default=0)
    green_count = Column(Integer, default=0)
    bronze_count = Column(Integer, default=0)
    license_json = Column(Text)
    data_link_count = Column(Integer, default=0)
    code_link_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    metadata_json = Column(Text)


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

    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(items)"))
        columns = {row[1] for row in result}

        def add_column(name: str, col_type: str) -> None:
            nonlocal columns
            if name not in columns:
                conn.execute(text(f"ALTER TABLE items ADD COLUMN {name} {col_type}"))
                columns.add(name)

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
        existing = session.query(PaperItem).filter_by(source=metadata.source, identifier=metadata.identifier).first()

    if existing:
        # 更新现有记录
        existing.title = metadata.title
        existing.authors_json = json.dumps([{"name": a.name, "affiliation": a.affiliation} for a in metadata.authors])
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


def get_last_checkpoint(session: Session, source: str) -> Optional[datetime]:
    """
    获取上次巡检检查点

    Args:
        session: 数据库会话
        source: 数据源（'arxiv' 或 'crossref'）

    Returns:
        上次检查点时间或 None
    """
    record = session.query(RunRecord).filter_by(source=source).order_by(RunRecord.created_at.desc()).first()
    return record.last_checkpoint if record else None


def get_last_run(session: Session, source: str) -> Optional[RunRecord]:
    """
    获取最新的运行记录

    Args:
        session: 数据库会话
        source: 数据源

    Returns:
        RunRecord 或 None
    """
    return session.query(RunRecord).filter_by(source=source).order_by(RunRecord.created_at.desc()).first()


def update_checkpoint(
    session: Session,
    source: str,
    checkpoint: datetime,
    items_count: int = 0,
    *,
    cursor: Optional[str] = None,
    summary_json: Optional[str] = None,
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

