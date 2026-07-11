"""
pytest 配置与共享 fixtures
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
import yaml


@pytest.fixture
def temp_dir():
    """创建临时目录用于测试"""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp)


@pytest.fixture
def temp_db_path(temp_dir):
    """临时数据库路径"""
    return temp_dir / "test.db"


@pytest.fixture
def temp_papers_dir(temp_dir):
    """临时论文目录"""
    papers_dir = temp_dir / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)
    return papers_dir


@pytest.fixture
def sample_config(temp_dir, temp_db_path, temp_papers_dir):
    """示例配置"""
    config_data = {
        "mailto": "test@example.com",
        "arxiv": {
            "categories": ["eess.SP", "physics.space-ph"],
            "max_results": 10,
            "delay_seconds": 0.1,  # 测试时使用较短延迟
        },
        "journals": {
            "issn": {
                "nature": ["0028-0836", "1476-4687"],
                "science": ["0036-8075", "1095-9203"],
                "cell": ["0092-8674", "1097-4172"],
            },
        },
        "store": {
            "root": str(temp_dir),
            "db_path": str(temp_db_path),
            "papers_dir": str(temp_papers_dir),
        },
        "schedule": {
            "enabled": False,
            "timezone": "UTC",
            "hour": 0,
            "minute": 0,
        },
        "logging": {
            "level": "DEBUG",
            "format": "text",
            "file": str(temp_dir / "test.log"),
        },
        "retry": {
            "max_attempts": 2,
            "initial_delay": 0.1,
            "max_delay": 1.0,
            "exponential_base": 2.0,
        },
    }
    return config_data


@pytest.fixture
def config_file(temp_dir, sample_config):
    """创建临时配置文件"""
    config_path = temp_dir / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(sample_config, f)
    return config_path


@pytest.fixture
def settings(config_file):
    """Settings 实例"""
    from papergazer.config import load_config

    return load_config(config_file)


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient"""
    client = AsyncMock()
    response = AsyncMock()
    response.text = ""
    response.content = b"test content"
    response.json.return_value = {}
    response.raise_for_status = Mock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client
