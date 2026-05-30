"""
群体遗传分析模块 - 常染色体祖源分析

功能:
1. PLINK 格式转换 (1240K/芯片 → .bed/.bim/.fam)
2. PCA 分析 (与现代人群对比)
3. ADMIXTURE 祖源成分分析
4. G25 坐标计算
5. qpAdm 祖源建模

依赖:
- plink (v1.9 或 v2.0)
- admixture
- smartpca (EIGENSOFT)
"""

import os
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..core.config import settings
from ..core.logging import logger
from ..core.reference import reference_manager


# ===== 数据模型 =====

@dataclass
class PlinkConvertResult:
    """PLINK 格式转换结果"""
    bed_file: str       # .bed 文件路径
    bim_file: str       # .bim 文件路径
    fam_file: str       # .fam 文件路径
    total_snps: int     # 总 SNP 数
    total_samples: int  # 样本数


@dataclass
class PCAResult:
    """PCA 分析结果"""
    output_dir: str
    evec_file: str          # 特征向量文件 (坐标)
    eval_file: str          # 特征值文件 (方差解释)
    plot_file: Optional[str]  # PCA 散点图 (如果生成了)
    pc1: float              # 样本的 PC1 坐标
    pc2: float              # 样本的 PC2 坐标
    variance_explained: List[float]  # 各 PC 的方差解释比例
    nearest_populations: List[dict]  # 最近的参考人群


@dataclass
class AdmixtureResult:
    """ADMIXTURE 分析结果"""
    output_dir: str
    k: int                          # 祖源成分数
    q_file: str                     # .Q 文件 (成分比例)
    p_file: str                     # .P 文件 (等位基因频率)
    components: Dict[str, float]    # {成分名: 比例}
    cv_error: float                 # 交叉验证误差


@dataclass
class G25Result:
    """G25 坐标计算结果"""
    coordinates: List[float]    # 25 维坐标
    output_file: str
    nearest_ancient: List[dict]  # 最近的古代样本
    nearest_modern: List[dict]   # 最近的现代人群


@dataclass
class QpAdmResult:
    """qpAdm 祖源建模结果"""
    output_file: str
    target: str                     # 目标样本
    sources: List[str]              # 源人群
    proportions: Dict[str, float]   # {源人群: 比例}
    std_errors: Dict[str, float]    # {源人群: 标准误}
    p_value: float                  # 模型 p 值
    feasible: bool                  # 模型是否可行 (p > 0.05)


