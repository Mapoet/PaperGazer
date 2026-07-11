"""
按需抓取 Pipeline：优先级链（arXiv → Unpaywall → Europe PMC → Crossref）
"""

import logging
import re
from pathlib import Path
from typing import Optional, Tuple, Union

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from papergazer.config import Settings
from papergazer.utils.http_client import async_client
from papergazer.exceptions import (
    FetchError,
    ArxivAPIError,
    UnpaywallAPIError,
    EuropePMCAPIError,
    CrossrefAPIError,
    FileStorageError,
)
from papergazer.models import PaperMetadata
from papergazer.sources import best_oa, crossref, doi_to_pmcid, fetch_fulltext_xml
from papergazer.store.db import get_session, upsert_paper
from papergazer.store.files import save_pdf, save_xml

logger = logging.getLogger(__name__)


def normalize_identifier(identifier: str) -> Tuple[str, str]:
    """
    规范化标识符，判断类型

    Args:
        identifier: DOI 或 arXiv id

    Returns:
        (类型, 规范化后的标识符)
        类型：'arxiv' 或 'doi'
    """
    identifier = identifier.strip()

    # 检查是否是 arXiv id
    if identifier.lower().startswith("arxiv:"):
        arxiv_id = identifier.split(":", 1)[1].strip()
        return "arxiv", arxiv_id
    elif "/" not in identifier and re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", identifier):
        # 格式如 2501.01234 或 2501.01234v1
        return "arxiv", identifier

    # 否则认为是 DOI
    # 去除协议前缀
    doi = identifier.replace("https://", "").replace("http://", "")
    doi = doi.replace("doi.org/", "").replace("dx.doi.org/", "")
    doi = doi.lower().strip()

    return "doi", doi


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
async def download_file(url: str, timeout: float = 60.0, max_redirect_depth: int = 5) -> bytes:
    """
    下载文件

    Args:
        url: 文件 URL
        timeout: 超时时间（秒）
        max_redirect_depth: 最大重定向深度（防止无限循环）

    Returns:
        文件内容（bytes）

    Raises:
        FetchError: 下载失败
    """
    default_headers = {
        "User-Agent": "Mozilla/5.0",
    }

    async def _perform_request(client: httpx.AsyncClient, target_url: str) -> httpx.Response:
        return await client.get(target_url, follow_redirects=True)

    try:
        async with async_client(
            timeout=timeout,
            follow_redirects=True,
            max_redirects=10,
            headers=default_headers,
        ) as client:
            response = await _perform_request(client, url)
            
            # 如果最终响应仍然是重定向状态码，说明重定向链没有成功完成，需要手动处理
            if response.status_code in (301, 302, 303, 307, 308):
                if max_redirect_depth <= 0:
                    raise FetchError(f"重定向深度超过限制: {url}")
                
                redirect_location = response.headers.get("Location")
                if not redirect_location:
                    raise FetchError(f"重定向响应但缺少 Location 头: {url}")
                
                # 构建完整的重定向 URL
                from urllib.parse import urljoin, urlparse
                if redirect_location.startswith("/"):
                    # 相对路径，使用原始 URL 的 scheme 和 netloc
                    parsed = urlparse(url)
                    redirect_url = f"{parsed.scheme}://{parsed.netloc}{redirect_location}"
                elif redirect_location.startswith("http://") or redirect_location.startswith("https://"):
                    # 绝对 URL
                    redirect_url = redirect_location
                else:
                    # 相对路径（相对于当前路径）
                    redirect_url = urljoin(url, redirect_location)
                
                logger.info(f"检测到重定向 {response.status_code}: {url} -> {redirect_url}")
                # 手动跟随重定向，递归调用（但限制递归深度）
                return await download_file(redirect_url, timeout, max_redirect_depth - 1)
            
            # 针对部分出版社（如 MDPI）需要先访问落地页获取 Cookie，再访问 PDF
            if response.status_code == 403 and "mdpi.com" in url:
                from urllib.parse import urlsplit

                parsed = urlsplit(url)
                pdf_path = parsed.path
                landing_path = pdf_path.split("/pdf")[0]
                landing_url = f"{parsed.scheme}://{parsed.netloc}{landing_path}"
                download_url = f"{parsed.scheme}://{parsed.netloc}{pdf_path}?download=1"

                logger.info("MDPI 返回 403，尝试先访问落地页获取授权 Cookie")
                await client.get(landing_url)
                response = await _perform_request(client, download_url)

            response.raise_for_status()
            return response.content
    except httpx.HTTPStatusError as e:
        raise FetchError(f"HTTP 错误 {e.response.status_code}: {url}") from e
    except httpx.RequestError as e:
        raise FetchError(f"请求错误: {url}") from e
    except Exception as e:
        raise FetchError(f"下载文件失败: {url}") from e


