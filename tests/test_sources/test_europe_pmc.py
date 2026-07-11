"""
Europe PMC 数据源模块测试
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from papergazer.sources.europe_pmc import doi_to_pmcid, fetch_fulltext_xml


@pytest.mark.asyncio
async def test_doi_to_pmcid():
    """测试 DOI 转 PMCID"""
    mock_response_data = {
        "resultList": {
            "result": [
                {
                    "pmcid": "PMC123456",
                    "doi": "10.1038/test",
                    "title": "Test Title",
                }
            ]
        }
    }

    with patch("papergazer.sources.europe_pmc.httpx.AsyncClient") as mock_client:
        mock_response = Mock()
        mock_response.json = Mock(return_value=mock_response_data)
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_client_instance

        pmcid = await doi_to_pmcid("10.1038/test")

        assert pmcid == "PMC123456"


@pytest.mark.asyncio
async def test_doi_to_pmcid_not_found():
    """测试 DOI 不存在的情况"""
    mock_response_data = {"resultList": {"result": []}}

    with patch("papergazer.sources.europe_pmc.httpx.AsyncClient") as mock_client:
        mock_response = Mock()
        mock_response.json = Mock(return_value=mock_response_data)
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_client_instance

        pmcid = await doi_to_pmcid("10.1038/notfound")

        assert pmcid is None


@pytest.mark.asyncio
async def test_fetch_fulltext_xml():
    """测试获取 FullTextXML"""
    mock_xml_content = b"<?xml version='1.0'?><article>Test XML</article>"

    with patch("papergazer.sources.europe_pmc.httpx.AsyncClient") as mock_client:
        mock_response = Mock()
        mock_response.content = mock_xml_content
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_client_instance

        xml_content = await fetch_fulltext_xml("123456")

        assert xml_content == mock_xml_content


@pytest.mark.asyncio
async def test_fetch_fulltext_xml_with_pmc_prefix():
    """测试带 PMC 前缀的 PMCID"""
    mock_xml_content = b"<?xml version='1.0'?><article>Test XML</article>"

    with patch("papergazer.sources.europe_pmc.httpx.AsyncClient") as mock_client:
        mock_response = Mock()
        mock_response.content = mock_xml_content
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_client_instance

        xml_content = await fetch_fulltext_xml("PMC123456")

        assert xml_content == mock_xml_content
        # 验证 PMC 前缀被去除
        mock_client_instance.get.assert_called_once()
        call_args = mock_client_instance.get.call_args[0][0]
        assert "PMC" not in call_args or call_args.endswith("/123456/fullTextXML")
