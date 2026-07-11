"""
文件存储管理：PDF/XML 文件存储路径规范与去重
"""

import hashlib
import re
from pathlib import Path

from papergazer.models import PaperMetadata


def sanitize_identifier(identifier: str) -> str:
    """
    规范化标识符（用于文件路径）

    Args:
        identifier: DOI 或 arXiv id

    Returns:
        规范化后的标识符
    """
    # 去除协议前缀
    identifier = identifier.replace("https://", "").replace("http://", "")
    identifier = (
        identifier.replace("doi.org/", "")
        .replace("arxiv.org/abs/", "")
        .replace("arxiv.org/pdf/", "")
    )

    # 去除版本号（arXiv）
    identifier = re.sub(r"v\d+$", "", identifier)

    # 替换特殊字符为下划线
    identifier = re.sub(r"[^\w\-.]", "_", identifier)

    # 去除多余下划线
    identifier = re.sub(r"_+", "_", identifier)

    return identifier.strip("_")


def get_paper_path(
    papers_dir: str | Path,
    metadata: PaperMetadata,
    filename: str = "paper.pdf",
) -> Path:
    """
    获取论文文件存储路径

    路径格式：{papers_dir}/{year}/{sanitized_id}/{filename}

    Args:
        papers_dir: 论文文件根目录
        metadata: 论文元数据
        filename: 文件名（如 paper.pdf, fulltext.xml）

    Returns:
        文件路径
    """
    papers_dir = Path(papers_dir)
    year = metadata.published_date.year if metadata.published_date else "unknown"
    sanitized_id = sanitize_identifier(metadata.identifier)

    return papers_dir / str(year) / sanitized_id / filename


def compute_file_hash(file_path: str | Path) -> str:
    """
    计算文件 SHA256 哈希

    Args:
        file_path: 文件路径

    Returns:
        SHA256 哈希值（十六进制字符串）
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def save_pdf(
    papers_dir: str | Path,
    metadata: PaperMetadata,
    pdf_content: bytes,
    overwrite: bool = False,
) -> tuple[Path, str]:
    """
    保存 PDF 文件

    Args:
        papers_dir: 论文文件根目录
        metadata: 论文元数据
        pdf_content: PDF 内容（bytes）
        overwrite: 是否覆盖已存在的文件

    Returns:
        (文件路径, 文件哈希)
    """
    pdf_path = get_paper_path(papers_dir, metadata, "paper.pdf")

    # 检查文件是否已存在
    if pdf_path.exists() and not overwrite:
        # 返回现有文件路径和哈希
        file_hash = compute_file_hash(pdf_path)
        return pdf_path, file_hash

    # 创建目录
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    # 保存文件
    pdf_path.write_bytes(pdf_content)

    # 计算哈希
    file_hash = compute_file_hash(pdf_path)

    return pdf_path, file_hash


def save_xml(
    papers_dir: str | Path,
    metadata: PaperMetadata,
    xml_content: bytes,
    overwrite: bool = False,
) -> tuple[Path, str]:
    """
    保存 XML 文件

    Args:
        papers_dir: 论文文件根目录
        metadata: 论文元数据
        xml_content: XML 内容（bytes）
        overwrite: 是否覆盖已存在的文件

    Returns:
        (文件路径, 文件哈希)
    """
    xml_path = get_paper_path(papers_dir, metadata, "fulltext.xml")

    # 检查文件是否已存在
    if xml_path.exists() and not overwrite:
        # 返回现有文件路径和哈希
        file_hash = compute_file_hash(xml_path)
        return xml_path, file_hash

    # 创建目录
    xml_path.parent.mkdir(parents=True, exist_ok=True)

    # 保存文件
    xml_path.write_bytes(xml_content)

    # 计算哈希
    file_hash = compute_file_hash(xml_path)

    return xml_path, file_hash


def file_exists(
    papers_dir: str | Path, metadata: PaperMetadata, filename: str = "paper.pdf"
) -> bool:
    """
    检查文件是否存在

    Args:
        papers_dir: 论文文件根目录
        metadata: 论文元数据
        filename: 文件名

    Returns:
        文件是否存在
    """
    file_path = get_paper_path(papers_dir, metadata, filename)
    return file_path.exists()
