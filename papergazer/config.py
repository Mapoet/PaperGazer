"""
配置管理模块：使用 pydantic-settings 加载配置
支持从环境变量读取敏感信息（邮箱、API key等）
"""

import os
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


class CNSConfig(BaseSettings):
    """CNS 期刊配置"""

    issn: dict[str, List[str]] = Field(
        default_factory=lambda: {
            "nature": ["0028-0836", "1476-4687"],
            "science": ["0036-8075", "1095-9203"],
            "cell": ["0092-8674", "1097-4172"],
        },
        description="CNS 期刊 ISSN 列表",
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


class RetryConfig(BaseSettings):
    """重试配置"""

    max_attempts: int = Field(default=3, description="最大重试次数")
    initial_delay: float = Field(default=1.0, description="初始延迟（秒）")
    max_delay: float = Field(default=60.0, description="最大延迟（秒）")
    exponential_base: float = Field(default=2.0, description="指数退避基数")


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="PAPERGAZER_",  # 环境变量前缀
    )

    mailto: str = Field(
        default="",
        description="联系邮箱（用于 Crossref/Unpaywall API），可从环境变量 PAPERGAZER_MAILTO 读取",
    )
    # 预留API key字段（如果未来需要）
    api_key: Optional[str] = Field(
        default=None,
        description="API密钥（如果未来需要），可从环境变量 PAPERGAZER_API_KEY 读取",
    )
    arxiv: ArxivConfig = Field(default_factory=ArxivConfig)
    cns: CNSConfig = Field(default_factory=CNSConfig)
    store: StoreConfig = Field(default_factory=StoreConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)


def load_config(config_path: str | Path | None = None) -> Settings:
    """
    加载配置文件
    优先从环境变量读取敏感信息（邮箱、API key等）

    Args:
        config_path: 配置文件路径，如果为 None 则使用默认路径

    Returns:
        Settings 实例
    """
    if config_path is None:
        config_path = Path("configs/config.yaml")
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    # 手动加载 YAML 文件
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f) or {}

    # 优先从环境变量读取敏感信息（环境变量优先级最高）
    # 支持两种环境变量格式：
    # 1. PAPERGAZER_MAILTO (带前缀，pydantic-settings自动处理)
    # 2. MAILTO (不带前缀，手动处理)
    mailto_from_env = os.getenv("MAILTO") or os.getenv("PAPERGAZER_MAILTO")
    
    # API key（如果未来需要）
    api_key_from_env = os.getenv("API_KEY") or os.getenv("PAPERGAZER_API_KEY")

    # 创建配置实例（pydantic-settings会自动从.env文件读取）
    settings = Settings(**config_data)
    
    # 环境变量优先级最高，覆盖配置文件中的值
    if mailto_from_env:
        settings.mailto = mailto_from_env
    
    if api_key_from_env:
        settings.api_key = api_key_from_env

    # 验证邮箱是否设置
    if not settings.mailto:
        raise ValueError(
            "邮箱未设置！请通过以下方式之一设置：\n"
            "1. 在配置文件中设置 mailto\n"
            "2. 设置环境变量 MAILTO 或 PAPERGAZER_MAILTO"
        )

    return settings

