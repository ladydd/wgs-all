"""
参考数据管理模块 - 管理参考基因组和注释文件

设计原则：
- 三套参考系（hg38/hg19/t2t）各自独立，结构一致
- 每个版本自包含，不依赖坐标转换
- 新增版本只需复制骨架，往里填文件
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .config import settings
from .logging import logger


@dataclass
class ReferenceConfig:
    """单个参考基因组版本的完整配置"""
    version: str          # hg38, hg19, t2t
    display_name: str     # 显示名称
    
    # genome/
    genome_file: Path     # 参考基因组 FASTA
    
    # snp/
    snp_annotation: Path  # SNP 注释文件 (bcftools annotate 用)
    
    # y_chromosome/
    yleaf_positions: Path  # yleaf Y-SNP 位点文件
    
    # mt/
    mt_reference: Optional[Path] = None  # MT 分析参考 (待补)
    
    # 1240k/
    k1240_file: Optional[Path] = None  # 1240K 位点文件
    
    # liftover (仅特殊场景用，如芯片模板需要 hg19 坐标)
    liftover_chain: Optional[Path] = None

    @property
    def bwa_index(self) -> Path:
        """BWA 索引前缀 (跟 genome_file 同路径同名)"""
        return self.genome_file

    @property
    def genome_dir(self) -> Path:
        return self.genome_file.parent

    @property
    def version_dir(self) -> Path:
        """版本根目录"""
        return self.genome_file.parent.parent


class ReferenceManager:
    """
    参考数据管理器
    
    管理三套独立的参考基因组及其配套文件
    """
    
    SUPPORTED_VERSIONS = ["hg38", "hg19", "t2t"]
    
    def __init__(self, reference_dir: Optional[Path] = None):
        self.reference_dir = reference_dir or settings.reference_dir
        self._configs: Dict[str, ReferenceConfig] = {}
        self._init_configs()
    
    def _init_configs(self):
        """初始化各版本配置 (按新目录结构)"""
        
        # hg38
        hg38_dir = self.reference_dir / "hg38"
        self._configs["hg38"] = ReferenceConfig(
            version="hg38",
            display_name="GRCh38 / hg38 (2013)",
            genome_file=hg38_dir / "genome" / "hs38.fa",
            snp_annotation=hg38_dir / "snp" / "All_SNPs_hg38_ref.tab.gz",
            yleaf_positions=hg38_dir / "y_chromosome" / "WGS_hg38.txt",
            k1240_file=hg38_dir / "1240k" / "1240K_hg38.tab.gz",
            liftover_chain=self.reference_dir / "liftover" / "hg38ToHg19.over.chain.gz",
        )
        
        # hg19
        hg19_dir = self.reference_dir / "hg19"
        self._configs["hg19"] = ReferenceConfig(
            version="hg19",
            display_name="GRCh37 / hg19 (2009)",
            genome_file=hg19_dir / "genome" / "hs37d5.fa",
            snp_annotation=hg19_dir / "snp" / "All_SNPs_hg19_ref.tab.gz",
            yleaf_positions=hg19_dir / "y_chromosome" / "WGS_hg19.txt",
            k1240_file=hg19_dir / "1240k" / "1240K_hg19.tab.gz",
            liftover_chain=None,
        )
        
        # T2T
        t2t_dir = self.reference_dir / "t2t"
        self._configs["t2t"] = ReferenceConfig(
            version="t2t",
            display_name="T2T-CHM13v2 (2022)",
            genome_file=t2t_dir / "genome" / "chm13v2.fa",
            snp_annotation=t2t_dir / "snp" / "All_SNPs_t2t_ref.tab.gz",
            yleaf_positions=t2t_dir / "y_chromosome" / "WGS_t2t.txt",
            k1240_file=t2t_dir / "1240k" / "1240K_t2t.tab.gz",
            liftover_chain=self.reference_dir / "liftover" / "chm13v2-hg19.chain",
        )
    
    def get_config(self, version: str) -> ReferenceConfig:
        """获取指定版本的参考配置"""
        if version not in self.SUPPORTED_VERSIONS:
            raise ValueError(
                f"不支持的基因组版本: {version}, "
                f"支持的版本: {self.SUPPORTED_VERSIONS}"
            )
        return self._configs[version]
    
    def validate_references(self, version: str = "hg38") -> Dict[str, bool]:
        """
        验证参考文件是否存在
        
        Returns:
            {文件类型: 是否存在} 字典
        """
        config = self.get_config(version)
        
        results = {
            "genome_file": config.genome_file.exists(),
            "bwa_index": Path(f"{config.genome_file}.bwt").exists(),
            "genome_fai": Path(f"{config.genome_file}.fai").exists(),
            "snp_annotation": config.snp_annotation.exists(),
            "yleaf_positions": config.yleaf_positions.exists(),
        }
        
        if config.k1240_file:
            results["1240k_file"] = config.k1240_file.exists()
        
        if config.liftover_chain:
            results["liftover_chain"] = config.liftover_chain.exists()
        
        # 记录状态
        missing = [k for k, v in results.items() if not v]
        if missing:
            logger.warning(f"[{version}] 缺失文件: {missing}")
        else:
            logger.info(f"[{version}] 所有参考文件就绪")
        
        return results
    
    def get_genome_path(self, version: str = "hg38") -> Path:
        """获取参考基因组路径"""
        return self.get_config(version).genome_file
    
    def get_snp_annotation(self, version: str = "hg38") -> Path:
        """获取 SNP 注释文件路径"""
        return self.get_config(version).snp_annotation
    
    def get_yleaf_position_file(self, version: str = "hg38") -> Path:
        """获取 yleaf 位点文件"""
        return self.get_config(version).yleaf_positions
    
    def get_1240k_file(self, version: str = "hg38") -> Path:
        """获取 1240K 位点文件"""
        config = self.get_config(version)
        if config.k1240_file:
            return config.k1240_file
        raise FileNotFoundError(f"[{version}] 1240K 位点文件未配置")
    
    def get_liftover_chain(self, from_version: str, to_version: str) -> Optional[Path]:
        """获取 liftOver chain 文件路径 (仅特殊场景用)"""
        if from_version == to_version:
            return None
        config = self.get_config(from_version)
        return config.liftover_chain
    
    def get_chip_template_dir(self) -> Path:
        """获取芯片模板目录 (版本无关)"""
        return self.reference_dir / "microarray" / "raw_file_templates"

    def get_eigenstrat_positions(
        self,
        version: str = "hg38",
        position_set: str = "v42.4.1240K",
        with_chr_prefix: bool = True,
    ) -> Dict[str, Path]:
        """
        获取 EIGENSTRAT 位点文件路径

        Args:
            version: 参考基因组版本 (目前只支持 hg38)
            position_set: 位点集名称，如 "v42.4.1240K" 或 "v66.2M.aadr"
            with_chr_prefix: 返回的 .pos 文件是否带 chr 前缀 (应与 BAM 命名风格一致)

        Returns:
            {
                "snp": .snp 文件路径 (EIGENSTRAT 6 列，pileupCaller --snpFile 用),
                "pos": .pos 文件路径 (2 列，samtools mpileup -l 用),
                "log": liftover_log.tsv 路径 (可选),
            }

        Raises:
            FileNotFoundError: 位点文件不存在
            ValueError: 版本暂不支持
        """
        if version not in ("hg38", "hg19"):
            raise ValueError(
                f"EIGENSTRAT 位点支持 hg38 / hg19 (请求: {version})。"
            )

        if version == "hg19":
            # hg19 直接用 AADR 原版位点文件（不需要 liftOver）
            # 优先查 /reference/aadr_positions/（Docker 内），再查 adna_to_dataset/positions/
            candidates = [
                self.reference_dir / "aadr_positions",
                Path("/reference/aadr_positions"),
            ]
            for base_dir in candidates:
                snp_file = base_dir / f"{position_set}.snp"
                if snp_file.exists():
                    # pos 文件：无 chr 前缀用 .pos，有 chr 前缀用 .hg19.pos
                    if with_chr_prefix:
                        pos_file = base_dir / f"{position_set}.hg19.pos"
                    else:
                        pos_file = base_dir / f"{position_set}.pos"
                    if not pos_file.exists():
                        pos_file = base_dir / f"{position_set}.pos"
                    return {
                        "snp": snp_file,
                        "pos": pos_file,
                        "log": None,
                    }
            raise FileNotFoundError(
                f"EIGENSTRAT hg19 .snp 文件不存在: {position_set}.snp\n"
                f"已查找: {candidates}"
            )

        # hg38: 用 liftOver 产物
        base_dir = self.reference_dir / "population" / "eigenstrat"
        prefix = f"{position_set}.hg38"

        snp_file = base_dir / f"{prefix}.snp"
        pos_file = base_dir / (f"{prefix}.chr.pos" if with_chr_prefix else f"{prefix}.pos")
        log_file = base_dir / f"{prefix}.liftover_log.tsv"

        if not snp_file.exists():
            raise FileNotFoundError(
                f"EIGENSTRAT .snp 文件不存在: {snp_file}\n"
                f"请先运行: scripts/liftover_aadr_snp_to_hg38.py"
            )
        if not pos_file.exists():
            raise FileNotFoundError(f"EIGENSTRAT .pos 文件不存在: {pos_file}")

        return {
            "snp": snp_file,
            "pos": pos_file,
            "log": log_file if log_file.exists() else None,
        }
    
    def get_readiness_summary(self) -> Dict[str, dict]:
        """获取所有版本的就绪状态摘要"""
        summary = {}
        for version in self.SUPPORTED_VERSIONS:
            results = self.validate_references(version)
            summary[version] = {
                "display_name": self._configs[version].display_name,
                "ready": all(results.values()),
                "files": results,
            }
        return summary


# 全局实例
reference_manager = ReferenceManager()
