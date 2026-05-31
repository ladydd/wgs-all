"""
提取模块 - 芯片格式导出和 1240K 位点提取

封装自:
- extract_chip_format_v2.py
- extract_1240k.py
"""

import os
import gzip
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from pyliftover import LiftOver

from ..core.config import settings
from ..core.logging import logger
from ..core.reference import reference_manager


@dataclass
class ChipFormatResult:
    """芯片格式提取结果"""
    format_type: str
    file_path: str
    total_positions: int
    positions_with_genotype: int
    
    @property
    def genotype_rate(self) -> float:
        if self.total_positions == 0:
            return 0.0
        return self.positions_with_genotype / self.total_positions


@dataclass
class K1240Result:
    """1240K 提取结果"""
    file_path: str
    total_positions: int
    positions_with_genotype: int
    
    @property
    def genotype_rate(self) -> float:
        if self.total_positions == 0:
            return 0.0
        return self.positions_with_genotype / self.total_positions


def _run_cmd(cmd: str, desc: str = "") -> subprocess.CompletedProcess:
    """运行命令并检查结果"""
    if desc:
        logger.info(f"  {desc}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"命令失败: {result.stderr}")
        raise RuntimeError(f"Command failed: {cmd}\n{result.stderr}")
    return result


def _process_genotype(geno: str) -> str:
    """
    处理基因型格式
    A/G -> AG, ./. -> --
    排序: TA->AT, TC->CT, TG->GT, GA->AG, GC->CG, CA->AC
    """
    geno = geno.replace('/', '').replace('.', '-')
    if geno == '--' or geno == '':
        return '--'
    
    # 排序基因型 (WGSExtract 风格)
    if len(geno) == 2 and geno != '--':
        if geno in ['TA', 'TC', 'TG', 'GA', 'GC', 'CA']:
            geno = geno[::-1]
    
    return geno


class ChipFormatExtractor:
    """
    芯片格式提取器
    
    从 BAM 文件提取基因型，生成各种芯片格式文件
    支持: CombinedKit, 23andMe, Ancestry, FTDNA, MyHeritage, LDNA
    """
    
    # 支持的芯片格式
    FORMATS = [
        ("23andMe_V3", ".txt"),
        ("23andMe_V5", ".txt"),
        ("23andMe_V35", ".txt"),
        ("Ancestry_V1", ".txt"),
        ("Ancestry_V2", ".txt"),
        ("FTDNA_V2", ".csv"),
        ("FTDNA_V3", ".csv"),
        ("LDNA_V1", ".txt"),
        ("LDNA_V2", ".txt"),
        ("MyHeritage_V1", ".csv"),
        ("MyHeritage_V2", ".csv"),
    ]
    
    def __init__(
        self,
        reference_dir: Optional[Path] = None,
        threads: int = None,
        reference: str = "hg38",
    ):
        self.reference_dir = reference_dir or settings.reference_dir
        self.threads = threads or settings.threads
        self.reference = reference
        # T2T 走 hg38 流程
        if reference == "t2t":
            self.reference = "hg38"
        self.microarray_dir = self.reference_dir / "microarray"
        self.templates_dir = self.microarray_dir / "raw_file_templates"
        
        # hg19 不需要 liftOver
        if self.reference == "hg19":
            self._liftover = None
        else:
            chain_file = reference_manager.get_liftover_chain("hg38", "hg19")
            if chain_file and chain_file.exists():
                self._liftover = LiftOver(str(chain_file))
            else:
                logger.warning("LiftOver chain 文件不存在，将从网络下载")
                self._liftover = LiftOver('hg38', 'hg19')
    
    def extract(
        self,
        bam_file: str,
        output_dir: str,
        sample_id: str,
        formats: Optional[List[str]] = None,
    ) -> List[ChipFormatResult]:
        """
        从 BAM 提取芯片格式文件
        
        Args:
            bam_file: 输入 BAM 文件路径
            output_dir: 输出目录
            sample_id: 样本 ID
            formats: 要生成的格式列表，None 表示全部
        
        Returns:
            ChipFormatResult 列表
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 临时文件
        temp_dir = Path("/tmp")
        raw_tab = temp_dir / f"{sample_id}_raw.tab"
        lifted_tab = temp_dir / f"{sample_id}_lifted.tab"
        sorted_tab = temp_dir / f"{sample_id}_sorted.tab"
        
        try:
            # Step 1: 从 BAM 提取基因型
            logger.info("Step 1: 从 BAM 提取基因型...")
            if self.reference == "hg19":
                ref_vcf = self.microarray_dir / "All_SNPs_hg19_ref.tab.gz"
                ref_genome = reference_manager.get_genome_path("hg19")
            else:
                ref_vcf = self.microarray_dir / "All_SNPs_hg38_ref.tab.gz"
                ref_genome = reference_manager.get_genome_path("hg38")
            self._extract_genotypes_from_bam(bam_file, str(ref_vcf), str(ref_genome), str(raw_tab))
            
            # Step 2: LiftOver (hg38 需要转 hg19，hg19 跳过)
            if self._liftover:
                logger.info("Step 2: 坐标转换 hg38 -> hg19...")
                self._liftover_to_hg19(str(raw_tab), str(lifted_tab))
            else:
                logger.info("Step 2: hg19 BAM，跳过 LiftOver")
                lifted_tab = raw_tab
            
            # Step 3: 排序
            logger.info("Step 3: 排序...")
            self._sort_tab_file(str(lifted_tab), str(sorted_tab))
            
            # Step 4: 创建 CombinedKit
            logger.info("Step 4: 创建 CombinedKit...")
            combined_kit = Path(output_dir) / f"{sample_id}_CombinedKit.txt"
            head_file = self.templates_dir / "head" / "23andMe_V3.txt"
            self._create_combined_kit(str(sorted_tab), str(combined_kit), str(head_file))
            
            # Step 5: 创建其他格式
            logger.info("Step 5: 创建其他芯片格式...")
            results = []
            
            for fmt, suffix in self.FORMATS:
                if formats and fmt not in formats:
                    continue
                
                body_file = self.templates_dir / "body" / f"{fmt}{suffix}"
                head_file = self.templates_dir / "head" / f"{fmt}{suffix}"
                
                if body_file.exists():
                    output_file = Path(output_dir) / f"{sample_id}_{fmt}{suffix}"
                    result = self._create_subset_file(
                        str(combined_kit), str(body_file), str(output_file),
                        str(head_file) if head_file.exists() else None
                    )
                    results.append(ChipFormatResult(
                        format_type=fmt,
                        file_path=str(output_file),
                        total_positions=result[0],
                        positions_with_genotype=result[1],
                    ))
            
            logger.info(f"完成! 文件保存在: {output_dir}")
            return results
            
        finally:
            # 清理临时文件 (可选保留用于调试)
            # for f in [raw_tab, lifted_tab, sorted_tab]:
            #     if f.exists():
            #         f.unlink()
            pass
    
    def _extract_genotypes_from_bam(
        self, bam_file: str, ref_vcf: str, ref_genome: str, output_tab: str
    ):
        """从 BAM 提取基因型"""
        temp_called = output_tab.replace('.tab', '_called.vcf.gz')
        temp_annotated = output_tab.replace('.tab', '_annotated.vcf.gz')
        
        # mpileup + call
        cmd = (
            f"bcftools mpileup -B -I -C 50 -T {ref_vcf} -f {ref_genome} -Ou {bam_file} | "
            f"bcftools call -V indels -m -P 0 --threads {self.threads} -Oz -o {temp_called}"
        )
        _run_cmd(cmd, "bcftools mpileup + call")
        _run_cmd(f"tabix -p vcf {temp_called}", "建立索引")
        
        # annotate (添加 rsID)
        cmd = f"bcftools annotate -Oz -a {ref_vcf} -c CHROM,POS,ID {temp_called} > {temp_annotated}"
        _run_cmd(cmd, "bcftools annotate")
        _run_cmd(f"tabix -p vcf {temp_annotated}")
        
        # query 导出
        cmd = f"bcftools query -f '%ID\\t%CHROM\\t%POS[\\t%TGT]\\n' {temp_annotated} -o {output_tab}"
        _run_cmd(cmd, "导出基因型")
        
        # 清理
        for f in [temp_called, temp_called + '.tbi', temp_annotated, temp_annotated + '.tbi']:
            if os.path.exists(f):
                os.remove(f)
    
    def _liftover_to_hg19(self, input_tab: str, output_tab: str):
        """坐标转换 hg38 -> hg19"""
        valid_chroms = set([str(i) for i in range(1, 23)] + ['X', 'Y', 'MT'])
        converted = 0
        failed = 0
        
        with open(output_tab, 'w') as out:
            with open(input_tab, 'r') as f:
                for line in f:
                    if line.startswith('#'):
                        continue
                    
                    parts = line.strip().split('\t')
                    if len(parts) < 4:
                        continue
                    
                    rsid, chrom, pos, geno = parts[0], parts[1], parts[2], parts[3]
                    
                    # 处理染色体名称
                    chrom = chrom.replace('chr', '')
                    if chrom == 'M':
                        chrom = 'MT'
                    
                    # 处理基因型
                    geno = _process_genotype(geno)
                    
                    # 转换坐标
                    old_chrom = f"chr{chrom}".replace('chrMT', 'chrM')
                    try:
                        new_coord = self._liftover.convert_coordinate(old_chrom, int(pos))
                        if new_coord and len(new_coord) > 0:
                            new_chrom = new_coord[0][0].replace('chr', '')
                            if new_chrom == 'M':
                                new_chrom = 'MT'
                            new_pos = new_coord[0][1]
                            if new_chrom in valid_chroms:
                                out.write(f"{rsid}\t{new_chrom}\t{new_pos}\t{geno}\n")
                                converted += 1
                            else:
                                failed += 1
                        else:
                            failed += 1
                    except Exception:
                        failed += 1
        
        logger.info(f"  转换完成: {converted} 成功, {failed} 失败")
    
    def _sort_tab_file(self, input_tab: str, output_tab: str):
        """按染色体和位置排序"""
        lines = []
        with open(input_tab, 'r') as f:
            lines = f.readlines()
        
        def sort_key(line):
            parts = line.strip().split('\t')
            if len(parts) < 3:
                return (999, 0)
            chrom = parts[1]
            try:
                pos = int(parts[2])
            except:
                pos = 0
            if chrom.isdigit():
                chrom_num = int(chrom)
            elif chrom == 'X':
                chrom_num = 23
            elif chrom == 'Y':
                chrom_num = 24
            elif chrom == 'MT':
                chrom_num = 25
            else:
                chrom_num = 99
            return (chrom_num, pos)
        
        lines.sort(key=sort_key)
        
        with open(output_tab, 'w') as f:
            f.writelines(lines)
        
        logger.info(f"  排序完成，{len(lines)} 行")
    
    def _create_combined_kit(self, sorted_tab: str, output_file: str, head_file: str):
        """创建 CombinedKit"""
        with open(output_file, 'w') as out:
            if os.path.exists(head_file):
                with open(head_file, 'r') as h:
                    out.write(h.read())
            with open(sorted_tab, 'r') as f:
                out.write(f.read())
    
    def _create_subset_file(
        self, combined_kit: str, template_body: str, output_file: str, head_file: Optional[str]
    ) -> Tuple[int, int]:
        """从 CombinedKit 创建子集文件"""
        # 加载 CombinedKit
        genotypes = {}
        with open(combined_kit, 'r') as f:
            for line in f:
                if line.startswith('#'):
                    continue
                parts = line.strip().split('\t')
                if len(parts) >= 4:
                    chrom, pos = parts[1], parts[2]
                    genotypes[(chrom, pos)] = (parts[0], parts[3])
        
        is_csv = template_body.endswith('.csv')
        count = 0
        has_geno = 0
        
        with open(output_file, 'w') as out:
            if head_file and os.path.exists(head_file):
                with open(head_file, 'r') as h:
                    out.write(h.read())
            
            with open(template_body, 'r') as f:
                for line in f:
                    line = line.strip().replace('"', '')
                    parts = line.split(',') if is_csv else line.split('\t')
                    
                    if len(parts) >= 3:
                        rsid, chrom, pos = parts[0], parts[1], parts[2]
                        geno = '--'
                        if (chrom, pos) in genotypes:
                            _, geno = genotypes[(chrom, pos)]
                            if geno and geno != '--':
                                has_geno += 1
                        
                        if is_csv:
                            out.write(f'"{rsid}","{chrom}","{pos}","{geno}"\n')
                        else:
                            out.write(f"{rsid}\t{chrom}\t{pos}\t{geno}\n")
                        count += 1
        
        logger.info(f"  {os.path.basename(output_file)}: {count} 位点, {has_geno} 有基因型")
        return (count, has_geno)


class K1240Extractor:
    """
    1240K 位点提取器
    
    从 BAM 文件提取 1240K 位点的基因型，用于古 DNA 分析 (G25, qpAdm)
    输出 hg38 坐标
    """
    
    def __init__(
        self,
        k1240_file: Optional[Path] = None,
        threads: int = None,
    ):
        self.k1240_file = k1240_file or reference_manager.get_1240k_file()
        self.threads = threads or settings.threads
        self._positions: Dict[Tuple[str, str], str] = {}
    
    def _load_positions(self):
        """加载 1240K 位点列表"""
        if self._positions:
            return
        
        valid_chroms = set([f"chr{i}" for i in range(1, 23)] + ['chrX', 'chrY', 'chrM'])
        
        opener = gzip.open if str(self.k1240_file).endswith('.gz') else open
        with opener(self.k1240_file, 'rt') as f:
            for line in f:
                if line.startswith('#'):
                    continue
                parts = line.strip().split('\t')
                if len(parts) >= 3:
                    chrom, pos, rsid = parts[0], parts[1], parts[2]
                    if not chrom.startswith('chr'):
                        chrom = f"chr{chrom}"
                    if chrom in valid_chroms:
                        self._positions[(chrom, pos)] = rsid
        
        logger.info(f"加载 1240K 位点: {len(self._positions)} 个")
    
    def extract(self, bam_file: str, output_file: str) -> K1240Result:
        """
        从 BAM 提取 1240K 位点
        
        Args:
            bam_file: 输入 BAM 文件
            output_file: 输出文件路径
        
        Returns:
            K1240Result
        """
        self._load_positions()
        
        ref_genome = reference_manager.get_genome_path("hg38")
        
        # 创建临时 BED 文件
        bed_file = output_file + '.bed'
        with open(bed_file, 'w') as f:
            for (chrom, pos), rsid in sorted(
                self._positions.items(), key=lambda x: (x[0][0], int(x[0][1]))
            ):
                start = int(pos) - 1  # BED 是 0-based
                f.write(f"{chrom}\t{start}\t{pos}\t{rsid}\n")
        
        logger.info(f"创建 BED 文件: {len(self._positions)} 个位点")
        
        # bcftools mpileup + call
        temp_vcf = output_file + '.vcf.gz'
        cmd = (
            f"bcftools mpileup -B -I -C 50 -R {bed_file} -f {ref_genome} -Ou {bam_file} | "
            f"bcftools call -V indels -m -P 0 --threads {self.threads} -Oz -o {temp_vcf}"
        )
        _run_cmd(cmd, "bcftools mpileup + call")
        
        # 解析 VCF
        logger.info("解析基因型...")
        genotypes = {}
        cmd = f"bcftools query -f '%CHROM\\t%POS[\\t%TGT]\\n' {temp_vcf}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) >= 3:
                chrom, pos, geno = parts[0], parts[1], parts[2]
                geno = _process_genotype(geno)
                genotypes[(chrom, pos)] = geno
        
        # 清理临时文件
        os.remove(bed_file)
        os.remove(temp_vcf)
        
        # 写入输出
        has_geno = 0
        with open(output_file, 'w') as f:
            f.write("# 1240K format for ancient DNA analysis\n")
            f.write("# Coordinates: GRCh38/hg38\n")
            f.write("# rsid\tchrom\tpos\tgenotype\n")
            
            for (chrom, pos), rsid in sorted(
                self._positions.items(), key=lambda x: (x[0][0], int(x[0][1]))
            ):
                geno = genotypes.get((chrom, pos), '--')
                chrom_out = chrom.replace('chr', '')
                if chrom_out == 'M':
                    chrom_out = 'MT'
                f.write(f"{rsid}\t{chrom_out}\t{pos}\t{geno}\n")
                if geno != '--':
                    has_geno += 1
        
        logger.info(f"完成! {len(self._positions)} 位点, {has_geno} 有基因型 ({100*has_geno/len(self._positions):.1f}%)")
        
        return K1240Result(
            file_path=output_file,
            total_positions=len(self._positions),
            positions_with_genotype=has_geno,
        )
