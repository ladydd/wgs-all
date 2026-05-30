"""
PCA 分析模块 - 使用 smartpca 做主成分分析

流程:
    1. 用户提供: 样本 EIGENSTRAT + 参考人群 EIGENSTRAT
    2. mergeit 合并两个数据集
    3. PLINK LD pruning (去连锁不平衡)
    4. smartpca 计算 PCA
    5. 提取样本坐标 + 找最近参考人群

输入: EIGENSTRAT 三件套 (bam-to-eigenstrat 产出)
参考: 用户挂载的参考人群 EIGENSTRAT (如 AADR 子集)
输出: PCA 坐标 + 最近人群列表
"""

import os
import subprocess
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..core.logging import logger


@dataclass
class PCAResult:
    """PCA 结果"""
    sample_id: str
    pc_coordinates: Dict[str, float]  # {"PC1": x, "PC2": y, ...}
    evec_file: str                     # 特征向量文件
    eval_file: str                     # 特征值文件
    nearest_pops: List[Tuple[str, float]]  # [(人群名, 距离), ...]


def _find_tool(name: str) -> str:
    """查找工具"""
    for cand in [
        shutil.which(name),
        f"/home/ladydd/miniconda3/envs/ychr/bin/{name}",
        f"/usr/local/bin/{name}",
    ]:
        if cand and os.path.exists(cand):
            return cand
    raise FileNotFoundError(f"找不到工具: {name}")


class PCAAnalyzer:
    """
    PCA 主成分分析

    用法:
        analyzer = PCAAnalyzer()
        result = analyzer.run(
            sample_prefix="/data/my_sample",       # bam-to-eigenstrat 产出前缀
            reference_prefix="/data/ref/aadr_sub", # 参考人群 EIGENSTRAT 前缀
            output_dir="/data/pca_out",
            sample_id="MySample",
        )
    """

    def __init__(self):
        self.smartpca = _find_tool("smartpca")
        self.mergeit = _find_tool("mergeit")
        self.plink = _find_tool("plink")

    def run(
        self,
        sample_prefix: str,
        reference_prefix: str,
        output_dir: str,
        sample_id: Optional[str] = None,
        num_pcs: int = 10,
        num_threads: int = 4,
    ) -> PCAResult:
        """
        运行 PCA

        Args:
            sample_prefix: 样本 EIGENSTRAT 前缀 (需有 .geno/.snp/.ind)
            reference_prefix: 参考人群 EIGENSTRAT 前缀
            output_dir: 输出目录
            sample_id: 样本 ID (用于从结果中提取坐标)
            num_pcs: 计算多少个主成分
            num_threads: 线程数
        """
        os.makedirs(output_dir, exist_ok=True)

        # 验证输入
        for suffix in [".geno", ".snp", ".ind"]:
            for prefix in [sample_prefix, reference_prefix]:
                f = f"{prefix}{suffix}"
                if not os.path.exists(f):
                    raise FileNotFoundError(f"缺失: {f}")

        if sample_id is None:
            # 从 .ind 读第一个样本名
            with open(f"{sample_prefix}.ind") as f:
                sample_id = f.readline().split()[0]

        merged_prefix = os.path.join(output_dir, "merged")
        pca_prefix = os.path.join(output_dir, "pca")

        # Step 1: 合并样本和参考
        logger.info("Step 1: 合并样本与参考人群...")
        self._merge(sample_prefix, reference_prefix, merged_prefix)

        # Step 2: 跑 smartpca
        logger.info("Step 2: 运行 smartpca...")
        evec_file, eval_file = self._run_smartpca(
            merged_prefix, pca_prefix, num_pcs, num_threads
        )

        # Step 3: 提取样本坐标
        logger.info("Step 3: 提取样本 PCA 坐标...")
        coords, nearest = self._extract_results(evec_file, sample_id, num_pcs)

        return PCAResult(
            sample_id=sample_id,
            pc_coordinates=coords,
            evec_file=evec_file,
            eval_file=eval_file,
            nearest_pops=nearest,
        )

    def _merge(self, sample_prefix: str, ref_prefix: str, out_prefix: str):
        """用 mergeit 合并两个 EIGENSTRAT 数据集"""
        par_file = f"{out_prefix}.mergeit.par"
        with open(par_file, "w") as f:
            f.write(f"geno1: {sample_prefix}.geno\n")
            f.write(f"snp1: {sample_prefix}.snp\n")
            f.write(f"ind1: {sample_prefix}.ind\n")
            f.write(f"geno2: {ref_prefix}.geno\n")
            f.write(f"snp2: {ref_prefix}.snp\n")
            f.write(f"ind2: {ref_prefix}.ind\n")
            f.write(f"genooutfilename: {out_prefix}.geno\n")
            f.write(f"snpoutfilename: {out_prefix}.snp\n")
            f.write(f"indoutfilename: {out_prefix}.ind\n")
            f.write("allowdups: YES\n")
            f.write("hashcheck: NO\n")

        result = subprocess.run(
            [self.mergeit, "-p", par_file],
            capture_output=True, text=True
        )
        if not os.path.exists(f"{out_prefix}.geno"):
            raise RuntimeError(f"mergeit 失败:\n{result.stdout}\n{result.stderr}")

    def _run_smartpca(
        self, input_prefix: str, output_prefix: str, num_pcs: int, threads: int
    ) -> Tuple[str, str]:
        """运行 smartpca"""
        par_file = f"{output_prefix}.smartpca.par"
        evec_file = f"{output_prefix}.evec"
        eval_file = f"{output_prefix}.eval"

        with open(par_file, "w") as f:
            f.write(f"genotypename: {input_prefix}.geno\n")
            f.write(f"snpname: {input_prefix}.snp\n")
            f.write(f"indivname: {input_prefix}.ind\n")
            f.write(f"evecoutname: {evec_file}\n")
            f.write(f"evaloutname: {eval_file}\n")
            f.write(f"numoutevec: {num_pcs}\n")
            f.write("lsqproject: YES\n")
            f.write("numthreads: {}\n".format(threads))
            f.write("shrinkmode: YES\n")

        result = subprocess.run(
            [self.smartpca, "-p", par_file],
            capture_output=True, text=True
        )
        if not os.path.exists(evec_file):
            raise RuntimeError(f"smartpca 失败:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}")

        return evec_file, eval_file

    def _extract_results(
        self, evec_file: str, sample_id: str, num_pcs: int
    ) -> Tuple[Dict[str, float], List[Tuple[str, float]]]:
        """从 .evec 文件提取样本坐标和最近人群"""
        coords = {}
        all_coords = {}  # {sample: [pc1, pc2, ...]}

        with open(evec_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) < num_pcs + 2:
                    continue
                sid = parts[0].split(":")[0] if ":" in parts[0] else parts[0]
                pcs = [float(x) for x in parts[1:num_pcs + 1]]
                pop = parts[-1]
                all_coords[sid] = (pcs, pop)

                if sid == sample_id:
                    for i, v in enumerate(pcs):
                        coords[f"PC{i+1}"] = v

        # 计算欧氏距离找最近人群
        nearest = []
        if sample_id in all_coords:
            sample_pcs = all_coords[sample_id][0]
            for sid, (pcs, pop) in all_coords.items():
                if sid == sample_id:
                    continue
                dist = sum((a - b) ** 2 for a, b in zip(sample_pcs, pcs[:len(sample_pcs)])) ** 0.5
                nearest.append((f"{sid}({pop})", dist))
            nearest.sort(key=lambda x: x[1])
            nearest = nearest[:20]

        return coords, nearest
