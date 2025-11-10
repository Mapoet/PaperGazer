"""
Unpaywall 数据源模块测试
"""

import pytest
from unittest.mock import patch, AsyncMock, Mock

from papergazer.sources.unpaywall import best_oa
from papergazer.models import UnpaywallResponse


@pytest.mark.asyncio
async def test_best_oa_is_oa():
    """测试 OA 论文"""
    mock_response_data = {
        "is_oa": True,
        "best_oa_location": {
            "url_for_pdf": "https://example.com/paper.pdf",
            "url": "https://example.com/paper",
        },
    }

    with patch("papergazer.sources.unpaywall.httpx.AsyncClient") as mock_client:
        mock_response = Mock()
        mock_response.json = Mock(return_value=mock_response_data)
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_client_instance

        result = await best_oa("10.1038/test", "test@example.com")

        assert isinstance(result, UnpaywallResponse)
        assert result.is_oa is True
        assert result.pdf_url == "https://example.com/paper.pdf"
        assert result.landing_url == "https://example.com/paper"


@pytest.mark.asyncio
async def test_best_oa_not_oa():
    """测试非 OA 论文"""
    mock_response_data = {"is_oa": False}

    with patch("papergazer.sources.unpaywall.httpx.AsyncClient") as mock_client:
        mock_response = Mock()
        mock_response.json = Mock(return_value=mock_response_data)
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_client_instance

        result = await best_oa("10.1038/test", "test@example.com")

        assert isinstance(result, UnpaywallResponse)
        assert result.is_oa is False
        assert result.pdf_url is None

