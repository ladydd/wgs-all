"""
VCF 提取模块 - 从 VCF 文件直接生成芯片格式

当 BAM 覆盖度太低时，测序公司提供的 VCF 通常包含更多变异信息
（使用了 imputation 或其他方法），可以直接从 VCF 提取基因型
"""

import os
import gzip
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pyliftover import LiftOver

from ..core.config import settings
from ..core.logging import logger
from ..core.reference import reference_manager


def _process_genotype(ref: str, alt: str, gt: str) -> str:
    """
    从 VCF GT 字段生成基因型字符串
    
    Args:
        ref: 参考碱基
        alt: 替代碱基 (可能是 '.' 表示无变异)
        gt: GT 字段 (如 '0/0', '0/1', '1/1', './.')
    """
    if gt in ('./.', '.|.', '.'):
        return '--'
    
    alleles = [ref]
    if alt and alt != '.':
        alleles.extend(alt.split(','))
    
    sep = '/' if '/' in gt else '|'
    parts = gt.split(sep)
    if len(parts) != 2:
        return '--'
    
    try:
        a1_idx = int(parts[0])
        a2_idx = int(parts[1])
    except (ValueError, IndexError):
        return '--'
    
    if a1_idx >= len(alleles) or a2_idx >= len(alleles):
        return '--'
    
    a1 = alleles[a1_idx]
    a2 = alleles[a2_idx]
    
    # 只处理 SNP (单碱基)
    if len(a1) != 1 or len(a2) != 1:
        return '--'
    
    geno = a1 + a2
    
    # 排序 (WGSExtract 风格)
    if geno in ('TA', 'TC', 'TG', 'GA', 'GC', 'CA'):
        geno = geno[::-1]
    
    return geno


