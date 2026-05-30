"""
全流程一键分析 - 从 BAM 到全部结果

输入: 一个或多个 BAM 文件
输出: 全部分析结果 (chrY/chrM 提取 + Y/MT 单倍群 + EIGENSTRAT + 芯片格式 + 祖源计算器)
"""

import os
from pathlib import Path
from typing import List, Optional

from ..core.logging import logger


def run_full_pipeline(
    bam_files: List[str],
    output_dir: str,
    population: str = "Unknown",
    position_set: str = "v42.4.1240K",
    reference: str = "hg38",
    calculators: Optional[List[str]] = None,
    seed: int = 42,
):
    """
    一键跑全部分析

    Args:
        bam_files: BAM 文件列表
        output_dir: 输出根目录
        population: 群体标签
        position_set: EIGENSTRAT 位点集
        reference: 参考版本 (hg38/hg19)
        calculators: 祖源计算器列表
        seed: 随机种子
    """
    from .alignment import ChromosomeExtractor
    from .haplogroup import YHaplogroupAnalyzer, MTHaplogroupAnalyzer
    from .eigenstrat import EigenstratExtractor
    from .extraction import ChipFormatExtractor
    from .calculator import AdmixtureCalculator

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    results = {"samples": []}

    for bam in bam_files:
        sample_id = Path(bam).stem.replace(".sorted", "").replace(".dedup", "")
        sample_dir = out / sample_id
        sample_dir.mkdir(exist_ok=True)
        sample_result = {"sample_id": sample_id, "bam": bam}

        logger.info(f"{'='*60}")
        logger.info(f"处理样本: {sample_id}")
        logger.info(f"{'='*60}")

        # 1. 提取 chrY + chrM
        try:
            logger.info("[1/5] 提取 chrY/chrM...")
            extractor = ChromosomeExtractor(reference=reference)
            chry_result = extractor.extract(bam, "chrY", str(sample_dir), sample_id)
            chrm_result = extractor.extract(bam, "chrM", str(sample_dir), sample_id)
            sample_result["chrY"] = {"bam": chry_result.bam_file, "coverage": chry_result.coverage}
            sample_result["chrM"] = {"bam": chrm_result.bam_file, "coverage": chrm_result.coverage}
        except Exception as e:
            logger.warning(f"chrY/chrM 提取失败: {e}")
            sample_result["chrY"] = {"error": str(e)}
            sample_result["chrM"] = {"error": str(e)}

        # 2. Y 单倍群
        try:
            logger.info("[2/5] Y 单倍群分析...")
            y_analyzer = YHaplogroupAnalyzer()
            y_result = y_analyzer.analyze(
                chry_result.bam_file, str(sample_dir / "yleaf"), sample_id, reference
            )
            sample_result["y_haplogroup"] = y_result.haplogroup
        except Exception as e:
            logger.warning(f"Y 单倍群失败: {e}")
            sample_result["y_haplogroup"] = f"Error: {e}"

        # 3. MT 单倍群
        try:
            logger.info("[3/5] MT 单倍群分析...")
            mt_analyzer = MTHaplogroupAnalyzer()
            mt_result = mt_analyzer.analyze(
                chrm_result.vcf_file, str(sample_dir / "mt_haplogroup.txt")
            )
            sample_result["mt_haplogroup"] = mt_result.haplogroup
        except Exception as e:
            logger.warning(f"MT 单倍群失败: {e}")
            sample_result["mt_haplogroup"] = f"Error: {e}"

        # 4. 芯片格式 + 祖源计算器
        try:
            logger.info("[4/5] 芯片格式导出 + 祖源计算...")
            chip_extractor = ChipFormatExtractor()
            chip_dir = str(sample_dir / "chip")
            chip_results = chip_extractor.extract(bam, chip_dir, sample_id)
            sample_result["chip_formats"] = len(chip_results)

            # 用 23andMe V5 跑计算器
            chip_file = os.path.join(chip_dir, f"{sample_id}_23andMe_V5.txt")
            if os.path.exists(chip_file):
                calc = AdmixtureCalculator()
                calc_result = calc.run(chip_file, sample_id, calculators)
                sample_result["admixture"] = {
                    cr.calculator: cr.components for cr in calc_result.calculators
                }
        except Exception as e:
            logger.warning(f"芯片/计算器失败: {e}")
            sample_result["chip_formats"] = f"Error: {e}"

        results["samples"].append(sample_result)

    # 5. EIGENSTRAT (所有样本合并)
    try:
        logger.info(f"\n[5/5] EIGENSTRAT 数据集 (全部 {len(bam_files)} 样本合并)...")
        eigen_extractor = EigenstratExtractor(reference_version=reference)
        eigen_dir = str(out / "eigenstrat")
        eigen_result = eigen_extractor.extract(
            bam_files=bam_files,
            population=population,
            output_dir=eigen_dir,
            output_name="dataset",
            position_set=position_set,
        )
        results["eigenstrat"] = {
            "geno": eigen_result.geno_file,
            "snp": eigen_result.snp_file,
            "ind": eigen_result.ind_file,
            "total_snps": eigen_result.total_snps,
        }
    except Exception as e:
        logger.warning(f"EIGENSTRAT 失败: {e}")
        results["eigenstrat"] = {"error": str(e)}

    # 汇总
    logger.info(f"\n{'='*60}")
    logger.info(f"全流程完成! 输出目录: {output_dir}")
    logger.info(f"{'='*60}")

    return results
