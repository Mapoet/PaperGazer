"""
TEI 解析工具：从 TEI XML 中抽取图表信息
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from lxml import etree

logger = logging.getLogger(__name__)


def _load_tei(path: Path) -> etree._Element:
    parser = etree.XMLParser(remove_blank_text=True, recover=True)
    with path.open("rb") as fh:
        return etree.parse(fh, parser).getroot()


def extract_figures_from_tei(tei_path: Path) -> list[dict[str, Any]]:
    """
    从 TEI XML 中抽取图信息

    Args:
        tei_path: TEI 文件路径

    Returns:
        图信息列表
    """
    root = _load_tei(tei_path)
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}
    figures: list[dict[str, Any]] = []

    for idx, fig in enumerate(root.xpath(".//tei:figure", namespaces=ns)):
        figure_id = fig.get("{http://www.w3.org/XML/1998/namespace}id") or fig.get("id")
        head_el = fig.find("tei:head", namespaces=ns)
        desc_el = fig.find("tei:figDesc", namespaces=ns)
        graphic_el = fig.find("tei:graphic", namespaces=ns)

        caption = (head_el.text or "").strip() if head_el is not None else ""
        description = (desc_el.text or "").strip() if desc_el is not None else ""
        graphic_url = graphic_el.get("url") if graphic_el is not None else None

        figures.append(
            {
                "sequence": idx + 1,
                "id": figure_id,
                "caption": caption,
                "description": description,
                "graphic": graphic_url,
            }
        )

    return figures


def extract_tables_from_tei(tei_path: Path) -> list[dict[str, Any]]:
    """
    从 TEI XML 中抽取表格信息（结构化为文本）

    Args:
        tei_path: TEI 文件路径

    Returns:
        表格信息列表
    """
    root = _load_tei(tei_path)
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}
    tables: list[dict[str, Any]] = []

    for idx, table in enumerate(root.xpath(".//tei:table", namespaces=ns)):
        table_id = table.get("{http://www.w3.org/XML/1998/namespace}id") or table.get("id")
        head_el = table.find("tei:head", namespaces=ns)
        caption = (head_el.text or "").strip() if head_el is not None else ""

        rows = []
        for row in table.findall(".//tei:row", namespaces=ns):
            cells = [
                ("".join(cell.itertext())).strip()
                for cell in row.findall("tei:cell", namespaces=ns)
            ]
            if cells:
                rows.append(cells)

        tables.append(
            {
                "sequence": idx + 1,
                "id": table_id,
                "caption": caption,
                "rows": rows,
            }
        )

    return tables