async def fetch_arxiv_pdf(arxiv_id: str, papers_dir: Path) -> Tuple[Optional[Path], Optional[str]]:
    """
    抓取 arXiv PDF

    Args:
        arxiv_id: arXiv ID
        papers_dir: 论文文件目录

    Returns:
        (PDF 路径, 文件哈希) 或 (None, None) 如果失败

    Raises:
        ArxivAPIError: arXiv API 错误
        FileStorageError: 文件存储错误
    """
    try:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        logger.info(f"下载 arXiv PDF: {pdf_url}")

        pdf_content = await download_file(pdf_url)

        # 创建临时元数据用于路径生成
        temp_metadata = PaperMetadata(
            source="arxiv",
            identifier=arxiv_id,
            title="",
            published_date=None,
        )

        try:
            pdf_path, file_hash = save_pdf(papers_dir, temp_metadata, pdf_content)
            logger.info(f"arXiv PDF 保存成功: {pdf_path}")
            return pdf_path, file_hash
        except Exception as e:
            raise FileStorageError(f"保存 PDF 文件失败: {arxiv_id}") from e

    except FetchError as e:
        raise ArxivAPIError(f"下载 arXiv PDF 失败: {arxiv_id}") from e
    except Exception as e:
        logger.error(f"抓取 arXiv PDF 失败: {e}", exc_info=True)
        raise ArxivAPIError(f"抓取 arXiv PDF 失败: {arxiv_id}") from e


