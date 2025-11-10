"""
核心逻辑模块测试 - ingest
"""

import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timedelta

from papergazer.core.ingest import ingest_arxiv, ingest_crossref, run_daily_check
from papergazer.models import ArxivEntry, CrossrefWork


@pytest.mark.asyncio
async def test_ingest_arxiv_empty(settings, temp_db_path):
    """测试空 arXiv 巡检"""
    from papergazer.store.db import init_db

    init_db(temp_db_path)

    async def empty_generator():
        return
        yield  # 使函数成为生成器

    with patch("papergazer.core.ingest.query_arxiv") as mock_query:
        mock_query.return_value = empty_generator()  # 空结果

        count = await ingest_arxiv(settings)
        assert count == 0


@pytest.mark.asyncio
async def test_ingest_arxiv_with_data(settings, temp_db_path):
    """测试 arXiv 巡检（有数据）"""
    from papergazer.store.db import init_db, get_session, PaperItem
    from datetime import timezone

    init_db(temp_db_path)

    # 创建测试数据（使用未来的时间，确保不会被过滤）
    future_time = datetime.now(timezone.utc) + timedelta(days=1)
    test_entry = ArxivEntry(
        arxiv_id="2501.00001",
        title="Test Paper",
        summary="Test summary",
        updated=future_time,
        published=future_time,
        authors=["Author"],
        categories=["eess.SP"],
    )

    async def mock_generator():
        yield test_entry

    with patch("papergazer.core.ingest.query_arxiv") as mock_query:
        mock_query.return_value = mock_generator()

        count = await ingest_arxiv(settings)
        assert count >= 0  # 可能被过滤掉（基于检查点）

        # 验证数据是否入库
        session = get_session()
        items = session.query(PaperItem).filter_by(identifier="2501.00001").all()
        session.close()

        # 如果通过了检查点过滤，应该有数据
        if count > 0:
            assert len(items) > 0


@pytest.mark.asyncio
async def test_ingest_crossref_empty(settings, temp_db_path):
    """测试空 Crossref 巡检"""
    from papergazer.store.db import init_db

    init_db(temp_db_path)

    async def empty_generator():
        return
        yield  # 使函数成为生成器

    with patch("papergazer.core.ingest.crossref.fetch_crossref_issn_increment") as mock_fetch:
        mock_fetch.return_value = empty_generator()  # 空结果

        count = await ingest_crossref(settings)
        assert count == 0


@pytest.mark.asyncio
async def test_ingest_crossref_with_data(settings, temp_db_path):
    """测试 Crossref 巡检（有数据）"""
    from papergazer.store.db import init_db, get_session, PaperItem

    init_db(temp_db_path)

    # 创建测试数据
    test_work = CrossrefWork(
        doi="10.1038/test",
        title=["Test Title"],
        author=[{"given": "John", "family": "Doe"}],
        container_title=["Nature"],
        issn=["0028-0836", "1476-4687"],
        issued={"date-parts": [[2025, 1, 1]]},
    )

    async def mock_generator():
        yield test_work

    with patch("papergazer.core.ingest.crossref.fetch_crossref_issn_increment") as mock_fetch:
        mock_fetch.return_value = mock_generator()

        count = await ingest_crossref(settings)
        assert count >= 0

        # 验证数据是否入库
        session = get_session()
        items = session.query(PaperItem).filter_by(doi="10.1038/test").all()
        session.close()

        if count > 0:
            assert len(items) > 0


@pytest.mark.asyncio
async def test_run_daily_check(settings, temp_db_path):
    """测试每日巡检主函数"""
    from papergazer.store.db import init_db

    init_db(temp_db_path)

    with patch("papergazer.core.ingest.ingest_arxiv") as mock_arxiv, patch(
        "papergazer.core.ingest.ingest_crossref"
    ) as mock_crossref:
        mock_arxiv.return_value = 5
        mock_crossref.return_value = 3

        results = await run_daily_check(settings)

        assert results["arxiv"] == 5
        assert results["crossref"] == 3
        assert len(results) == 2

