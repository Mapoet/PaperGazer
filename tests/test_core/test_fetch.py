"""
核心逻辑模块测试 - fetch
"""

from unittest.mock import patch

import pytest

from papergazer.core.fetch import fetch_arxiv_pdf, fetch_by_identifier, normalize_identifier


def test_normalize_identifier_arxiv():
    """测试 arXiv ID 规范化"""
    id_type, normalized = normalize_identifier("arxiv:2501.01234")
    assert id_type == "arxiv"
    assert normalized == "2501.01234"

    id_type, normalized = normalize_identifier("2501.01234")
    assert id_type == "arxiv"
    assert normalized == "2501.01234"


def test_normalize_identifier_doi():
    """测试 DOI 规范化"""
    id_type, normalized = normalize_identifier("10.1038/s41586-024-xxxx-x")
    assert id_type == "doi"
    assert "10.1038" in normalized

    id_type, normalized = normalize_identifier("https://doi.org/10.1038/test")
    assert id_type == "doi"
    assert normalized.startswith("10.1038")


@pytest.mark.asyncio
async def test_fetch_arxiv_pdf(temp_papers_dir):
    """测试抓取 arXiv PDF"""
    with patch("papergazer.core.fetch.download_file") as mock_download:
        mock_download.return_value = b"PDF content"

        pdf_path, file_hash = await fetch_arxiv_pdf("2501.00001", temp_papers_dir)

        assert pdf_path is not None
        assert pdf_path.exists()
        assert pdf_path.read_bytes() == b"PDF content"
        assert file_hash is not None
        assert len(file_hash) == 64


@pytest.mark.asyncio
async def test_fetch_by_identifier_arxiv(settings, temp_db_path, temp_papers_dir):
    """测试按 arXiv ID 抓取"""
    from papergazer.store.db import init_db

    init_db(temp_db_path)

    with (
        patch("papergazer.core.fetch.fetch_arxiv_pdf") as mock_fetch_pdf,
        patch("papergazer.core.fetch.download_file"),
    ):
        mock_pdf_path = temp_papers_dir / "test.pdf"
        mock_pdf_path.parent.mkdir(parents=True, exist_ok=True)
        mock_pdf_path.write_bytes(b"PDF content")
        mock_hash = "test_hash"

        mock_fetch_pdf.return_value = (mock_pdf_path, mock_hash)

        result = await fetch_by_identifier("2501.00001", settings)

        assert result["success"] is True
        assert result["source"] == "arxiv"
        assert result["pdf_path"] is not None
        assert result["abstract_only"] is False


@pytest.mark.asyncio
async def test_fetch_by_identifier_doi_unpaywall(settings, temp_db_path, temp_papers_dir):
    """测试按 DOI 抓取（Unpaywall）"""
    from papergazer.models import UnpaywallResponse
    from papergazer.store.db import init_db

    init_db(temp_db_path)

    with (
        patch("papergazer.core.fetch.best_oa") as mock_oa,
        patch("papergazer.core.fetch.download_file") as mock_download,
        patch("papergazer.core.fetch.crossref.fetch_crossref_by_doi") as mock_crossref,
    ):
        # Mock Unpaywall 返回 OA
        mock_oa.return_value = UnpaywallResponse(
            is_oa=True, best_oa_location={"url_for_pdf": "https://example.com/paper.pdf"}
        )

        # Mock 下载
        mock_download.return_value = b"PDF content"

        # Mock Crossref 元数据
        from papergazer.models import CrossrefWork

        mock_crossref.return_value = CrossrefWork(
            doi="10.1038/test",
            title=["Test Title"],
            author=[{"given": "John", "family": "Doe"}],
        )

        result = await fetch_by_identifier("10.1038/test", settings)

        assert result["success"] is True
        assert result["source"] == "unpaywall"
        assert result["pdf_path"] is not None


@pytest.mark.asyncio
async def test_fetch_by_identifier_fallback(settings, temp_db_path):
    """测试抓取失败回退"""
    from papergazer.store.db import init_db

    init_db(temp_db_path)

    with (
        patch("papergazer.core.fetch.best_oa") as mock_oa,
        patch("papergazer.core.fetch.doi_to_pmcid") as mock_pmcid,
        patch("papergazer.core.fetch.crossref.fetch_crossref_by_doi") as mock_crossref,
    ):
        from papergazer.models import CrossrefWork, UnpaywallResponse

        # 所有 OA 源都失败
        mock_oa.return_value = UnpaywallResponse(is_oa=False)
        mock_pmcid.return_value = None

        # 但 Crossref 有摘要
        mock_crossref.return_value = CrossrefWork(
            doi="10.1038/test",
            title=["Test Title"],
            abstract="Test abstract",
        )

        result = await fetch_by_identifier("10.1038/test", settings)

        assert result["success"] is True
        assert result["source"] == "crossref"
        assert result["abstract_only"] is True
