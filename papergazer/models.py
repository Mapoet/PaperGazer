"""
数据模型：使用 pydantic 定义标准化数据结构
"""

from datetime import date, datetime

from pydantic import BaseModel, Field


class Author(BaseModel):
    """作者模型"""

    name: str
    affiliation: str | None = None


class PaperMetadata(BaseModel):
    """论文元数据模型（标准化）"""

    source: str = Field(description="数据源：arxiv 或 crossref")
    identifier: str = Field(description="arxiv_id 或 doi")
    title: str
    authors: list[Author] = Field(default_factory=list)
    venue: str | None = Field(default=None, description="期刊/会议名称")
    issn_print: str | None = None
    issn_online: str | None = None
    published_date: date | None = None
    updated_date: datetime | None = None
    doi: str | None = None
    url_landing: str | None = None
    abstract: str | None = None


class ArxivEntry(BaseModel):
    """arXiv API 返回的条目"""

    arxiv_id: str
    title: str
    summary: str
    updated: datetime
    published: datetime | None = None
    authors: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    pdf_url: str | None = None
    doi: str | None = None

    def to_metadata(self) -> PaperMetadata:
        """转换为标准化元数据"""
        # 使用主分类作为 venue（arXiv 论文的第一个分类）
        venue = None
        if self.categories:
            primary_category = self.categories[0]
            venue = f"arXiv [{primary_category}]"

        return PaperMetadata(
            source="arxiv",
            identifier=self.arxiv_id,
            title=self.title,
            authors=[Author(name=name) for name in self.authors],
            venue=venue,
            published_date=self.published.date() if self.published else None,
            updated_date=self.updated,
            doi=self.doi,
            url_landing=f"https://arxiv.org/abs/{self.arxiv_id}",
            abstract=self.summary,
        )


class CrossrefWork(BaseModel):
    """Crossref API 返回的工作项"""

    doi: str
    title: list[str] = Field(default_factory=list)
    author: list[dict] = Field(default_factory=list)
    container_title: list[str] = Field(default_factory=list)
    issn: list[str] = Field(default_factory=list)
    issued: dict | None = None
    published_online: dict | None = None
    published_print: dict | None = None
    link: list[dict] = Field(default_factory=list)
    abstract: str | None = None

    def to_metadata(self) -> PaperMetadata:
        """转换为标准化元数据"""
        # 提取标题（取第一个）
        title = self.title[0] if self.title else ""

        # 提取作者
        authors = []
        for author in self.author:
            given = author.get("given", "")
            family = author.get("family", "")
            name = f"{given} {family}".strip()
            if name:
                # 处理 affiliation：可能是列表或字典
                affiliation = None
                if author.get("affiliation"):
                    aff_data = author["affiliation"]
                    if isinstance(aff_data, list) and len(aff_data) > 0:
                        if isinstance(aff_data[0], dict):
                            affiliation = aff_data[0].get("name")
                        elif isinstance(aff_data[0], str):
                            affiliation = aff_data[0]
                    elif isinstance(aff_data, str):
                        affiliation = aff_data
                authors.append(Author(name=name, affiliation=affiliation))

        # 提取日期
        published_date = None
        if self.issued and "date-parts" in self.issued:
            date_parts = self.issued["date-parts"][0]
            if len(date_parts) >= 3:
                published_date = date(date_parts[0], date_parts[1], date_parts[2])

        # 提取 ISSN
        issn_print = None
        issn_online = None
        if self.issn:
            # 通常第一个是 print，第二个是 online
            if len(self.issn) >= 1:
                issn_print = self.issn[0]
            if len(self.issn) >= 2:
                issn_online = self.issn[1]

        # 提取 landing page URL
        url_landing = None
        for link in self.link:
            if (
                link.get("intended-application") == "text-mining"
                or link.get("content-type") == "text/html"
            ):
                url_landing = link.get("URL")
                break

        return PaperMetadata(
            source="crossref",
            identifier=self.doi.lower().strip(),
            title=title,
            authors=authors,
            venue=self.container_title[0] if self.container_title else None,
            issn_print=issn_print,
            issn_online=issn_online,
            published_date=published_date,
            doi=self.doi.lower().strip(),
            url_landing=url_landing,
            abstract=self.abstract,
        )


class UnpaywallResponse(BaseModel):
    """Unpaywall API 响应"""

    is_oa: bool
    best_oa_location: dict | None = None

    @property
    def pdf_url(self) -> str | None:
        """获取 PDF URL"""
        if self.best_oa_location:
            return self.best_oa_location.get("url_for_pdf") or self.best_oa_location.get("url")
        return None

    @property
    def landing_url(self) -> str | None:
        """获取 landing page URL"""
        if self.best_oa_location:
            return self.best_oa_location.get("url")
        return None


class EuropePMCResult(BaseModel):
    """Europe PMC 搜索结果"""

    pmcid: str | None = None
    title: str | None = None
    doi: str | None = None
