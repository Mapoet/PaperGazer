"""
集成测试：完整 Pipeline
"""

from datetime import datetime

import pytest

from papergazer.core.fetch import fetch_by_identifier
from papergazer.core.ingest import run_daily_check
from papergazer.store.db import PaperItem, RunRecord, get_session, init_db


@pytest.mark.asyncio
async def test_full_pipeline_ingest(settings, temp_db_path):
    """测试完整巡检 Pipeline"""
    from unittest.mock import patch

    from papergazer.store.db import init_db

    init_db(temp_db_path)

    async def empty_generator():
        return
        yield

    # 运行巡检（使用 mock 数据）
    with (
        patch("papergazer.core.ingest.query_arxiv") as mock_arxiv,
        patch("papergazer.core.ingest.crossref.fetch_crossref_issn_increment") as mock_crossref,
    ):
        # Mock 空结果（避免实际 API 调用）
        mock_arxiv.return_value = empty_generator()
        mock_crossref.return_value = empty_generator()

        results = await run_daily_check(settings)

        assert "arxiv" in results
        assert "crossref" in results

        # 验证检查点已更新
        session = get_session()
        arxiv_runs = session.query(RunRecord).filter_by(source="arxiv").all()
        crossref_runs = session.query(RunRecord).filter_by(source="crossref").all()
        session.close()

        # 即使没有数据，也应该有运行记录
        assert len(arxiv_runs) > 0 or len(crossref_runs) > 0


@pytest.mark.asyncio
async def test_full_pipeline_fetch(settings, temp_db_path, temp_papers_dir):
    """测试完整抓取 Pipeline"""
    from unittest.mock import patch

    from papergazer.store.db import PaperItem, init_db

    init_db(temp_db_path)

    # 测试 arXiv 抓取
    with patch("papergazer.core.fetch.fetch_arxiv_pdf") as mock_fetch:
        test_pdf = temp_papers_dir / "test.pdf"
        test_pdf.parent.mkdir(parents=True, exist_ok=True)
        test_pdf.write_bytes(b"test pdf")
        test_hash = "test_hash"

        mock_fetch.return_value = (test_pdf, test_hash)

        result = await fetch_by_identifier("2501.00001", settings)

        assert result["success"] is True

        # 验证数据库记录
        session = get_session()
        items = session.query(PaperItem).filter_by(identifier="2501.00001").all()
        session.close()

        if result["success"]:
            assert len(items) > 0
            assert items[0].pdf_path is not None


@pytest.mark.asyncio
async def test_database_persistence(settings, temp_db_path):
    """测试数据库持久化"""
    init_db(temp_db_path)

    from papergazer.models import Author, PaperMetadata
    from papergazer.store.db import upsert_paper

    # 插入数据
    metadata = PaperMetadata(
        source="arxiv",
        identifier="2501.00001",
        title="Test Paper",
        authors=[Author(name="Author")],
        published_date=datetime.now().date(),
    )

    session = get_session()
    item = upsert_paper(session, metadata)
    session.commit()
    item_id = item.id
    session.close()

    # 重新打开会话，验证数据持久化
    session2 = get_session()
    retrieved = session2.query(PaperItem).filter_by(id=item_id).first()
    session2.close()

    assert retrieved is not None
    assert retrieved.identifier == "2501.00001"
    assert retrieved.title == "Test Paper"
