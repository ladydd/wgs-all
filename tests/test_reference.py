"""
Reference Manager 测试
"""

import pytest
from pathlib import Path

from app.core.reference import ReferenceManager, ReferenceConfig


class TestReferenceManager:
    """测试 ReferenceManager"""
    
    def test_supported_versions(self):
        """测试支持的版本列表"""
        rm = ReferenceManager()
        assert "hg38" in rm.SUPPORTED_VERSIONS
        assert "hg19" in rm.SUPPORTED_VERSIONS
        assert "t2t" in rm.SUPPORTED_VERSIONS
    
    def test_get_config_hg38(self):
        """测试获取 hg38 配置"""
        rm = ReferenceManager()
        config = rm.get_config("hg38")
        
        assert isinstance(config, ReferenceConfig)
        assert config.version == "hg38"
        assert "hs38" in str(config.genome_file)
    
    def test_get_config_invalid_version(self):
        """测试无效版本"""
        rm = ReferenceManager()
        
        with pytest.raises(ValueError) as exc_info:
            rm.get_config("hg99")
        
        assert "不支持的基因组版本" in str(exc_info.value)
    
    def test_get_genome_path(self):
        """测试获取基因组路径"""
        rm = ReferenceManager()
        path = rm.get_genome_path("hg38")
        
        assert isinstance(path, Path)
        assert "hs38.fa" in str(path)
    
    def test_get_liftover_chain(self):
        """测试获取 liftOver chain"""
        rm = ReferenceManager()
        
        # hg38 -> hg19 应该返回 chain 文件
        chain = rm.get_liftover_chain("hg38", "hg19")
        assert chain is not None
        assert "hg38ToHg19" in str(chain)
        
        # 相同版本应该返回 None
        chain = rm.get_liftover_chain("hg38", "hg38")
        assert chain is None
    
    def test_get_1240k_file(self):
        """测试获取 1240K 文件路径"""
        rm = ReferenceManager()
        path = rm.get_1240k_file()
        
        assert "1240K" in str(path)
