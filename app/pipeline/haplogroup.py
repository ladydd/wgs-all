"""
单倍群分析模块 - Y 染色体和线粒体单倍群分析

Y 单倍群: 使用 yleaf
MT 单倍群: 使用 Haplogrep (待实现)
"""

import os
import subprocess
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List

from ..core.config import settings
from ..core.logging import logger
from ..core.reference import reference_manager


@dataclass
class YHaplogroupResult:
    """Y 单倍群分析结果"""
    haplogroup: str  # 预测的单倍群 (如 D1a2b1)
    confidence: float  # 置信度
    haplogroup_path: List[str]  # 单倍群路径
    markers_used: int  # 使用的标记数
    quality_markers: int  # 高质量标记数
    output_dir: str  # 输出目录


@dataclass
class MTHaplogroupResult:
    """MT 单倍群分析结果"""
    haplogroup: str
    quality_score: float
    variants: List[str]


def _run_cmd(cmd: str, desc: str = "") -> subprocess.CompletedProcess:
    """运行命令"""
    if desc:
        logger.info(f"  {desc}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"命令失败: {result.stderr}")
        raise RuntimeError(f"Command failed: {cmd}\n{result.stderr}")
    return result


def _find_executable(name: str) -> str:
    """查找可执行文件路径"""
    result = subprocess.run(f"which {name}", shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    raise FileNotFoundError(f"找不到 {name}，请确保已安装并在 PATH 中")


class YHaplogroupAnalyzer:
    """
    Y 染色体单倍群分析器

    使用 Yleaf v4 分析 Y 染色体单倍群
    支持 4 种 Y-SNP 树: isogg, yfull, yfull_v10, ftdna
    支持 3 种参考系: hg38, hg19, t2t
    支持古 DNA 模式 (-aDNA)
    """

    SUPPORTED_TREES = ["isogg", "yfull", "yfull_v10", "ftdna"]

    def __init__(
        self,
        yleaf_dir: Optional[Path] = None,
        threads: int = None,
        quality_thresh: int = 20,
        reads_thresh: int = 1,
        base_majority: int = 90,
    ):
        # 查找 yleaf v4: 优先用 Python 包，fallback 到二进制
        try:
            import yleaf
            self.yleaf_mode = "python"
            self.yleaf_bin = None
        except ImportError:
            # fallback 到独立二进制
            candidates = [
                Path(yleaf_dir) / "yleaf" if yleaf_dir else None,
                Path("/reference/yleaf_v4/yleaf/yleaf"),
                settings.reference_dir / "yleaf_v4" / "yleaf" / "yleaf",
            ]
            self.yleaf_bin = None
            for c in candidates:
                if c and c.exists():
                    self.yleaf_bin = str(c)
                    break
            if not self.yleaf_bin:
                raise FileNotFoundError(
                    "找不到 Yleaf v4。请确认已安装 (pip install yleaf) 或二进制存在。"
                )
            self.yleaf_mode = "binary"

        self.threads = threads or settings.effective_threads
        self.quality_thresh = quality_thresh
        self.reads_thresh = reads_thresh
        self.base_majority = base_majority

    def analyze(
        self,
        chry_bam: str,
        output_dir: str,
        sample_id: Optional[str] = None,
        reference: str = "hg38",
        tree: str = "isogg",
        ancient_dna: bool = True,
    ) -> YHaplogroupResult:
        """
        分析 Y 染色体单倍群

        Args:
            chry_bam: chrY BAM 文件路径
            output_dir: 输出目录
            sample_id: 样本 ID
            reference: 参考基因组版本 (hg38/hg19/t2t)
            tree: Y-SNP 树 (isogg/yfull/yfull_v10/ftdna)
            ancient_dna: 是否启用古 DNA 模式
        """
        if not os.path.exists(chry_bam):
            raise FileNotFoundError(f"BAM 文件不存在: {chry_bam}")

        if tree not in self.SUPPORTED_TREES:
            raise ValueError(f"不支持的树: {tree}，支持: {self.SUPPORTED_TREES}")

        if not sample_id:
            sample_id = Path(chry_bam).stem.replace('.chrY', '').replace('.sorted', '')

        # 检测 chrY 覆盖度，低于 1x 可能是女性样本
        # 只对全基因组 BAM 做检测（chrY BAM 跳过，因为已经提取过了）
        import subprocess
        try:
            idxstats = subprocess.run(
                ["samtools", "idxstats", chry_bam], capture_output=True, text=True
            )
            if idxstats.returncode == 0:
                total_mapped = 0
                chry_mapped = 0
                chry_len = 0
                for line in idxstats.stdout.strip().split("\n"):
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        total_mapped += int(parts[2])
                        if parts[0] in ("chrY", "Y"):
                            chry_len = int(parts[1])
                            chry_mapped = int(parts[2])
                # 只有全基因组 BAM（多条染色体有 reads）才做女性检测
                non_zero_chroms = sum(1 for line in idxstats.stdout.strip().split("\n")
                                     if len(line.split("\t")) >= 3 and int(line.split("\t")[2]) > 0)
                if non_zero_chroms > 3 and chry_len > 0:
                    chry_ratio = chry_mapped / total_mapped if total_mapped > 0 else 0
                    # 女性样本 chrY reads 占比通常 < 0.1%
                    if chry_ratio < 0.001:
                        logger.warning(
                            f"⚠️ chrY reads 占比极低 ({chry_ratio:.4%})，该样本可能是女性。"
                            f" Y 单倍群结果可能不可靠。"
                        )
        except Exception:
            pass

        os.makedirs(output_dir, exist_ok=True)

        # Yleaf v4 在输出子目录已存在时会交互式询问覆盖，需要预先清理
        yleaf_subdir = Path(output_dir) / Path(chry_bam).stem
        if yleaf_subdir.exists():
            import shutil
            shutil.rmtree(yleaf_subdir)

        # Yleaf 需要对 BAM 建索引，如果 BAM 所在目录只读则复制到输出目录
        bam_path = Path(chry_bam)
        bai_path = Path(f"{chry_bam}.bai")
        if not bai_path.exists():
            # 尝试在原位建索引，失败则复制到输出目录的上级
            import subprocess, shutil
            ret = subprocess.run(["samtools", "index", str(bam_path)], capture_output=True)
            if ret.returncode != 0:
                work_dir = Path(output_dir).parent
                local_bam = work_dir / bam_path.name
                if not local_bam.exists():
                    shutil.copy2(str(bam_path), str(local_bam))
                subprocess.run(["samtools", "index", str(local_bam)], check=True)
                chry_bam = str(local_bam)

        logger.info(f"分析 Y 单倍群: {chry_bam}")
        logger.info(f"  参考: {reference}, 树: {tree}, 古DNA模式: {ancient_dna}")

        # 构建命令
        if self.yleaf_mode == "python":
            import sys
            python_bin = sys.executable
            cmd = (
                f'{python_bin} -c "from yleaf.Yleaf import main; import sys; sys.argv = ['
                f"'yleaf', "
                f"'-bam', '{chry_bam}', "
                f"'-o', '{output_dir}', "
                f"'-rg', '{reference}', "
                f"'-t', '{self.threads}', "
                f"'-q', '{self.quality_thresh}', "
                f"'-b', '{self.base_majority}', "
                f"'-r', '{self.reads_thresh}', "
                f"'-tree', '{tree}'"
            )
            if ancient_dna:
                cmd += ", '-aDNA'"
            cmd += ", '-force'"
            cmd += ']; main()"'
        else:
            cmd = (
                f'"{self.yleaf_bin}" '
                f'-bam "{chry_bam}" '
                f'-o "{output_dir}" '
                f'-rg {reference} '
                f'-t {self.threads} '
                f'-q {self.quality_thresh} '
                f'-b {self.base_majority} '
                f'-r {self.reads_thresh} '
                f'-tree {tree} '
            )
            if ancient_dna:
                cmd += '-aDNA '
            cmd += '-force '

        _run_cmd(cmd, "Yleaf v4")

        # 解析结果
        result = self._parse_results(output_dir, sample_id)
        logger.info(f"Y 单倍群: {result.haplogroup} (QC: {result.confidence})")
        return result

    def _parse_results(self, output_dir: str, sample_id: str) -> YHaplogroupResult:
        """解析 Yleaf v4 输出"""
        haplogroup = "Unknown"
        confidence = 0.0
        markers_used = 0
        quality_markers = 0
        haplogroup_path = []

        # 读取 hg_prediction.hg
        hg_file = os.path.join(output_dir, "hg_prediction.hg")
        if os.path.exists(hg_file):
            with open(hg_file, 'r') as f:
                lines = f.readlines()
                for line in lines[1:]:  # 跳过表头
                    parts = line.strip().split('\t')
                    if len(parts) >= 6:
                        haplogroup = parts[1] if parts[1] != "NA" else "Unknown"
                        markers_used = int(parts[4]) if parts[4].isdigit() else 0
                        try:
                            confidence = float(parts[5])
                        except (ValueError, IndexError):
                            confidence = 0.0
                        break

        return YHaplogroupResult(
            haplogroup=haplogroup,
            confidence=confidence,
            haplogroup_path=haplogroup_path,
            markers_used=markers_used,
            quality_markers=quality_markers,
            output_dir=output_dir,
        )


class MTHaplogroupAnalyzer:
    """
    线粒体单倍群分析器

    使用 Haplogrep3 分析 MT 单倍群
    输入: chrM VCF 文件
    输出: MT 单倍群 (如 H4a1a4b, D4, B4a1 等)
    """

    def __init__(self, haplogrep_dir: Optional[str] = None):
        # 查找 haplogrep3 目录
        candidates = [
            Path(haplogrep_dir) if haplogrep_dir else None,
            Path("/reference/tools/haplogrep"),  # Docker 内
            settings.reference_dir / "tools" / "haplogrep",  # 本地
        ]
        self.haplogrep_dir = None
        for c in candidates:
            if c and (c / "haplogrep3.jar").exists():
                self.haplogrep_dir = c
                break

        if not self.haplogrep_dir:
            raise FileNotFoundError(
                "找不到 haplogrep3，请确认 haplogrep3.jar 存在于 "
                "/reference/tools/haplogrep/ 或 reference_dir/tools/haplogrep/"
            )

    def analyze(self, chrm_vcf: str, output_file: str) -> MTHaplogroupResult:
        """
        分析 MT 单倍群

        Args:
            chrm_vcf: chrM VCF 文件 (.vcf 或 .vcf.gz)
            output_file: 输出文件路径

        Returns:
            MTHaplogroupResult
        """
        if not os.path.exists(chrm_vcf):
            raise FileNotFoundError(f"VCF 文件不存在: {chrm_vcf}")

        logger.info(f"分析 MT 单倍群: {chrm_vcf}")

        # 运行 haplogrep3 classify
        jar = self.haplogrep_dir / "haplogrep3.jar"
        cmd = (
            f'java -Xmx2G -jar "{jar}" classify '
            f'--tree phylotree-fu-rcrs@1.2 '
            f'--input "{chrm_vcf}" '
            f'--output "{output_file}"'
        )
        _run_cmd(cmd, "Haplogrep3 classify")

        # 解析结果
        result = self._parse_result(output_file)
        logger.info(f"MT 单倍群: {result.haplogroup} (质量: {result.quality_score})")
        return result

    def _parse_result(self, output_file: str) -> MTHaplogroupResult:
        """解析 Haplogrep3 输出 (TSV 格式)"""
        haplogroup = "Unknown"
        quality_score = 0.0
        variants = []

        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                lines = f.readlines()
                if len(lines) >= 2:
                    # 跳过表头，取第一个样本的结果
                    parts = lines[1].strip().replace('"', '').split('\t')
                    if len(parts) >= 4:
                        haplogroup = parts[1]
                        try:
                            quality_score = float(parts[3])
                        except (ValueError, IndexError):
                            quality_score = 0.0

        return MTHaplogroupResult(
            haplogroup=haplogroup,
            quality_score=quality_score,
            variants=variants,
        )
