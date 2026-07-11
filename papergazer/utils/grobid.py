"""
GROBID 工具封装：支持将 PDF、纯文本或已有 XML 转换为 TEI
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

import httpx
from xml.sax.saxutils import escape

from papergazer.config import Settings
from papergazer.utils.http_client import async_client

logger = logging.getLogger(__name__)


class GrobidError(RuntimeError):
    """GROBID 相关错误"""


class GrobidDisabledError(GrobidError):
    """当 GROBID 功能未启用但仍尝试调用时抛出"""


@dataclass
class GrobidResult:
    """GROBID 处理结果"""

    tei_xml: str
    tei_path: Optional[Path]
    source: str  # grobid | text | xml
    metadata: Optional[Dict[str, str]] = None
    error: Optional[str] = None


async def process_fulltext_document(
    config: Settings,
    pdf_path: Optional[Path] = None,
    *,
    text: Optional[str] = None,
    xml: Optional[str] = None,
    document_id: Optional[str] = None,
    output_dir: Optional[Path] = None,
    save: bool = True,
) -> GrobidResult:
    """
    将 PDF、纯文本或 XML 转换为 TEI

    Args:
        config: 全局配置
        pdf_path: PDF 文件路径（与 text/xml 互斥）
        text: 纯文本内容（与 pdf_path/xml 互斥）
        xml: 已有 XML 内容（与 pdf_path/text 互斥）
        document_id: 文档标识（用于输出文件命名）
        output_dir: 输出目录（默认继承 PDF 目录或配置目录）
        save: 是否保存生成的 TEI 文件

    Returns:
        GrobidResult
    """

    sources = [item is not None for item in (pdf_path, text, xml)]
    if sum(sources) != 1:
        raise ValueError("必须且只能提供 pdf_path、text、xml 中的一种输入")

    if pdf_path:
        tei_xml = await _process_pdf_with_grobid(config, Path(pdf_path))
        source = "grobid"
    elif text is not None:
        tei_xml = _build_tei_from_text(text, document_id=document_id)
        source = "text"
    else:  # xml case
        tei_xml = _normalize_xml(xml or "", document_id=document_id)
        source = "xml"

    tei_path: Optional[Path] = None
    if save:
        tei_path = _save_tei(
            tei_xml,
            config=config,
            pdf_path=Path(pdf_path) if pdf_path else None,
            output_dir=output_dir,
            document_id=document_id,
            source=source,
        )

    return GrobidResult(
        tei_xml=tei_xml,
        tei_path=tei_path,
        source=source,
        metadata={"document_id": document_id} if document_id else None,
    )


async def _process_pdf_with_grobid(config: Settings, pdf_path: Path) -> str:
    if not config.grobid.enabled:
        raise GrobidDisabledError("GROBID 未启用，无法处理 PDF")

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

    base_url = config.grobid.base_url.rstrip("/")
    endpoint = config.grobid.process_fulltext_path.lstrip("/")
    url = f"{base_url}/{endpoint}"

    params = {
        "teiCoordinates": str(config.grobid.tei_coordinates).lower(),
    }

    timeout = httpx.Timeout(config.grobid.timeout_seconds)

    logger.info("调用 GROBID 处理 PDF: %s -> %s", pdf_path.name, url)

    async with async_client(timeout=timeout) as client:
        try:
            with pdf_path.open("rb") as file_obj:
                files = {"input": (pdf_path.name, file_obj, "application/pdf")}
                response = await client.post(url, params=params, files=files)
        except Exception as exc:  # pragma: no cover - 网络错误
            raise GrobidError(f"GROBID 请求失败: {exc}") from exc

    if response.status_code >= 400:
        raise GrobidError(
            f"GROBID 返回错误 {response.status_code}: {response.text.strip()}"
        )

    tei_xml = response.text
    if not tei_xml.strip():
        raise GrobidError("GROBID 返回空的 TEI 内容")

    return tei_xml


def _build_tei_from_text(text: str, document_id: Optional[str] = None) -> str:
    safe_title = escape(document_id or "Untitled")
    paragraphs = _split_paragraphs(text)
    paragraph_xml = "\n".join(f"        <p>{escape(p)}</p>" for p in paragraphs)

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<TEI xmlns="http://www.tei-c.org/ns/1.0">\n'
        "  <teiHeader>\n"
        "    <fileDesc>\n"
        f"      <titleStmt><title>{safe_title}</title></titleStmt>\n"
        "      <publicationStmt><p>Generated from plain text by PaperGazer</p></publicationStmt>\n"
        "      <sourceDesc><p>Plain text input.</p></sourceDesc>\n"
        "    </fileDesc>\n"
        "  </teiHeader>\n"
        "  <text>\n"
        "    <body>\n"
        "      <div type=\"plain-text\">\n"
        f"{paragraph_xml}\n"
        "      </div>\n"
        "    </body>\n"
        "  </text>\n"
        "</TEI>\n"
    )


def _normalize_xml(xml_content: str, document_id: Optional[str] = None) -> str:
    stripped = xml_content.strip()
    if not stripped:
        raise ValueError("提供的 XML 内容为空")

    if "<TEI" in stripped[:200]:
        return stripped

    safe_title = escape(document_id or "XML Document")

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<TEI xmlns="http://www.tei-c.org/ns/1.0">\n'
        "  <teiHeader>\n"
        "    <fileDesc>\n"
        f"      <titleStmt><title>{safe_title}</title></titleStmt>\n"
        "      <publicationStmt><p>Source XML wrapped into TEI by PaperGazer</p></publicationStmt>\n"
        "      <sourceDesc><p>Original XML embedded as CDATA.</p></sourceDesc>\n"
        "    </fileDesc>\n"
        "  </teiHeader>\n"
        "  <text>\n"
        "    <body>\n"
        "      <div type=\"embedded-xml\">\n"
        "        <ab><![CDATA[\n"
        f"{stripped}\n"
        "        ]]></ab>\n"
        "      </div>\n"
        "    </body>\n"
        "  </text>\n"
        "</TEI>\n"
    )


def _split_paragraphs(text: str) -> List[str]:
    lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
    paragraphs: List[str] = []
    buffer: List[str] = []

    for line in lines:
        if not line:
            if buffer:
                paragraphs.append(" ".join(buffer))
                buffer = []
        else:
            buffer.append(line)

    if buffer:
        paragraphs.append(" ".join(buffer))

    return paragraphs or [""]


def _save_tei(
    tei_xml: str,
    *,
    config: Settings,
    pdf_path: Optional[Path],
    output_dir: Optional[Path],
    document_id: Optional[str],
    source: str,
) -> Path:
    base_dir = (
        Path(output_dir)
        if output_dir
        else Path(config.grobid.output_dir)
        if config.grobid.output_dir
        else (pdf_path.parent if pdf_path else Path(config.store.papers_dir))
    )
    base_dir = base_dir.expanduser().resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    filename_base = _sanitize_filename(
        document_id
        or (pdf_path.stem if pdf_path else f"{source}_{uuid.uuid4().hex[:8]}")
    )
    tei_path = base_dir / f"{filename_base}.tei.xml"
    tei_path.write_text(tei_xml, encoding="utf-8")
    logger.info("TEI 文件已保存: %s", tei_path)
    return tei_path


_UNSAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_filename(value: str) -> str:
    value = value.strip()
    sanitized = _UNSAFE_FILENAME_PATTERN.sub("_", value)
    return sanitized or f"doc_{uuid.uuid4().hex[:8]}"


# 便捷同步封装
def process_fulltext_document_sync(
    config: Settings,
    pdf_path: Optional[Path] = None,
    *,
    text: Optional[str] = None,
    xml: Optional[str] = None,
    document_id: Optional[str] = None,
    output_dir: Optional[Path] = None,
    save: bool = True,
) -> GrobidResult:
    """
    同步版本包装，方便在同步上下文中调用
    """

    return asyncio.run(
        process_fulltext_document(
            config,
            pdf_path,
            text=text,
            xml=xml,
            document_id=document_id,
            output_dir=output_dir,
            save=save,
        )
    )


