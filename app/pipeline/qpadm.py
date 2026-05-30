"""
qpAdm 祖源建模模块

输入: 样本 EIGENSTRAT + 参考人群 EIGENSTRAT
输出: 祖源比例 + p 值

用户需要指定:
    - target: 目标样本
    - sources: 源人群列表 (如 ["Yamnaya_EMBA", "WHG", "Anatolia_N"])
    - outgroups: 外群列表 (如 ["Mbuti", "Papuan", "Onge", ...])
"""

import os
import subprocess
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from ..core.logging import logger


@dataclass
class QpAdmResult:
    """qpAdm 结果"""
    target: str
    sources: List[str]
    proportions: Dict[str, float]   # {源人群: 比例}
    std_errors: Dict[str, float]    # {源人群: 标准误}
    p_value: float
    feasible: bool                  # p > 0.05 且比例在 [0,1]
    output_file: str


def _find_tool(name: str) -> str:
    for cand in [
        shutil.which(name),
        f"/home/ladydd/miniconda3/envs/ychr/bin/{name}",
        f"/usr/local/bin/{name}",
    ]:
        if cand and os.path.exists(cand):
            return cand
    raise FileNotFoundError(f"找不到工具: {name}")


class QpAdmAnalyzer:
    """
    qpAdm 祖源建模

    用法:
        analyzer = QpAdmAnalyzer()
        result = analyzer.run(
            eigenstrat_prefix="/data/merged",
            target="MySample",
            sources=["Yamnaya_EMBA", "WHG", "Anatolia_N"],
            outgroups=["Mbuti", "Papuan", "Onge", "Han", "Karitiana"],
            output_dir="/data/qpadm_out",
        )
    """

    def __init__(self):
        self.qpadm = _find_tool("qpAdm")

    def run(
        self,
        eigenstrat_prefix: str,
        target: str,
        sources: List[str],
        outgroups: List[str],
        output_dir: str,
    ) -> QpAdmResult:
        """
        运行 qpAdm

        Args:
            eigenstrat_prefix: 合并后的 EIGENSTRAT 前缀 (含样本 + 参考人群)
            target: 目标样本/人群名
            sources: 源人群列表
            outgroups: 外群列表 (至少 4-5 个)
            output_dir: 输出目录
        """
        os.makedirs(output_dir, exist_ok=True)

        # 写 left/right 人群文件
        left_file = os.path.join(output_dir, "left.txt")
        right_file = os.path.join(output_dir, "right.txt")

        with open(left_file, "w") as f:
            f.write(target + "\n")
            for s in sources:
                f.write(s + "\n")

        with open(right_file, "w") as f:
            for o in outgroups:
                f.write(o + "\n")

        # 写 par 文件
        par_file = os.path.join(output_dir, "qpadm.par")
        out_file = os.path.join(output_dir, "qpadm.out")

        with open(par_file, "w") as f:
            f.write(f"genotypename: {eigenstrat_prefix}.geno\n")
            f.write(f"snpname: {eigenstrat_prefix}.snp\n")
            f.write(f"indivname: {eigenstrat_prefix}.ind\n")
            f.write(f"popleft: {left_file}\n")
            f.write(f"popright: {right_file}\n")
            f.write("details: YES\n")
            f.write("allsnps: YES\n")

        logger.info(f"qpAdm: target={target}, sources={sources}")

        result = subprocess.run(
            [self.qpadm, "-p", par_file],
            capture_output=True, text=True
        )

        # 保存完整输出
        with open(out_file, "w") as f:
            f.write(result.stdout)

        # 解析结果
        proportions, std_errors, p_value = self._parse_output(result.stdout, sources)

        feasible = (
            p_value > 0.05
            and all(0 <= v <= 1 for v in proportions.values())
        )

        return QpAdmResult(
            target=target,
            sources=sources,
            proportions=proportions,
            std_errors=std_errors,
            p_value=p_value,
            feasible=feasible,
            output_file=out_file,
        )

    def _parse_output(
        self, stdout: str, sources: List[str]
    ) -> tuple:
        """解析 qpAdm 输出"""
        proportions = {}
        std_errors = {}
        p_value = 0.0

        for line in stdout.split("\n"):
            # 找 "best coefficients" 行
            if "best coefficients:" in line:
                parts = line.split("best coefficients:")[1].strip().split()
                for i, s in enumerate(sources):
                    if i < len(parts):
                        try:
                            proportions[s] = float(parts[i])
                        except ValueError:
                            proportions[s] = 0.0

            # 找 p-value
            if "tail prob" in line.lower() or "p-value" in line.lower():
                parts = line.split()
                for p in parts:
                    try:
                        val = float(p)
                        if 0 <= val <= 1:
                            p_value = val
                            break
                    except ValueError:
                        continue

        # 如果没解析到，给默认值
        if not proportions:
            for s in sources:
                proportions[s] = 0.0
                std_errors[s] = 0.0

        return proportions, std_errors, p_value