def _run_cmd(cmd: str, desc: str = "") -> subprocess.CompletedProcess:
    """运行命令"""
    if desc:
        logger.info(f"  {desc}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"命令失败: {result.stderr}")
        raise RuntimeError(f"Command failed: {cmd}\n{result.stderr}")
    return result


# ===== PLINK 格式转换 =====

class PlinkConverter:
    """
    PLINK 格式转换器

    将 1240K 或芯片格式数据转换为 PLINK 二进制格式 (.bed/.bim/.fam)
    """

    def __init__(self, plink_path: Optional[str] = None):
        self.plink = plink_path or "plink"
        # TODO: 验证 plink 可用

    def from_1240k(
        self,
        input_file: str,
        output_prefix: str,
        sample_id: str,
    ) -> PlinkConvertResult:
        """
        1240K 格式 → PLINK

        Args:
            input_file: 1240K 提取结果文件 (rsid, chrom, pos, genotype)
            output_prefix: 输出文件前缀
            sample_id: 样本 ID
        """
        # TODO: 实现
        # 1. 解析 1240K 文件
        # 2. 生成 .ped + .map
        # 3. plink --file xxx --make-bed --out xxx
        raise NotImplementedError("PLINK 格式转换待实现")

    def from_chip_format(
        self,
        input_file: str,
        output_prefix: str,
        sample_id: str,
        chip_type: str = "23andMe_V5",
    ) -> PlinkConvertResult:
        """
        芯片格式 → PLINK

        Args:
            input_file: 芯片格式文件
            output_prefix: 输出文件前缀
            sample_id: 样本 ID
            chip_type: 芯片类型
        """
        # TODO: 实现
        raise NotImplementedError("芯片格式转 PLINK 待实现")

    def merge_with_reference(
        self,
        sample_prefix: str,
        reference_prefix: str,
        output_prefix: str,
    ) -> PlinkConvertResult:
        """
        将样本与参考人群数据合并

        Args:
            sample_prefix: 样本 PLINK 文件前缀
            reference_prefix: 参考人群 PLINK 文件前缀
            output_prefix: 合并后输出前缀
        """
        # TODO: 实现
        # plink --bfile sample --bmerge reference --make-bed --out merged
        raise NotImplementedError("PLINK 合并待实现")


# ===== PCA 分析 =====

class PCAAnalyzer:
    """
    PCA 主成分分析

    将样本投影到参考人群的 PCA 空间中，
    看样本跟哪些人群最接近
    """

    def __init__(
        self,
        reference_dataset: Optional[str] = None,
        n_components: int = 10,
    ):
        """
        Args:
            reference_dataset: 参考人群 PLINK 数据集前缀
            n_components: 计算多少个主成分
        """
        self.reference_dataset = reference_dataset
        self.n_components = n_components

    def analyze(
        self,
        sample_plink_prefix: str,
        output_dir: str,
        sample_id: str,
    ) -> PCAResult:
        """
        运行 PCA 分析

        流程:
        1. 合并样本与参考人群
        2. LD pruning (去除连锁不平衡)
        3. 运行 smartpca 或 plink --pca
        4. 提取样本坐标
        5. 找最近的参考人群
        """
        # TODO: 实现
        raise NotImplementedError("PCA 分析待实现")

    def _find_nearest_populations(
        self,
        sample_coords: List[float],
        ref_coords: Dict[str, List[float]],
        top_n: int = 10,
    ) -> List[dict]:
        """计算样本与各参考人群的欧氏距离，返回最近的 N 个"""
        # TODO: 实现
        raise NotImplementedError


# ===== ADMIXTURE 分析 =====

class AdmixtureAnalyzer:
    """
    ADMIXTURE 祖源成分分析

    估算样本的祖源成分比例
    支持多个 K 值 (成分数)
    """

    # 常用计算器对应的 K 值和参考数据
    CALCULATORS = {
        "K13_Eurogenes": {"k": 13, "dataset": "eurogenes_k13"},
        "K47_Dodecad": {"k": 47, "dataset": "dodecad_k47"},
        "E11_Eurogenes": {"k": 11, "dataset": "eurogenes_e11"},
        "K12_HarappaWorld": {"k": 12, "dataset": "harappa_k12"},
        "K7_MDLP": {"k": 7, "dataset": "mdlp_k7"},
    }

    def __init__(self, admixture_path: Optional[str] = None):
        self.admixture = admixture_path or "admixture"

    def analyze(
        self,
        sample_plink_prefix: str,
        output_dir: str,
        sample_id: str,
        calculator: str = "K13_Eurogenes",
    ) -> AdmixtureResult:
        """
        运行 ADMIXTURE 分析

        Args:
            sample_plink_prefix: 样本 PLINK 文件前缀
            output_dir: 输出目录
            sample_id: 样本 ID
            calculator: 计算器名称
        """
        # TODO: 实现
        # 1. 合并样本与计算器参考数据
        # 2. 运行 admixture --supervised
        # 3. 解析 .Q 文件
        raise NotImplementedError("ADMIXTURE 分析待实现")

    def analyze_multi_k(
        self,
        sample_plink_prefix: str,
        output_dir: str,
        sample_id: str,
        k_range: Tuple[int, int] = (2, 15),
    ) -> List[AdmixtureResult]:
        """
        多 K 值分析，找最优 K

        通过交叉验证误差 (CV error) 确定最佳成分数
        """
        # TODO: 实现
        raise NotImplementedError("多 K 值分析待实现")


# ===== G25 坐标计算 =====

class G25Analyzer:
    """
    G25 (Global25) 坐标计算

    将样本投影到 Vahaduo G25 坐标空间，
    得到 25 维坐标，可用于 Vahaduo 在线工具做距离计算
    """

    def __init__(
        self,
        g25_reference: Optional[str] = None,
    ):
        """
        Args:
            g25_reference: G25 参考坐标文件路径
        """
        self.g25_reference = g25_reference or str(
            settings.reference_dir / "population" / "g25" / "g25_reference.txt"
        )

    def calculate(
        self,
        sample_plink_prefix: str,
        output_dir: str,
        sample_id: str,
    ) -> G25Result:
        """
        计算 G25 坐标

        流程:
        1. 提取 G25 所需的 SNP 子集
        2. PCA 投影到 G25 空间
        3. 输出 25 维坐标
        4. 计算与参考样本的距离
        """
        # TODO: 实现
        raise NotImplementedError("G25 坐标计算待实现")

    def find_nearest(
        self,
        coordinates: List[float],
        top_n: int = 20,
    ) -> Tuple[List[dict], List[dict]]:
        """
        找最近的古代和现代样本

        Returns:
            (nearest_ancient, nearest_modern)
        """
        # TODO: 实现
        raise NotImplementedError


# ===== qpAdm 祖源建模 =====

class QpAdmAnalyzer:
    """
    qpAdm 祖源建模

    使用 ADMIXTOOLS2 / qpAdm 进行正式的祖源建模，
    估算目标样本由哪些源人群混合而成
    """

    def __init__(self, admixtools_path: Optional[str] = None):
        self.admixtools = admixtools_path

    def analyze(
        self,
        sample_plink_prefix: str,
        output_dir: str,
        sample_id: str,
        sources: List[str],
        outgroups: Optional[List[str]] = None,
    ) -> QpAdmResult:
        """
        运行 qpAdm 分析

        Args:
            sample_plink_prefix: 样本 PLINK 文件前缀
            output_dir: 输出目录
            sample_id: 样本 ID
            sources: 源人群列表 (如 ["Yamnaya", "WHG", "EEF"])
            outgroups: 外群列表
        """
        # TODO: 实现
        raise NotImplementedError("qpAdm 分析待实现")


# ===== 统一入口 =====

class PopulationAnalyzer:
    """
    群体分析统一入口

    串联 PLINK 转换 → PCA/ADMIXTURE/G25/qpAdm 的完整流程
    """

    def __init__(self, reference_version: str = "hg38"):
        self.reference_version = reference_version
        self.converter = PlinkConverter()
        self.pca = PCAAnalyzer()
        self.admixture = AdmixtureAnalyzer()
        self.g25 = G25Analyzer()
        self.qpadm = QpAdmAnalyzer()

    def full_analysis(
        self,
        input_file: str,
        input_type: str,  # "1240k" or "chip"
        output_dir: str,
        sample_id: str,
        analyses: Optional[List[str]] = None,
    ) -> dict:
        """
        完整群体分析流程

        Args:
            input_file: 输入文件 (1240K 或芯片格式)
            input_type: 输入类型
            output_dir: 输出目录
            sample_id: 样本 ID
            analyses: 要运行的分析 ["pca", "admixture", "g25", "qpadm"]
                      None 表示全部

        Returns:
            各分析结果的字典
        """
        if analyses is None:
            analyses = ["pca", "admixture", "g25"]

        os.makedirs(output_dir, exist_ok=True)
        results = {}

        # Step 1: 转换为 PLINK 格式
        logger.info(f"Step 1: 转换为 PLINK 格式...")
        plink_prefix = os.path.join(output_dir, f"{sample_id}")
        if input_type == "1240k":
            plink_result = self.converter.from_1240k(input_file, plink_prefix, sample_id)
        else:
            plink_result = self.converter.from_chip_format(input_file, plink_prefix, sample_id)
        results["plink"] = plink_result

        # Step 2: PCA
        if "pca" in analyses:
            logger.info(f"Step 2: PCA 分析...")
            pca_dir = os.path.join(output_dir, "pca")
            results["pca"] = self.pca.analyze(plink_prefix, pca_dir, sample_id)

        # Step 3: ADMIXTURE
        if "admixture" in analyses:
            logger.info(f"Step 3: ADMIXTURE 分析...")
            adm_dir = os.path.join(output_dir, "admixture")
            results["admixture"] = {}
            for calc_name in ["K13_Eurogenes", "E11_Eurogenes"]:
                results["admixture"][calc_name] = self.admixture.analyze(
                    plink_prefix, adm_dir, sample_id, calculator=calc_name
                )

        # Step 4: G25
        if "g25" in analyses:
            logger.info(f"Step 4: G25 坐标计算...")
            g25_dir = os.path.join(output_dir, "g25")
            results["g25"] = self.g25.calculate(plink_prefix, g25_dir, sample_id)

        # Step 5: qpAdm
        if "qpadm" in analyses:
            logger.info(f"Step 5: qpAdm 祖源建模...")
            qpadm_dir = os.path.join(output_dir, "qpadm")
            results["qpadm"] = self.qpadm.analyze(
                plink_prefix, qpadm_dir, sample_id,
                sources=["Yamnaya_EMBA", "WHG", "Anatolia_N"],  # 默认源人群
            )

        logger.info(f"群体分析完成: {output_dir}")
        return results
