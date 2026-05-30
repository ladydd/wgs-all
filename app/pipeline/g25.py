"""
G25 坐标距离计算模块

输入: 样本的 25 维 G25 坐标
输出: 与参考人群的欧氏距离排名（最近的现代/古代人群）

参考数据: /reference/population/g25/vahaduo_modern_scaled.txt
"""

import csv
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..core.config import settings
from ..core.logging import logger


@dataclass
class G25DistanceResult:
    """G25 距离计算结果"""
    sample_id: str
    coordinates: List[float]
    nearest_modern: List[Tuple[str, float]]   # [(人群名, 距离), ...]
    nearest_ancient: List[Tuple[str, float]]


def _euclidean_distance(a: List[float], b: List[float]) -> float:
    """计算欧氏距离"""
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _load_g25_reference(filepath: str) -> Dict[str, List[float]]:
    """加载 G25 参考坐标文件 (CSV: name,PC1,PC2,...,PC25)"""
    ref = {}
    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        header = next(reader, None)  # 跳过表头
        for row in reader:
            if len(row) >= 26:
                name = row[0]
                try:
                    coords = [float(x) for x in row[1:26]]
                    ref[name] = coords
                except ValueError:
                    continue
    return ref


class G25Calculator:
    """
    G25 坐标距离计算器

    用法:
        calc = G25Calculator()
        result = calc.find_nearest(
            coordinates=[0.023, -0.015, 0.008, ...],  # 25 个数字
            sample_id="MySample",
            top_n=20,
        )
    """

    def __init__(self, g25_dir: Optional[str] = None):
        g25_path = Path(g25_dir) if g25_dir else settings.reference_dir / "population" / "g25"

        self.modern_file = g25_path / "vahaduo_modern_scaled.txt"
        self.ancient_file = g25_path / "vahaduo_ancient_scaled.txt"

        if not self.modern_file.exists():
            raise FileNotFoundError(f"G25 现代参考文件不存在: {self.modern_file}")

        self._modern_ref = None
        self._ancient_ref = None

    def _load_refs(self):
        if self._modern_ref is None:
            logger.info(f"加载 G25 现代参考: {self.modern_file}")
            self._modern_ref = _load_g25_reference(str(self.modern_file))
            logger.info(f"  加载 {len(self._modern_ref)} 个现代样本")

        if self._ancient_ref is None and self.ancient_file.exists():
            logger.info(f"加载 G25 古代参考: {self.ancient_file}")
            self._ancient_ref = _load_g25_reference(str(self.ancient_file))
            logger.info(f"  加载 {len(self._ancient_ref)} 个古代样本")
        elif self._ancient_ref is None:
            self._ancient_ref = {}

    def find_nearest(
        self,
        coordinates: List[float],
        sample_id: str = "Sample",
        top_n: int = 20,
    ) -> G25DistanceResult:
        """
        计算样本与所有参考人群的距离，返回最近的

        Args:
            coordinates: 25 维 G25 坐标
            sample_id: 样本名
            top_n: 返回前 N 个最近的
        """
        if len(coordinates) != 25:
            raise ValueError(f"G25 坐标必须是 25 维，收到 {len(coordinates)} 维")

        self._load_refs()

        # 计算与现代人群的距离
        modern_distances = []
        for name, ref_coords in self._modern_ref.items():
            dist = _euclidean_distance(coordinates, ref_coords)
            modern_distances.append((name, dist))
        modern_distances.sort(key=lambda x: x[1])

        # 计算与古代样本的距离
        ancient_distances = []
        for name, ref_coords in self._ancient_ref.items():
            dist = _euclidean_distance(coordinates, ref_coords)
            ancient_distances.append((name, dist))
        ancient_distances.sort(key=lambda x: x[1])

        return G25DistanceResult(
            sample_id=sample_id,
            coordinates=coordinates,
            nearest_modern=modern_distances[:top_n],
            nearest_ancient=ancient_distances[:top_n],
        )

    def find_nearest_from_file(
        self,
        g25_file: str,
        sample_id: Optional[str] = None,
        top_n: int = 20,
    ) -> G25DistanceResult:
        """
        从 G25 坐标文件读取样本坐标并计算距离

        文件格式: CSV 一行，name,PC1,PC2,...,PC25
        """
        with open(g25_file, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if row and not row[0].startswith('PC') and not row[0].startswith(','):
                    name = row[0] if row[0] else (sample_id or "Sample")
                    try:
                        coords = [float(x) for x in row[1:26]]
                        if len(coords) == 25:
                            return self.find_nearest(coords, name, top_n)
                    except ValueError:
                        continue

        raise ValueError(f"无法从文件解析 G25 坐标: {g25_file}")
