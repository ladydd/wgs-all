"""
SNP 文件提取模块 - 从测序公司的 .snp 文件直接生成芯片格式

.snp 文件格式:
#rsid    chromosome    position    genotype
rs12345  1             12345       AG

这种文件通常是测序公司 imputation 后的结果，包含大量 SNP 和基因型
直接用 rsID 匹配芯片模板，不需要坐标转换
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..core.config import settings
from ..core.logging import logger


class SnpChipExtractor:
    """
    从 .snp 文件直接生成芯片格式
    
    用 rsID 匹配芯片模板，简单高效
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
    
    def __init__(self, reference_dir: Optional[Path] = None):
        self.reference_dir = reference_dir or settings.reference_dir
        self.templates_dir = self.reference_dir / "microarray" / "raw_file_templates"
    
    def _load_snp_file(self, snp_file: str) -> Dict[str, Tuple[str, str, str]]:
        """
        加载 .snp 文件，建立 rsID -> (chrom, pos, genotype) 映射
        """
        logger.info(f"加载 SNP 文件: {snp_file}")
        snp_map = {}
        
        with open(snp_file, 'r') as f:
            for line in f:
                if line.startswith('#'):
                    continue
                parts = line.strip().split('\t')
                if len(parts) >= 4:
                    rsid = parts[0]
                    chrom = parts[1]
                    pos = parts[2]
                    geno = parts[3]
                    
                    # 排序基因型
                    if len(geno) == 2 and geno != '--':
                        if geno in ('TA', 'TC', 'TG', 'GA', 'GC', 'CA'):
                            geno = geno[::-1]
                    
                    snp_map[rsid] = (chrom, pos, geno)
        
        has_geno = sum(1 for v in snp_map.values() if v[2] != '--')
        logger.info(f"  加载 {len(snp_map)} 个 SNP, {has_geno} 有基因型")
        return snp_map
    
    def extract(
        self,
        snp_file: str,
        output_dir: str,
        sample_id: str,
        formats: Optional[List[str]] = None,
    ) -> dict:
        """
        从 .snp 文件生成芯片格式
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 加载 SNP 数据
        snp_map = self._load_snp_file(snp_file)
        
        # 创建 CombinedKit (用模板的坐标，填入基因型)
        logger.info("创建 CombinedKit...")
        combined_kit = Path(output_dir) / f"{sample_id}_CombinedKit.txt"
        head_file = self.templates_dir / "head" / "23andMe_V3.txt"
        
        with open(combined_kit, 'w') as out:
            if head_file.exists():
                with open(head_file, 'r') as h:
                    out.write(h.read())
            # 写入所有有基因型的 SNP
            for rsid, (chrom, pos, geno) in sorted(
                snp_map.items(),
                key=lambda x: (
                    int(x[1][0]) if x[1][0].isdigit() else 99,
                    int(x[1][1])
                )
            ):
                if geno != '--':
                    out.write(f"{rsid}\t{chrom}\t{pos}\t{geno}\n")
        
        # 创建各芯片格式 (用 rsID 匹配)
        logger.info("创建芯片格式...")
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
                snp_map, str(body_file), str(output_file),
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
        return {"total_snps": len(snp_map), "formats": results}
    
    def _create_subset(
        self,
        snp_map: dict,
        template_body: str,
        output_file: str,
        head_file: Optional[str],
    ) -> Tuple[int, int]:
        """用 rsID 匹配模板，生成芯片文件"""
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
                        rsid = parts[0]
                        chrom = parts[1]
                        pos = parts[2]
                        geno = '--'
                        
                        # 用 rsID 匹配
                        if rsid in snp_map:
                            _, _, geno = snp_map[rsid]
                            if geno and geno != '--':
                                has_geno += 1
                        
                        if is_csv:
                            out.write(f'"{rsid}","{chrom}","{pos}","{geno}"\n')
                        else:
                            out.write(f"{rsid}\t{chrom}\t{pos}\t{geno}\n")
                        count += 1
        
        logger.info(f"  {os.path.basename(output_file)}: {count} 位点, {has_geno} 有基因型")
        return (count, has_geno)
