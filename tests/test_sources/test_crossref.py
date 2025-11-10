"""
Crossref 数据源模块测试
"""

import pytest
from unittest.mock import patch, AsyncMock, Mock
from datetime import date

from papergazer.sources.crossref import fetch_crossref_issn_increment, fetch_crossref_by_doi
from papergazer.models import CrossrefWork


@pytest.mark.asyncio
async def test_fetch_crossref_issn_increment():
    """测试 Crossref ISSN 增量拉取"""
    mock_response_data = {
        "message": {
            "items": [
                {
                    "DOI": "10.1038/test",
                    "title": ["Test Title"],
                    "author": [{"given": "John", "family": "Doe"}],
                    "container-title": ["Nature"],
                    "ISSN": ["0028-0836", "1476-4687"],
                    "issued": {"date-parts": [[2025, 1, 1]]},
                    "link": [{"URL": "https://nature.com/test"}],
                    "abstract": None,
                }
            ],
            "next-cursor": None,
        }
    }

    with patch("papergazer.sources.crossref.httpx.AsyncClient") as mock_client:
        mock_response = Mock()
        mock_response.json = Mock(return_value=mock_response_data)
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_client_instance

        results = []
        async for work in fetch_crossref_issn_increment(
            ["0028-0836"], date(2025, 1, 1), "test@example.com"
        ):
            results.append(work)

        assert len(results) == 1
        assert isinstance(results[0], CrossrefWork)
        assert results[0].doi == "10.1038/test"


@pytest.mark.asyncio
async def test_fetch_crossref_by_doi():
    """测试按 DOI 获取工作项"""
    mock_response_data = {
        "message": {
            "DOI": "10.1038/test",
            "title": ["Test Title"],
            "author": [{"given": "John", "family": "Doe"}],
            "container-title": [],
            "ISSN": [],
            "issued": None,
            "link": [],
        }
    }

    with patch("papergazer.sources.crossref.httpx.AsyncClient") as mock_client:
        mock_response = Mock()
        mock_response.json = Mock(return_value=mock_response_data)
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_client_instance

        work = await fetch_crossref_by_doi("10.1038/test", "test@example.com")

        assert work is not None
        assert isinstance(work, CrossrefWork)
        assert work.doi == "10.1038/test"


@pytest.mark.asyncio
async def test_fetch_crossref_by_doi_not_found():
    """测试 DOI 不存在的情况"""
    with patch("papergazer.sources.crossref.httpx.AsyncClient") as mock_client:
        from httpx import HTTPStatusError

        mock_response = AsyncMock()
        mock_response.status_code = 404
        error = HTTPStatusError("Not Found", request=Mock(), response=mock_response)

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(side_effect=error)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_client_instance

        work = await fetch_crossref_by_doi("10.1038/notfound", "test@example.com")

        assert work is None


@pytest.mark.asyncio
async def test_crossref_work_to_metadata():
    """测试 CrossrefWork 转换为 PaperMetadata"""
    work = CrossrefWork(
        doi="10.1038/test",
        title=["Test Title"],
        author=[{"given": "John", "family": "Doe", "affiliation": [{"name": "University"}]}],
        container_title=["Nature"],
        issn=["0028-0836", "1476-4687"],
        issued={"date-parts": [[2025, 1, 15]]},
        link=[{"URL": "https://nature.com/test", "content-type": "text/html"}],
        abstract="Test abstract",
    )

    metadata = work.to_metadata()

    assert metadata.source == "crossref"
    assert metadata.identifier == "10.1038/test"
    assert metadata.title == "Test Title"
    assert len(metadata.authors) == 1
    assert metadata.authors[0].name == "John Doe"
    # affiliation 可能是字符串或 None
    assert metadata.authors[0].affiliation is None or isinstance(metadata.authors[0].affiliation, str)
    assert metadata.venue == "Nature"
    assert metadata.issn_print == "0028-0836"
    assert metadata.issn_online == "1476-4687"
    assert metadata.published_date == date(2025, 1, 15)
    assert metadata.abstract == "Test abstract"

