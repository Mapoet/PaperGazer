"""
数据库模块测试
"""

from datetime import date, datetime

import pytest

from papergazer.models import Author, PaperMetadata
from papergazer.store.db import (
    get_last_checkpoint,
    get_session,
    init_db,
    update_checkpoint,
    upsert_paper,
)


@pytest.fixture
def db_session(temp_db_path):
    """数据库会话"""
    init_db(temp_db_path)
    session = get_session()
    yield session
    session.close()


def test_init_db(temp_db_path):
    """测试数据库初始化"""
    init_db(temp_db_path)
    assert temp_db_path.exists()

    session = get_session()
    # 验证表已创建
    from sqlalchemy import inspect

    inspector = inspect(session.bind)
    tables = inspector.get_table_names()
    assert "items" in tables
    assert "runs" in tables
    session.close()


def test_upsert_paper_insert(db_session):
    """测试插入新论文"""
    metadata = PaperMetadata(
        source="arxiv",
        identifier="2501.00001",
        title="Test Paper",
        authors=[Author(name="Test Author")],
        published_date=date(2025, 1, 1),
        doi="10.1234/test",
    )

    item = upsert_paper(db_session, metadata)
    db_session.commit()

    assert item.id is not None
    assert item.source == "arxiv"
    assert item.identifier == "2501.00001"
    assert item.title == "Test Paper"
    assert item.doi == "10.1234/test"


def test_upsert_paper_update(db_session):
    """测试更新现有论文"""
    metadata1 = PaperMetadata(
        source="arxiv",
        identifier="2501.00001",
        title="Old Title",
        authors=[Author(name="Author 1")],
    )

    item1 = upsert_paper(db_session, metadata1)
    db_session.commit()

    # 更新论文
    metadata2 = PaperMetadata(
        source="arxiv",
        identifier="2501.00001",
        title="New Title",
        authors=[Author(name="Author 2")],
    )

    item2 = upsert_paper(db_session, metadata2)
    db_session.commit()

    assert item1.id == item2.id
    assert item2.title == "New Title"


def test_upsert_paper_by_doi(db_session):
    """测试通过 DOI 去重"""
    metadata1 = PaperMetadata(
        source="arxiv",
        identifier="2501.00001",
        title="Title 1",
        doi="10.1234/test",
    )

    metadata2 = PaperMetadata(
        source="crossref",
        identifier="10.1234/test",
        title="Title 2",
        doi="10.1234/test",
    )

    item1 = upsert_paper(db_session, metadata1)
    db_session.commit()
    item1_id = item1.id

    item2 = upsert_paper(db_session, metadata2)
    db_session.commit()

    # 应该更新同一个记录（通过 DOI 匹配）
    assert item1_id == item2.id
    # 注意：由于 upsert_paper 的逻辑，如果通过 DOI 找到现有记录，会更新它
    assert item2.doi == "10.1234/test"


def test_get_last_checkpoint_empty(db_session):
    """测试获取空检查点"""
    checkpoint = get_last_checkpoint(db_session, "arxiv")
    assert checkpoint is None


def test_update_checkpoint(db_session):
    """测试更新检查点"""
    checkpoint = datetime(2025, 1, 1, 12, 0, 0)
    update_checkpoint(db_session, "arxiv", checkpoint, items_count=10)
    db_session.commit()

    last_checkpoint = get_last_checkpoint(db_session, "arxiv")
    assert last_checkpoint == checkpoint


def test_paper_item_to_metadata(db_session):
    """测试 PaperItem 转换为 PaperMetadata"""
    metadata = PaperMetadata(
        source="arxiv",
        identifier="2501.00001",
        title="Test Paper",
        authors=[Author(name="Author 1"), Author(name="Author 2")],
        published_date=date(2025, 1, 1),
    )

    item = upsert_paper(db_session, metadata)
    db_session.commit()

    converted = item.to_metadata()
    assert converted.source == "arxiv"
    assert converted.identifier == "2501.00001"
    assert converted.title == "Test Paper"
    assert len(converted.authors) == 2
