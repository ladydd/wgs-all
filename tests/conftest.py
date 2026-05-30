"""
pytest 配置和 fixtures
"""

import pytest
from pathlib import Path


@pytest.fixture
def test_data_dir():
    """测试数据目录"""
    return Path(__file__).parent / "data"


@pytest.fixture
def sample_bam(test_data_dir):
    """示例 BAM 文件路径"""
    return test_data_dir / "sample.bam"
