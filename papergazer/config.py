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
    cns: CNSConfig = Field(default_factory=CNSConfig)
    store: StoreConfig = Field(default_factory=StoreConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)


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

