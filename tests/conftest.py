"""
pytest 配置与共享 fixtures
"""

import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_dir():
    """创建临时目录用于测试"""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp)


@pytest.fixture
def sample_config():
    """示例配置数据"""
    return {
        "mailto": "test@example.com",
        "arxiv": {
            "categories": ["eess.SP"],
            "max_results": 10,
        },
        "cns": {
            "issn": {
                "nature": ["0028-0836", "1476-4687"],
            },
        },
        "store": {
            "root": "./data",
            "db_path": "./data/test.db",
        },
    }