class VcfChipExtractor:
    """
    从 VCF 文件直接提取芯片格式
    
    流程:
    1. 加载 SNP 注释文件 (rsID + 位置映射)
    2. 解析 VCF 基因型
    3. LiftOver 到 hg19
    4. 生成 CombinedKit 和各芯片格式
    """
    
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
    
    def __init__(self, reference_dir: Optional[Path] = None, reference: str = "hg38"):
        self.reference_dir = reference_dir or settings.reference_dir
        # T2T 常染色体坐标与 hg38 兼容，走 hg38 流程
        if reference == "t2t":
            reference = "hg38"
        self.reference = reference
        self.microarray_dir = self.reference_dir / "microarray"
        self.templates_dir = self.microarray_dir / "raw_file_templates"
        
        if reference == "hg19":
            # hg19 VCF 不需要 liftOver（芯片模板本身就是 hg19 坐标）
            self._liftover = None
        else:
            chain_file = reference_manager.get_liftover_chain("hg38", "hg19")
            if chain_file and chain_file.exists():
                self._liftover = LiftOver(str(chain_file))
            else:
                logger.warning("LiftOver chain 文件不存在，将从网络下载")
                self._liftover = LiftOver('hg38', 'hg19')
    
    def _load_snp_annotation(self) -> Dict[Tuple[str, str], str]:
        """加载 SNP 注释文件，建立 (chrom, pos) -> rsID 映射"""
        if self.reference == "hg19":
            snp_file = self.microarray_dir / "All_SNPs_hg19_ref.tab.gz"
        else:
            snp_file = self.microarray_dir / "All_SNPs_hg38_ref.tab.gz"
        if not snp_file.exists():
            raise FileNotFoundError(f"SNP 注释文件不存在: {snp_file}")
        
        logger.info(f"加载 SNP 注释: {snp_file}")
        snp_map = {}
        
        with gzip.open(snp_file, 'rt') as f:
            for line in f:
                if line.startswith('#'):
                    continue
                parts = line.strip().split('\t')
                if len(parts) >= 3:
                    chrom = parts[0].replace('chr', '')
                    pos = parts[1]
                    rsid = parts[2]
                    if rsid and rsid != '.':
                        snp_map[(chrom, pos)] = rsid
        
        logger.info(f"  加载 {len(snp_map)} 个 SNP 注释")
        return snp_map
    
    def _parse_vcf(self, vcf_file: str) -> Dict[Tuple[str, str], Tuple[str, str]]:
        """解析 VCF 文件，返回 (chrom, pos) -> (rsid, genotype) 映射"""
        logger.info(f"解析 VCF: {vcf_file}")
        
        genotypes = {}
        opener = gzip.open if vcf_file.endswith('.gz') else open
        
        with opener(vcf_file, 'rt') as f:
            for line in f:
                if line.startswith('#'):
                    continue
                
                parts = line.strip().split('\t')
                if len(parts) < 10:
                    continue
                
                chrom = parts[0].replace('chr', '')
                if chrom == 'M':
                    chrom = 'MT'
                pos = parts[1]
                rsid = parts[2]
                ref = parts[3]
                alt = parts[4]
                
                # 只处理 SNP
                if len(ref) != 1:
                    continue
                if alt != '.' and any(len(a) != 1 for a in alt.split(',')):
                    continue
                
                # 解析基因型
                format_field = parts[8]
                sample_field = parts[9]
                
                fmt_keys = format_field.split(':')
                fmt_vals = sample_field.split(':')
                
                gt_idx = fmt_keys.index('GT') if 'GT' in fmt_keys else -1
                if gt_idx < 0 or gt_idx >= len(fmt_vals):
                    continue
                
                gt = fmt_vals[gt_idx]
                geno = _process_genotype(ref, alt, gt)
                
                genotypes[(chrom, pos)] = (rsid, geno)
        
        logger.info(f"  解析 {len(genotypes)} 个 SNP")
        return genotypes
    
    def extract(
        self,
        vcf_file: str,
        output_dir: str,
        sample_id: str,
        formats: Optional[List[str]] = None,
    ) -> dict:
        """
        从 VCF 提取芯片格式文件
        
        Args:
            vcf_file: 输入 VCF 文件
            output_dir: 输出目录
            sample_id: 样本 ID
            formats: 要生成的格式列表
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Step 1: 加载 SNP 注释
        snp_map = self._load_snp_annotation()
        
        # Step 2: 解析 VCF
        vcf_genotypes = self._parse_vcf(vcf_file)
        
        # Step 3: 匹配 rsID + LiftOver
        logger.info("Step 3: 匹配 rsID + 坐标转换...")
        matched = {}
        matched_count = 0
        no_rsid_count = 0
        
        for (chrom, pos), (vcf_rsid, geno) in vcf_genotypes.items():
            if geno == '--':
                continue
            
            rsid = snp_map.get((chrom, pos), vcf_rsid)
            if rsid == '.' or not rsid:
                no_rsid_count += 1
                continue
            
            if self._liftover:
                # hg38 VCF: LiftOver hg38 -> hg19
                old_chrom = f"chr{chrom}".replace('chrMT', 'chrM')
                try:
                    new_coord = self._liftover.convert_coordinate(old_chrom, int(pos))
                    if new_coord and len(new_coord) > 0:
                        new_chrom = new_coord[0][0].replace('chr', '')
                        if new_chrom == 'M':
                            new_chrom = 'MT'
                        new_pos = str(int(new_coord[0][1]))
                        matched[(new_chrom, new_pos)] = (rsid, geno)
                        matched_count += 1
                except Exception:
                    continue
            else:
                # hg19 VCF: 坐标已经是 hg19，直接用
                matched[(chrom, pos)] = (rsid, geno)
                matched_count += 1
        
        logger.info(f"  匹配成功: {matched_count}, 无 rsID: {no_rsid_count}")
        
        # Step 4: 排序并创建 CombinedKit
        logger.info("Step 4: 创建 CombinedKit...")
        combined_kit = Path(output_dir) / f"{sample_id}_CombinedKit.txt"
        
        def sort_key(item):
            chrom, pos = item[0]
            if chrom.isdigit():
                cn = int(chrom)
            elif chrom == 'X':
                cn = 23
            elif chrom == 'Y':
                cn = 24
            elif chrom == 'MT':
                cn = 25
            else:
                cn = 99
            return (cn, int(pos))
        
        sorted_items = sorted(matched.items(), key=sort_key)
        
        head_file = self.templates_dir / "head" / "23andMe_V3.txt"
        with open(combined_kit, 'w') as out:
            if head_file.exists():
                with open(head_file, 'r') as h:
                    out.write(h.read())
            for (chrom, pos), (rsid, geno) in sorted_items:
                out.write(f"{rsid}\t{chrom}\t{pos}\t{geno}\n")
        
        logger.info(f"  CombinedKit: {len(sorted_items)} 位点")
        
        # Step 5: 创建各芯片格式
        logger.info("Step 5: 创建芯片格式...")
        genotype_lookup = {}
        for (chrom, pos), (rsid, geno) in sorted_items:
            genotype_lookup[(chrom, pos)] = (rsid, geno)
        
        results = []
        for fmt, suffix in self.FORMATS:
            if formats and fmt not in formats:
                continue
            
            body_file = self.templates_dir / "body" / f"{fmt}{suffix}"
            head_file = self.templates_dir / "head" / f"{fmt}{suffix}"
            
            if not body_file.exists():
                continue
            
            output_file = Path(output_dir) / f"{sample_id}_{fmt}{suffix}"
            total, has_geno = self._create_subset(
                genotype_lookup, str(body_file), str(output_file),
                str(head_file) if head_file.exists() else None
            )
            results.append({
                "format": fmt,
                "file": str(output_file),
                "total": total,
                "with_genotype": has_geno,
                "rate": f"{100*has_geno/total:.1f}%" if total > 0 else "0%",
            })
        
        logger.info(f"完成! 文件保存在: {output_dir}")
        return {
            "vcf_snps": len(vcf_genotypes),
            "matched": matched_count,
            "formats": results,
        }
    
    def _create_subset(
        self,
        genotype_lookup: dict,
        template_body: str,
        output_file: str,
        head_file: Optional[str],
    ) -> Tuple[int, int]:
        """从模板创建子集文件"""
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
                        
                        if (chrom, pos) in genotype_lookup:
                            _, geno = genotype_lookup[(chrom, pos)]
                            if geno and geno != '--':
                                has_geno += 1
                        
                        if is_csv:
                            out.write(f'"{rsid}","{chrom}","{pos}","{geno}"\n')
                        else:
                            out.write(f"{rsid}\t{chrom}\t{pos}\t{geno}\n")
                        count += 1
        
        logger.info(f"  {os.path.basename(output_file)}: {count} 位点, {has_geno} 有基因型")
        return (count, has_geno)
