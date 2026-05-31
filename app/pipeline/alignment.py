"""
比对模块 - BWA-MEM 比对和 samtools 处理

流程:
1. BWA-MEM 比对 FASTQ -> SAM
2. samtools sort 排序 -> BAM
3. samtools index 建索引
4. 提取 chrY/chrM
5. SNP calling
"""

import os
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple

from ..core.config import settings
from ..core.logging import logger
from ..core.reference import reference_manager


@dataclass
class AlignmentResult:
    """比对结果"""
    bam_file: str
    bam_index: str
    total_reads: int
    mapped_reads: int
    mapping_rate: float
    average_coverage: float


@dataclass
class ChromosomeResult:
    """染色体提取结果"""
    bam_file: str
    vcf_file: Optional[str]
    coverage: float
    snp_count: int


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
    """查找可执行文件"""
    result = subprocess.run(f"which {name}", shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    raise FileNotFoundError(f"找不到 {name}，请确保已安装")


class AlignmentModule:
    """
    比对模块
    
    使用 BWA-MEM 进行序列比对，samtools 进行排序和索引
    """
    
    def __init__(
        self,
        reference: str = "hg38",
        threads: int = None,
        sort_memory: str = "2G",
    ):
        """
        初始化比对模块
        
        Args:
            reference: 参考基因组版本 (hg38/hg19)
            threads: 线程数
            sort_memory: 每线程排序内存
        """
        self.reference = reference
        self.threads = threads or settings.threads
        self.sort_memory = sort_memory
        
        # 获取参考基因组路径
        self.ref_genome = reference_manager.get_genome_path(reference)
        if not self.ref_genome.exists():
            raise FileNotFoundError(f"参考基因组不存在: {self.ref_genome}")
        
        # 检查 BWA 索引
        bwt_file = Path(f"{self.ref_genome}.bwt")
        if not bwt_file.exists():
            raise FileNotFoundError(f"BWA 索引不存在: {bwt_file}，请先运行 bwa index")
    
    def align(
        self,
        fastq_r1: str,
        fastq_r2: str,
        output_dir: str,
        sample_id: str,
    ) -> AlignmentResult:
        """
        比对 FASTQ 文件
        
        Args:
            fastq_r1: R1 FASTQ 文件
            fastq_r2: R2 FASTQ 文件
            output_dir: 输出目录
            sample_id: 样本 ID
        
        Returns:
            AlignmentResult
        """
        # 检查输入文件
        if not os.path.exists(fastq_r1):
            raise FileNotFoundError(f"R1 文件不存在: {fastq_r1}")
        if not os.path.exists(fastq_r2):
            raise FileNotFoundError(f"R2 文件不存在: {fastq_r2}")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # 输出文件
        sorted_bam = os.path.join(output_dir, f"{sample_id}.sorted.bam")
        tmp_dir = os.path.join(output_dir, "tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        
        logger.info(f"开始比对: {sample_id}")
        logger.info(f"  R1: {fastq_r1}")
        logger.info(f"  R2: {fastq_r2}")
        logger.info(f"  参考基因组: {self.ref_genome}")
        logger.info(f"  线程数: {self.threads}")
        
        # BWA-MEM + samtools sort (管道)
        logger.info("Step 1: BWA-MEM 比对 + 排序 (这可能需要几小时)...")
        cmd = (
            f'bwa mem -t {self.threads} '
            f'-R "@RG\\tID:{sample_id}\\tSM:{sample_id}\\tPL:ILLUMINA" '
            f'"{self.ref_genome}" "{fastq_r1}" "{fastq_r2}" | '
            f'samtools sort -@ {self.threads} -m {self.sort_memory} '
            f'-T "{tmp_dir}/{sample_id}.tmp" -o "{sorted_bam}"'
        )
        _run_cmd(cmd, "BWA-MEM + samtools sort")
        
        # 建索引
        logger.info("Step 2: 建立 BAM 索引...")
        cmd = f'samtools index -@ {self.threads} "{sorted_bam}"'
        _run_cmd(cmd, "samtools index")
        
        # 获取统计信息
        stats = self._get_bam_stats(sorted_bam)
        
        logger.info(f"比对完成!")
        logger.info(f"  总读取数: {stats['total_reads']:,}")
        logger.info(f"  比对率: {stats['mapping_rate']:.1f}%")
        
        return AlignmentResult(
            bam_file=sorted_bam,
            bam_index=sorted_bam + ".bai",
            total_reads=stats['total_reads'],
            mapped_reads=stats['mapped_reads'],
            mapping_rate=stats['mapping_rate'],
            average_coverage=stats['coverage'],
        )
    
    def _get_bam_stats(self, bam_file: str) -> dict:
        """获取 BAM 统计信息"""
        # samtools flagstat
        result = subprocess.run(
            f'samtools flagstat "{bam_file}"',
            shell=True, capture_output=True, text=True
        )
        
        total_reads = 0
        mapped_reads = 0
        
        for line in result.stdout.split('\n'):
            if 'in total' in line:
                total_reads = int(line.split()[0])
            elif 'mapped (' in line and 'primary' not in line:
                mapped_reads = int(line.split()[0])
        
        mapping_rate = (mapped_reads / total_reads * 100) if total_reads > 0 else 0
        
        # 简单估算覆盖度 (可选，耗时)
        coverage = 0.0
        
        return {
            'total_reads': total_reads,
            'mapped_reads': mapped_reads,
            'mapping_rate': mapping_rate,
            'coverage': coverage,
        }


class ChromosomeExtractor:
    """
    染色体提取器
    
    从 BAM 文件提取特定染色体，并进行 SNP calling
    """
    
    def __init__(
        self,
        reference: str = "hg38",
        threads: int = None,
    ):
        self.reference = reference
        self.threads = threads or settings.threads
        self.ref_genome = reference_manager.get_genome_path(reference)
    
    def extract(
        self,
        bam_file: str,
        chromosome: str,
        output_dir: str,
        sample_id: str,
        call_snps: bool = True,
    ) -> ChromosomeResult:
        """
        提取染色体
        
        Args:
            bam_file: 输入 BAM 文件
            chromosome: 染色体名称 (chrY, chrM)
            output_dir: 输出目录
            sample_id: 样本 ID
            call_snps: 是否进行 SNP calling
        
        Returns:
            ChromosomeResult
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 输出文件
        chr_bam = os.path.join(output_dir, f"{sample_id}.{chromosome}.bam")
        chr_vcf = os.path.join(output_dir, f"{sample_id}.{chromosome}.vcf.gz")
        
        logger.info(f"提取 {chromosome}: {bam_file}")
        
        # 自动适配染色体命名（chrY↔Y, chrM↔MT）
        actual_chr = chromosome
        check_cmd = f'samtools idxstats "{bam_file}" | cut -f1'
        check = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
        if check.returncode == 0:
            chroms_in_bam = check.stdout.strip().split("\n")
            if chromosome not in chroms_in_bam:
                # 尝试去掉/加上 chr 前缀
                alt = chromosome.replace("chr", "") if chromosome.startswith("chr") else f"chr{chromosome}"
                # MT ↔ chrM
                if chromosome == "chrM" and "MT" in chroms_in_bam:
                    alt = "MT"
                elif chromosome == "MT" and "chrM" in chroms_in_bam:
                    alt = "chrM"
                if alt in chroms_in_bam:
                    logger.info(f"  BAM 中无 {chromosome}，使用 {alt}")
                    actual_chr = alt
        
        # 提取染色体
        cmd = f'samtools view -@ {self.threads} -bh "{bam_file}" {actual_chr} -o "{chr_bam}"'
        _run_cmd(cmd, f"提取 {chromosome}")
        
        # 建索引
        cmd = f'samtools index -@ {self.threads} "{chr_bam}"'
        _run_cmd(cmd, "建立索引")
        
        # 计算覆盖度
        coverage = self._calculate_coverage(chr_bam)
        logger.info(f"  {chromosome} 覆盖度: {coverage:.2f}x")
        
        # SNP calling
        snp_count = 0
        if call_snps:
            logger.info(f"  SNP calling...")
            cmd = (
                f'bcftools mpileup -f "{self.ref_genome}" --threads {self.threads} '
                f'-q 20 -Q 20 "{chr_bam}" | '
                f'bcftools call -mv --threads {self.threads} -Oz -o "{chr_vcf}"'
            )
            _run_cmd(cmd, "bcftools mpileup + call")
            
            # 建索引
            cmd = f'bcftools index "{chr_vcf}"'
            _run_cmd(cmd, "bcftools index")
            
            # 统计 SNP 数量
            result = subprocess.run(
                f'bcftools view -H "{chr_vcf}" | wc -l',
                shell=True, capture_output=True, text=True
            )
            snp_count = int(result.stdout.strip())
            logger.info(f"  {chromosome} SNP 数量: {snp_count}")
        
        return ChromosomeResult(
            bam_file=chr_bam,
            vcf_file=chr_vcf if call_snps else None,
            coverage=coverage,
            snp_count=snp_count,
        )
    
    def _calculate_coverage(self, bam_file: str) -> float:
        """计算覆盖度"""
        result = subprocess.run(
            f'samtools depth "{bam_file}" | awk \'{{sum+=$3; cnt++}} END {{if(cnt>0) printf "%.2f", sum/cnt; else print "0"}}\'',
            shell=True, capture_output=True, text=True
        )
        try:
            return float(result.stdout.strip())
        except:
            return 0.0