async def fetch_by_identifier(
    identifier: str,
    config: Settings,
) -> dict:
    """
    按标识符抓取论文（优先级链）

    优先级：arXiv → Unpaywall → Europe PMC → Crossref 摘要

    Args:
        identifier: DOI 或 arXiv id
        config: 应用配置

    Returns:
        抓取结果字典，包含：
        - success: bool
        - source: str (arxiv/unpaywall/eupmc/crossref)
        - pdf_path: str | None
        - xml_path: str | None
        - abstract_only: bool
        - error: str | None
    """
    logger.info(f"开始抓取: {identifier}")

    id_type, normalized_id = normalize_identifier(identifier)
    papers_dir = Path(config.store.papers_dir)
    session = get_session()

    try:
        # 1. 如果是 arXiv id，直接下载 PDF
        if id_type == "arxiv":
            pdf_path, file_hash = await fetch_arxiv_pdf(normalized_id, papers_dir)
            if pdf_path:
                # 更新数据库（创建临时元数据）
                metadata = PaperMetadata(
                    source="arxiv",
                    identifier=normalized_id,
                    title=f"arXiv:{normalized_id}",
                    published_date=None,
                )
                item = upsert_paper(session, metadata)
                item.pdf_path = str(pdf_path)
                item.hash = file_hash
                item.is_oa = True
                item.oa_source = "arxiv"
                session.commit()

                return {
                    "success": True,
                    "source": "arxiv",
                    "pdf_path": str(pdf_path),
                    "xml_path": None,
                    "abstract_only": False,
                    "error": None,
                }

        # 2. 尝试 Unpaywall
        if id_type == "doi":
            logger.info(f"查询 Unpaywall: {normalized_id}")
            oa_info = await best_oa(normalized_id, config.mailto)

            if oa_info.is_oa and oa_info.pdf_url:
                try:
                    logger.info(f"下载 Unpaywall PDF: {oa_info.pdf_url}")
                    pdf_content = await download_file(oa_info.pdf_url)

                    # 获取元数据（从 Crossref）
                    work = await crossref.fetch_crossref_by_doi(normalized_id, config.mailto)
                    if work:
                        metadata = work.to_metadata()
                    else:
                        # 创建临时元数据
                        metadata = PaperMetadata(
                            source="crossref",
                            identifier=normalized_id,
                            title="",
                            doi=normalized_id,
                        )

                    pdf_path, file_hash = save_pdf(papers_dir, metadata, pdf_content)

                    # 更新数据库
                    item = upsert_paper(session, metadata)
                    item.pdf_path = str(pdf_path)
                    item.hash = file_hash
                    item.is_oa = True
                    item.oa_source = "unpaywall"
                    item.oa_pdf_url = oa_info.pdf_url
                    session.commit()

                    return {
                        "success": True,
                        "source": "unpaywall",
                        "pdf_path": str(pdf_path),
                        "xml_path": None,
                        "abstract_only": False,
                        "error": None,
                    }

                except Exception as e:
                    logger.warning(f"Unpaywall PDF 下载失败: {e}")

            # 3. 尝试 Europe PMC
            logger.info(f"查询 Europe PMC: {normalized_id}")
            pmcid = await doi_to_pmcid(normalized_id)

            if pmcid:
                try:
                    logger.info(f"下载 Europe PMC XML: {pmcid}")
                    xml_content = await fetch_fulltext_xml(pmcid)

                    # 获取元数据
                    work = await crossref.fetch_crossref_by_doi(normalized_id, config.mailto)
                    if work:
                        metadata = work.to_metadata()
                    else:
                        metadata = PaperMetadata(
                            source="crossref",
                            identifier=normalized_id,
                            title="",
                            doi=normalized_id,
                        )

                    xml_path, file_hash = save_xml(papers_dir, metadata, xml_content)

                    # 更新数据库
                    item = upsert_paper(session, metadata)
                    item.pdf_path = None  # XML 不是 PDF
                    item.hash = file_hash
                    item.is_oa = True
                    item.oa_source = "eupmc"
                    session.commit()

                    return {
                        "success": True,
                        "source": "eupmc",
                        "pdf_path": None,
                        "xml_path": str(xml_path),
                        "abstract_only": False,
                        "error": None,
                    }

                except Exception as e:
                    logger.warning(f"Europe PMC XML 下载失败: {e}")

            # 4. 回退到 Crossref 摘要
            logger.info(f"回退到 Crossref 摘要: {normalized_id}")
            work = await crossref.fetch_crossref_by_doi(normalized_id, config.mailto)

            if work:
                metadata = work.to_metadata()
                item = upsert_paper(session, metadata)
                session.commit()

                return {
                    "success": True,
                    "source": "crossref",
                    "pdf_path": None,
                    "xml_path": None,
                    "abstract_only": True,
                    "error": None,
                }

        # 所有方法都失败
        error_msg = f"无法抓取 {identifier}：所有方法均失败"
        logger.error(error_msg)
        return {
            "success": False,
            "source": None,
            "pdf_path": None,
            "xml_path": None,
            "abstract_only": False,
            "error": error_msg,
        }

    except (ArxivAPIError, UnpaywallAPIError, EuropePMCAPIError, CrossrefAPIError, FileStorageError) as e:
        session.rollback()
        error_msg = f"抓取失败: {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "source": None,
            "pdf_path": None,
            "xml_path": None,
            "abstract_only": False,
            "error": error_msg,
        }
    except Exception as e:
        session.rollback()
        error_msg = f"未知错误: {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "source": None,
            "pdf_path": None,
            "xml_path": None,
            "abstract_only": False,
            "error": error_msg,
        }
    finally:
        session.close()

