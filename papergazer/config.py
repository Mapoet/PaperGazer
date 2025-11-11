"""
配置管理模块：使用 pydantic-settings 加载配置
所有配置从 YAML 文件读取
"""

import yaml
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ArxivConfig(BaseSettings):
    """arXiv 配置"""

    categories: List[str] = Field(
        default=["eess.SP", "physics.space-ph"],
        description="关注的 arXiv 分类",
    )
    max_results: int = Field(default=100, description="每次查询最大结果数")
    delay_seconds: float = Field(default=3.0, description="请求间隔（秒）")


class JournalsConfig(BaseSettings):
    """期刊配置"""

    issn: dict[str, List[str]] = Field(
        default_factory=lambda: {
            "nature": ["0028-0836", "1476-4687"],
            "science": ["0036-8075", "1095-9203"],
            "cell": ["0092-8674", "1097-4172"],
        },
        description="期刊 ISSN 列表（支持 print 和 online ISSN）",
    )


class StoreConfig(BaseSettings):
    """存储配置"""

    root: str = Field(default="./data", description="数据根目录")
    db_path: str = Field(default="./data/db.sqlite3", description="数据库路径")
    papers_dir: str = Field(default="./data/papers", description="论文文件目录")


class ScheduleConfig(BaseSettings):
    """调度配置"""

    enabled: bool = Field(default=True, description="是否启用定时任务")
    timezone: str = Field(default="Asia/Singapore", description="时区")
    hour: int = Field(default=7, description="每日执行时间（小时）")
    minute: int = Field(default=0, description="每日执行时间（分钟）")


class LoggingConfig(BaseSettings):
    """日志配置"""

    level: str = Field(default="INFO", description="日志级别")
    format: str = Field(default="json", description="日志格式：json 或 text")
    file: str = Field(default="./data/papergazer.log", description="日志文件路径")


class GrobidConfig(BaseSettings):
    """GROBID 配置"""

    enabled: bool = Field(default=False, description="是否启用 GROBID 服务")
    base_url: str = Field(
        default="http://localhost:8070",
        description="GROBID 服务基础地址，例如 http://localhost:8070",
    )
    timeout_seconds: float = Field(default=60.0, description="请求超时时间（秒）")
    output_dir: Optional[str] = Field(
        default=None,
        description="TEI 输出目录（为空则与 PDF 同目录或使用默认数据目录）",
    )
    process_fulltext_path: str = Field(
        default="/api/processFulltextDocument",
        description="GROBID fulltext 接口路径",
    )
    tei_coordinates: bool = Field(
        default=False, description="是否请求返回坐标信息（teicoordinates 参数）"
    )


class RetryConfig(BaseSettings):
    """重试配置"""

    max_attempts: int = Field(default=3, description="最大重试次数")
    initial_delay: float = Field(default=1.0, description="初始延迟（秒）")
    max_delay: float = Field(default=60.0, description="最大延迟（秒）")
    exponential_base: float = Field(default=2.0, description="指数退避基数")


class FigureExtractionConfig(BaseSettings):
    """图表抽取配置"""

    enabled: bool = Field(default=False, description="是否启用图表抽取流程")
    prefer_pdf: bool = Field(default=True, description="优先使用 PDF 抽取，否则回退到 TEI")
    pdffigures2_path: Optional[str] = Field(
        default=None, description="pdffigures2 可执行文件路径（若为空则仅使用 TEI ）"
    )
    table_transformer_model: Optional[str] = Field(
        default=None, description="table-transformer 模型权重或服务地址"
    )
    max_per_paper: int = Field(
        default=20, description="每篇论文最多保存的图表数量（分别计算）"
    )
    cache_dir: str = Field(
        default="./data/cache/figures",
        description="临时缓存目录（用于外部工具输出）",
    )


class OrcidConfig(BaseSettings):
    """ORCID 搜索配置"""

    enabled: bool = Field(default=False, description="是否启用 ORCID 匹配")
    base_url: str = Field(
        default="https://pub.orcid.org/v3.0/expanded-search",
        description="ORCID Expanded Search API 基础地址",
    )
    token: Optional[str] = Field(
        default=None, description="ORCID API Token（可选，若未提供则使用匿名速率限制）"
    )
    max_results: int = Field(default=5, description="每次匹配返回的最大结果数")
    min_score: float = Field(default=0.6, description="接受匹配的最低相似度")


class RorConfig(BaseSettings):
    """ROR 搜索配置"""

    enabled: bool = Field(default=False, description="是否启用 ROR 匹配")
    base_url: str = Field(
        default="https://api.ror.org/v2/organizations",
        description="ROR v2 搜索 API 地址",
    )
    max_results: int = Field(default=5, description="每次匹配返回的最大结果数")
    min_score: float = Field(default=0.75, description="接受匹配的最低得分")


class IdentityConfig(BaseSettings):
    """作者/机构身份识别配置"""

    cache_dir: str = Field(
        default="./data/cache/identity", description="本地缓存目录，避免重复请求"
    )
    orcid: OrcidConfig = Field(default_factory=OrcidConfig)
    ror: RorConfig = Field(default_factory=RorConfig)


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        # 不再使用 .env 文件，所有配置从 YAML 文件读取
        case_sensitive=False,
    )

    mailto: str = Field(
        default="",
        description="联系邮箱（用于 Crossref/Unpaywall API），从 YAML 配置文件读取",
    )
    # 预留API key字段（如果未来需要）
    api_key: Optional[str] = Field(
        default=None,
        description="API密钥（如果未来需要），从 YAML 配置文件读取",
    )
    arxiv: ArxivConfig = Field(default_factory=ArxivConfig)
    journals: JournalsConfig = Field(default_factory=JournalsConfig)
    store: StoreConfig = Field(default_factory=StoreConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    grobid: GrobidConfig = Field(default_factory=GrobidConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    figures: FigureExtractionConfig = Field(default_factory=FigureExtractionConfig)
    identity: IdentityConfig = Field(default_factory=IdentityConfig)


def load_config(config_path: str | Path | None = None) -> Settings:
    """
    加载配置文件
    所有配置从 YAML 文件读取

    Args:
        config_path: 配置文件路径，如果为 None 则使用默认路径

    Returns:
        Settings 实例

    Raises:
        FileNotFoundError: 配置文件不存在
        ValueError: 邮箱未设置
    """
    if config_path is None:
        config_path = Path("configs/config.yaml")
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(
            f"配置文件不存在: {config_path}\n"
            f"请复制 configs/config.yaml.example 为 {config_path} 并修改相应配置"
        )

    # 手动加载 YAML 文件
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f) or {}

    # 创建配置实例（所有配置从 YAML 文件读取）
    settings = Settings(**config_data)

    # 验证邮箱是否设置
    if not settings.mailto:
        raise ValueError(
            "邮箱未设置！请在配置文件中设置 mailto 字段。\n"
            f"配置文件路径: {config_path}\n"
            "参考示例: configs/config.yaml.example"
        )

    return settings

