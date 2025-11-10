"""
文件存储模块测试
"""

import pytest
from pathlib import Path
from datetime import date

from papergazer.store.files import (
    sanitize_identifier,
    get_paper_path,
    compute_file_hash,
    save_pdf,
    save_xml,
    file_exists,
)
from papergazer.models import PaperMetadata


def test_sanitize_identifier():
    """测试标识符规范化"""
    # DOI - 验证特殊字符被替换
    result1 = sanitize_identifier("10.1038/s41586-024-xxxx-x")
    assert "10" in result1 and "1038" in result1
    assert "/" not in result1  # 斜杠应被替换
    result2 = sanitize_identifier("https://doi.org/10.1038/test")
    assert "10" in result2 and "1038" in result2
    assert "https" not in result2  # 协议应被去除

    # arXiv - 验证版本号被去除（点号保留，因为匹配 \w）
    result3 = sanitize_identifier("2501.01234")
    assert "2501" in result3 and "01234" in result3
    result4 = sanitize_identifier("2501.01234v1")
    assert "v1" not in result4  # 版本号应被去除
    assert "2501" in result4 and "01234" in result4
    result5 = sanitize_identifier("arxiv:2501.01234")
    # arxiv: 前缀会被替换为下划线，但冒号后的内容保留
    assert "2501" in result5 and "01234" in result5
    # 验证冒号被替换
    assert ":" not in result5


def test_get_paper_path(temp_papers_dir):
    """测试获取论文路径"""
    from datetime import date

    metadata = PaperMetadata(
        source="arxiv",
        identifier="2501.00001",
        title="Test",
        published_date=None,
    )

    path = get_paper_path(temp_papers_dir, metadata, "paper.pdf")
    # 如果没有日期，应该使用 "unknown" 或当前年份
    assert path.name == "paper.pdf"
    assert "unknown" in str(path) or str(date.today().year) in str(path)

    metadata.published_date = date(2025, 1, 1)
    path = get_paper_path(temp_papers_dir, metadata, "paper.pdf")
    assert "2025" in str(path)
    assert path.name == "paper.pdf"


def test_compute_file_hash(temp_dir):
    """测试文件哈希计算"""
    test_file = temp_dir / "test.txt"
    test_file.write_text("test content")

    hash_value = compute_file_hash(test_file)

    assert len(hash_value) == 64  # SHA256 十六进制长度
    assert isinstance(hash_value, str)

    # 验证哈希一致性
    hash_value2 = compute_file_hash(test_file)
    assert hash_value == hash_value2


def test_save_pdf(temp_papers_dir):
    """测试保存 PDF"""
    metadata = PaperMetadata(
        source="arxiv",
        identifier="2501.00001",
        title="Test",
        published_date=date(2025, 1, 1),
    )

    pdf_content = b"PDF content test"

    pdf_path, file_hash = save_pdf(temp_papers_dir, metadata, pdf_content)

    assert pdf_path.exists()
    assert pdf_path.read_bytes() == pdf_content
    assert file_hash == compute_file_hash(pdf_path)
    assert len(file_hash) == 64


def test_save_pdf_no_overwrite(temp_papers_dir):
    """测试不覆盖已存在的 PDF"""
    metadata = PaperMetadata(
        source="arxiv",
        identifier="2501.00001",
        title="Test",
        published_date=date(2025, 1, 1),
    )

    pdf_content1 = b"Original content"
    pdf_path1, hash1 = save_pdf(temp_papers_dir, metadata, pdf_content1)

    pdf_content2 = b"New content"
    pdf_path2, hash2 = save_pdf(temp_papers_dir, metadata, pdf_content2, overwrite=False)

    assert pdf_path1 == pdf_path2
    assert pdf_path2.read_bytes() == pdf_content1  # 保持原内容
    assert hash1 == hash2


def test_save_xml(temp_papers_dir):
    """测试保存 XML"""
    metadata = PaperMetadata(
        source="crossref",
        identifier="10.1038/test",
        title="Test",
        published_date=date(2025, 1, 1),
    )

    xml_content = b"<?xml version='1.0'?><article>Test</article>"

    xml_path, file_hash = save_xml(temp_papers_dir, metadata, xml_content)

    assert xml_path.exists()
    assert xml_path.read_bytes() == xml_content
    assert file_hash == compute_file_hash(xml_path)


def test_file_exists(temp_papers_dir):
    """测试文件存在性检查"""
    metadata = PaperMetadata(
        source="arxiv",
        identifier="2501.00001",
        title="Test",
        published_date=date(2025, 1, 1),
    )

    assert not file_exists(temp_papers_dir, metadata, "paper.pdf")

    pdf_content = b"test"
    save_pdf(temp_papers_dir, metadata, pdf_content)

    assert file_exists(temp_papers_dir, metadata, "paper.pdf")

