"""
BAM 参考基因组版本自动识别模块

通过读取 BAM 文件 header 中的染色体长度信息，
精确匹配已知参考基因组版本。
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .logging import logger


@dataclass
class BamInfo:
    """BAM 文件识别结果"""
    file_path: str
    reference_version: str          # hg38, hg19, grch37, t2t, unknown
    reference_display: str          # 人类可读名称
    has_chr_prefix: bool            # 染色体是否有 chr 前缀
    chr1_length: int                # chr1 长度
    mt_name: str                    # 线粒体名称 (chrM / MT)
    confidence: str                 # high / low / none


# 已知参考基因组的 chr1 长度指纹
# 这些是物理事实，不会变
_CHR1_SIGNATURES = {
    248956422: "hg38",      # GRCh38
    249250621: "hg19",      # GRCh37 / hg19 (需进一步区分 chr 前缀)
    248387328: "t2t",       # T2T-CHM13v2
}


def detect_bam_reference(bam_path: str) -> BamInfo:
    """
    自动识别 BAM 文件的参考基因组版本
    
    通过读取 BAM header 中 @SQ 行的染色体名称和长度，
    精确匹配已知参考基因组版本。
    
    Args:
        bam_path: BAM 文件路径
    
    Returns:
        BamInfo 包含识别结果
    """
    if not Path(bam_path).exists():
        raise FileNotFoundError(f"BAM 文件不存在: {bam_path}")
    
    # 读取 BAM header
    result = subprocess.run(
        f'samtools view -H "{bam_path}"',
        shell=True, capture_output=True, text=True
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"无法读取 BAM header: {result.stderr}")
    
    # 解析 @SQ 行
    sequences = {}  # {name: length}
    for line in result.stdout.split('\n'):
        if line.startswith('@SQ'):
            parts = line.split('\t')
            name = None
            length = None
            for part in parts:
                if part.startswith('SN:'):
                    name = part[3:]
                elif part.startswith('LN:'):
                    length = int(part[3:])
            if name and length:
                sequences[name] = length
    
    if not sequences:
        return BamInfo(
            file_path=bam_path,
            reference_version="unknown",
            reference_display="无法识别",
            has_chr_prefix=False,
            chr1_length=0,
            mt_name="",
            confidence="none",
        )
    
    # 判断是否有 chr 前缀
    has_chr_prefix = "chr1" in sequences
    
    # 获取 chr1 长度
    chr1_length = sequences.get("chr1", sequences.get("1", 0))
    
    # 判断线粒体名称
    mt_name = ""
    if "chrM" in sequences:
        mt_name = "chrM"
    elif "MT" in sequences:
        mt_name = "MT"
    
    # 匹配参考基因组版本
    version = _CHR1_SIGNATURES.get(chr1_length, None)
    
    if version is None:
        logger.warning(f"无法识别参考基因组版本, chr1 长度: {chr1_length}")
        return BamInfo(
            file_path=bam_path,
            reference_version="unknown",
            reference_display=f"未知 (chr1={chr1_length})",
            has_chr_prefix=has_chr_prefix,
            chr1_length=chr1_length,
            mt_name=mt_name,
            confidence="none",
        )
    
    # hg19 需要进一步区分
    if version == "hg19":
        if has_chr_prefix:
            display = "hg19 (UCSC 风格, chr 前缀)"
        else:
            display = "GRCh37 (Ensembl 风格, 无 chr 前缀)"
            version = "grch37"
    elif version == "hg38":
        display = "GRCh38 / hg38"
    elif version == "t2t":
        display = "T2T-CHM13v2"
    else:
        display = version
    
    logger.info(f"BAM 参考基因组识别: {display} (chr1={chr1_length})")
    
    return BamInfo(
        file_path=bam_path,
        reference_version=version,
        reference_display=display,
        has_chr_prefix=has_chr_prefix,
        chr1_length=chr1_length,
        mt_name=mt_name,
        confidence="high",
    )


def map_to_system_version(bam_info: BamInfo) -> str:
    """
    将 BAM 识别结果映射到系统支持的版本名称
    
    grch37 和 hg19 在系统里都走 hg19 流程
    
    Returns:
        系统版本名: hg38, hg19, t2t
    
    Raises:
        ValueError: 无法映射
    """
    mapping = {
        "hg38": "hg38",
        "hg19": "hg19",
        "grch37": "hg19",  # GRCh37 无 chr 前缀，但走 hg19 流程
        "t2t": "t2t",
    }
    
    system_version = mapping.get(bam_info.reference_version)
    if not system_version:
        raise ValueError(
            f"无法映射到系统版本: {bam_info.reference_version} "
            f"({bam_info.reference_display})"
        )
    
    return system_version
