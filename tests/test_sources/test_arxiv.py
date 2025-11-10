"""
arXiv 数据源模块测试
"""

import pytest
from unittest.mock import patch, AsyncMock, Mock
from datetime import datetime

from papergazer.sources.arxiv import query_arxiv, query_arxiv_batch
from papergazer.models import ArxivEntry


@pytest.mark.asyncio
async def test_query_arxiv_empty_result():
    """测试空结果"""
    with patch("papergazer.sources.arxiv.httpx.AsyncClient") as mock_client:
        mock_response = AsyncMock()
        mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2501.00001</id>
    <title>Test Paper</title>
    <summary>Test summary</summary>
    <updated>2025-01-01T00:00:00Z</updated>
    <published>2025-01-01T00:00:00Z</published>
    <author><name>Test Author</name></author>
    <link rel="related" type="application/pdf" title="pdf" href="http://arxiv.org/pdf/2501.00001.pdf"/>
  </entry>
</feed>"""
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_client_instance

        results = []
        async for entry in query_arxiv(["eess.SP"], max_results=10, delay_seconds=0):
            results.append(entry)

        assert len(results) > 0
        assert isinstance(results[0], ArxivEntry)
        assert results[0].arxiv_id == "2501.00001"
        assert results[0].title == "Test Paper"


@pytest.mark.asyncio
async def test_query_arxiv_batch():
    """测试批量查询"""
    with patch("papergazer.sources.arxiv.query_arxiv") as mock_query:
        mock_entry = ArxivEntry(
            arxiv_id="2501.00001",
            title="Test",
            summary="Summary",
            updated=datetime.now(),
            published=datetime.now(),
            authors=["Author"],
            categories=["eess.SP"],
        )

        async def mock_generator():
            for i in range(5):
                yield mock_entry

        mock_query.return_value = mock_generator()

        results = await query_arxiv_batch(["eess.SP"], max_results=10, delay_seconds=0)

        assert len(results) == 5
        assert all(isinstance(r, ArxivEntry) for r in results)


@pytest.mark.asyncio
async def test_arxiv_entry_to_metadata():
    """测试 ArxivEntry 转换为 PaperMetadata"""
    entry = ArxivEntry(
        arxiv_id="2501.00001",
        title="Test Paper",
        summary="Test summary",
        updated=datetime(2025, 1, 1),
        published=datetime(2025, 1, 1),
        authors=["Author 1", "Author 2"],
        categories=["eess.SP"],
        pdf_url="http://arxiv.org/pdf/2501.00001.pdf",
        doi="10.1234/test",
    )

    metadata = entry.to_metadata()

    assert metadata.source == "arxiv"
    assert metadata.identifier == "2501.00001"
    assert metadata.title == "Test Paper"
    assert len(metadata.authors) == 2
    assert metadata.doi == "10.1234/test"
    assert metadata.url_landing == "https://arxiv.org/abs/2501.00001"

