"""
日志配置工具
"""

import json
import logging
import sys
from pathlib import Path

from papergazer.config import LoggingConfig


def setup_logging(config: LoggingConfig) -> None:
    """
    配置日志系统

    Args:
        config: 日志配置
    """
    # 创建日志目录
    log_file = Path(config.file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # 配置日志格式
    formatter: logging.Formatter
    if config.format == "json":
        # JSON 格式日志
        class JSONFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                log_data = {
                    "timestamp": self.formatTime(record, self.datefmt),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
                if record.exc_info:
                    log_data["exception"] = self.formatException(record.exc_info)
                return json.dumps(log_data)

        formatter = JSONFormatter()
    else:
        # 文本格式日志
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level.upper()))

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 文件处理器
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
