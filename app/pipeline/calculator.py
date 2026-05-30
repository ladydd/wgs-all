"""
常染色体祖源计算器模块 - 基于 admix 包的 supervised ADMIXTURE 计算

支持 28 个计算器 (E11, K13, K36, K47, HarappaWorld 等)。
输入: 23andMe 格式的芯片文件 (extract-chip 产出)
输出: 各计算器的祖源成分比例

依赖: admix (pip install admix)
"""

import os
import subprocess
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ..core.logging import logger


@dataclass
class AdmixtureCalcResult:
    """单个计算器的结果"""
    calculator: str                    # 计算器名 (如 E11, K13)
    components: Dict[str, float]       # {成分名: 比例}，如 {"East Chinese": 34.56}
    total_snps_used: int = 0           # 使用的 SNP 数


@dataclass
class AdmixtureResult:
    """全部计算器结果"""
    sample_id: str
    input_file: str
    calculators: List[AdmixtureCalcResult]


# 所有可用计算器
AVAILABLE_CALCULATORS = [
    "E11", "K12b", "K13", "K13M2", "K14M1", "K18M4", "K25R1",
    "K36", "K47", "K7b", "K7M1", "K7AMI", "K8AMI",
    "EUtest13", "Eurasia7", "globe10", "globe13",
    "HarappaWorld", "Jtest14", "Africa9", "AncientNearEast13",
    "KurdishK10", "MDLPk27", "MichalK25", "puntDNAL",
    "TurkicK11", "weac2", "world9",
]

# 推荐的东亚/全球常用计算器子集
RECOMMENDED_CALCULATORS = ["E11", "K12b", "K36", "globe13"]


class AdmixtureCalculator:
    """
    常染色体祖源计算器

    用法:
        calc = AdmixtureCalculator()
        result = calc.run(
            chip_file="/path/to/SAMPLE_23andMe_V5.txt",
            sample_id="SAMPLE",
            calculators=["E11", "K13", "K36"],
        )
    """

    def __init__(self, admix_cmd: Optional[str] = None):
        """
        Args:
            admix_cmd: admix 命令路径，None 则自动查找
        """
        if admix_cmd:
            self.admix_cmd = admix_cmd
        else:
            self.admix_cmd = shutil.which("admix")
            if not self.admix_cmd:
                # 尝试 conda 环境
                cand = Path.home() / "miniconda3" / "envs" / "ychr" / "bin" / "admix"
                if cand.exists():
                    self.admix_cmd = str(cand)
                else:
                    raise FileNotFoundError(
                        "找不到 admix 命令。请安装: pip install admix"
                    )

    def list_calculators(self) -> List[str]:
        """列出所有可用计算器"""
        return AVAILABLE_CALCULATORS.copy()

    def run(
        self,
        chip_file: str,
        sample_id: Optional[str] = None,
        calculators: Optional[List[str]] = None,
        vendor: str = "23andme",
    ) -> AdmixtureResult:
        """
        运行祖源计算

        Args:
            chip_file: 芯片格式文件 (23andMe/AncestryDNA 等)
            sample_id: 样本 ID
            calculators: 要跑的计算器列表，None 则用推荐子集
            vendor: 文件格式 (23andme / ancestry)

        Returns:
            AdmixtureResult
        """
        if not os.path.exists(chip_file):
            raise FileNotFoundError(f"芯片文件不存在: {chip_file}")

        if sample_id is None:
            sample_id = Path(chip_file).stem

        if calculators is None:
            calculators = RECOMMENDED_CALCULATORS

        logger.info(f"祖源计算: {sample_id}, 计算器: {calculators}")

        results = []
        for calc in calculators:
            try:
                comp = self._run_single(chip_file, calc, vendor)
                if comp:
                    results.append(AdmixtureCalcResult(
                        calculator=calc,
                        components=comp,
                    ))
            except Exception as e:
                logger.warning(f"计算器 {calc} 失败: {e}")

        return AdmixtureResult(
            sample_id=sample_id,
            input_file=chip_file,
            calculators=results,
        )

    def _run_single(
        self, chip_file: str, calculator: str, vendor: str
    ) -> Optional[Dict[str, float]]:
        """跑单个计算器，解析输出"""
        cmd = f'{self.admix_cmd} -f "{chip_file}" -v {vendor} -m {calculator}'
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=120
        )

        if result.returncode != 0:
            if "Cannot find model" in result.stdout:
                logger.warning(f"计算器不存在: {calculator}")
                return None
            raise RuntimeError(f"admix 失败: {result.stdout}\n{result.stderr}")

        # 解析输出
        components = {}
        in_result = False
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line == calculator:
                in_result = True
                continue
            if in_result:
                if not line or line.startswith("Admixture") or line.startswith("Calcuation"):
                    break
                if ":" in line:
                    name, pct = line.rsplit(":", 1)
                    try:
                        val = float(pct.strip().rstrip("%"))
                        if val > 0:
                            components[name.strip()] = val
                    except ValueError:
                        pass

        return components if components else None
