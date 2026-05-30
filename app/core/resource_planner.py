"""
资源规划模块 - 根据样本大小和机器资源，计算最优比对参数

两步走:
1. 估算样本需求 (输入大小 → 预估内存、磁盘、耗时)
2. 匹配机器资源 (CPU/内存/磁盘 → 最优线程数和排序内存)

核心原则: 宁可慢不要死，跑不了就提前说
"""

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from .logging import logger


@dataclass
class SampleEstimate:
    """样本资源估算"""
    sample_id: str
    r1_size_gb: float          # R1 文件大小 (GB)
    r2_size_gb: float          # R2 文件大小 (GB)
    input_total_gb: float      # 输入总大小 (GB)
    est_bam_gb: float          # 预估 BAM 大小 (GB)
    est_temp_gb: float         # 预估临时文件大小 (GB)
    est_disk_need_gb: float    # 预估总磁盘需求 (GB)
    min_memory_gb: int         # 最低内存需求 (GB)


@dataclass
class MachineResources:
    """机器资源"""
    cpu_count: int             # CPU 核心数
    total_memory_gb: int       # 总内存 (GB)
    avail_memory_gb: int       # 可用内存 (GB)
    disk_avail_gb: int         # 磁盘可用空间 (GB)
    disk_path: str             # 磁盘路径


@dataclass
class AlignmentPlan:
    """比对执行计划"""
    can_run: bool              # 能不能跑
    reason: str                # 不能跑的原因 / 能跑的说明
    threads: int               # 推荐线程数
    sort_memory: str           # 推荐每线程排序内存 (如 "2G", "768M")
    total_memory_gb: int       # 预估总内存使用 (GB)
    est_hours: float           # 预估耗时 (小时)
    docker_memory_limit: str   # Docker --memory 参数
    warnings: list             # 警告信息


# ===== 常量 =====
BWA_BASE_MEMORY_GB = 8        # BWA 加载 hg38 索引的固定内存
MIN_MEMORY_GB = 12            # 最低可运行内存 (BWA 8G + sort 至少 4G)
MIN_DISK_MARGIN_GB = 10       # 磁盘最少保留空间 (GB)
BAM_SIZE_RATIO = 0.8          # BAM ≈ 压缩 FASTQ 的 0.8 倍
TEMP_SIZE_RATIO = 2.5         # sort 临时文件 ≈ 压缩 FASTQ 的 2.5 倍
MAX_SORT_MEM_PER_THREAD_GB = 4  # 每线程排序内存上限
MAX_USEFUL_THREADS = 16       # 超过 16 线程收益递减


def get_file_size_gb(path: str) -> float:
    """获取文件大小 (GB)"""
    try:
        return os.path.getsize(path) / (1024 ** 3)
    except OSError:
        return 0.0


def estimate_sample(sample_id: str, r1_path: str, r2_path: str) -> SampleEstimate:
    """
    估算样本资源需求
    
    根据输入 FASTQ 文件大小，估算比对过程需要的磁盘和内存
    """
    r1_gb = get_file_size_gb(r1_path)
    r2_gb = get_file_size_gb(r2_path)
    total_gb = r1_gb + r2_gb
    
    # 预估输出和临时文件大小
    est_bam = total_gb * BAM_SIZE_RATIO
    est_temp = total_gb * TEMP_SIZE_RATIO
    est_disk = est_bam + est_temp + MIN_DISK_MARGIN_GB
    
    # 最低内存: BWA 8G + sort 至少需要一点缓冲
    min_mem = MIN_MEMORY_GB
    
    return SampleEstimate(
        sample_id=sample_id,
        r1_size_gb=round(r1_gb, 2),
        r2_size_gb=round(r2_gb, 2),
        input_total_gb=round(total_gb, 2),
        est_bam_gb=round(est_bam, 1),
        est_temp_gb=round(est_temp, 1),
        est_disk_need_gb=round(est_disk, 1),
        min_memory_gb=min_mem,
    )


def detect_machine_resources(output_path: str = "/data") -> MachineResources:
    """
    检测当前机器资源
    """
    # CPU
    cpu_count = os.cpu_count() or 4
    
    # 内存
    total_mem = 16
    avail_mem = 8
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if line.startswith('MemTotal:'):
                    total_mem = int(line.split()[1]) // (1024 * 1024)
                elif line.startswith('MemAvailable:'):
                    avail_mem = int(line.split()[1]) // (1024 * 1024)
    except (FileNotFoundError, ValueError):
        pass
    
    # 磁盘
    disk_avail = 100
    try:
        usage = shutil.disk_usage(output_path)
        disk_avail = int(usage.free / (1024 ** 3))
    except OSError:
        try:
            usage = shutil.disk_usage("/")
            disk_avail = int(usage.free / (1024 ** 3))
        except OSError:
            pass
    
    return MachineResources(
        cpu_count=cpu_count,
        total_memory_gb=total_mem,
        avail_memory_gb=avail_mem,
        disk_avail_gb=disk_avail,
        disk_path=output_path,
    )


def plan_alignment(
    sample: SampleEstimate,
    machine: MachineResources,
    max_memory_gb: Optional[int] = None,
    max_threads: Optional[int] = None,
) -> AlignmentPlan:
    """
    根据样本需求和机器资源，生成最优比对计划
    
    Args:
        sample: 样本估算
        machine: 机器资源
        max_memory_gb: 用户指定的内存上限 (可选)
        max_threads: 用户指定的线程上限 (可选)
    
    Returns:
        AlignmentPlan 包含能不能跑、推荐参数、预估耗时
    """
    warnings = []
    
    # ===== 检查硬性条件 =====
    
    # 1. 磁盘够不够
    if machine.disk_avail_gb < sample.est_disk_need_gb:
        return AlignmentPlan(
            can_run=False,
            reason=(
                f"磁盘空间不足: 需要 {sample.est_disk_need_gb:.0f}GB, "
                f"可用 {machine.disk_avail_gb}GB"
            ),
            threads=0, sort_memory="0", total_memory_gb=0,
            est_hours=0, docker_memory_limit="0", warnings=[],
        )
    
    # 2. 内存够不够 (最低 12GB)
    usable_memory = max_memory_gb or machine.avail_memory_gb
    if usable_memory < MIN_MEMORY_GB:
        return AlignmentPlan(
            can_run=False,
            reason=(
                f"内存不足: 最低需要 {MIN_MEMORY_GB}GB, "
                f"可用 {machine.avail_memory_gb}GB"
            ),
            threads=0, sort_memory="0", total_memory_gb=0,
            est_hours=0, docker_memory_limit="0", warnings=[],
        )
    
    # ===== 计算最优参数 =====
    
    # 可用内存 (保守: 用可用内存的 80%)
    mem_budget = int(usable_memory * 0.8)
    
    # sort 可用内存 = 总预算 - BWA 固定开销
    sort_budget = mem_budget - BWA_BASE_MEMORY_GB
    if sort_budget < 2:
        sort_budget = 2
        warnings.append("内存紧张，排序缓冲区很小，会频繁写磁盘")
    
    # 线程数: CPU - 2，但不超过上限
    threads = machine.cpu_count - 2
    if threads < 2:
        threads = 2
    if threads > MAX_USEFUL_THREADS:
        threads = MAX_USEFUL_THREADS
    if max_threads and threads > max_threads:
        threads = max_threads
    
    # 每线程排序内存
    sort_per_thread = sort_budget // threads
    if sort_per_thread < 1:
        # 内存太少，减线程
        threads = max(2, sort_budget)
        sort_per_thread = 1
        warnings.append(f"内存有限，线程降至 {threads}")
    if sort_per_thread > MAX_SORT_MEM_PER_THREAD_GB:
        sort_per_thread = MAX_SORT_MEM_PER_THREAD_GB
    
    sort_memory = f"{sort_per_thread}G"
    
    # 总内存预估
    total_memory = BWA_BASE_MEMORY_GB + sort_per_thread * threads
    
    # Docker 内存限制 (比预估多给 20% 余量)
    docker_limit = int(total_memory * 1.2)
    docker_memory_limit = f"{docker_limit}g"
    
    # 预估耗时 (基于经验数据)
    # 实测参考: 8线程, 3GB 压缩 FASTQ ≈ 2-3 小时
    # 线程越多越快，但不是线性的 (IO 瓶颈)
    # 公式: 基准时间 × 输入大小 × 线程修正
    base_minutes_per_gb = 35  # 8 线程下每 GB 压缩 FASTQ 约 35 分钟
    if threads <= 4:
        thread_factor = 1.8   # 4 线程比 8 线程慢 80%
    elif threads <= 8:
        thread_factor = 1.0   # 基准
    elif threads <= 12:
        thread_factor = 0.75  # 12 线程快 25%
    else:
        thread_factor = 0.65  # 16 线程快 35% (IO 瓶颈，不会更快了)
    
    # sort 内存小的话会频繁写磁盘，额外加时间
    sort_penalty = 1.0
    if sort_per_thread < 1:
        sort_penalty = 1.5    # 内存很小，慢 50%
    elif sort_per_thread < 2:
        sort_penalty = 1.2    # 内存偏小，慢 20%
    
    est_minutes = sample.input_total_gb * base_minutes_per_gb * thread_factor * sort_penalty
    est_hours = round(est_minutes / 60, 1)
    if est_hours < 0.1:
        est_hours = 0.1
    
    # 磁盘余量警告
    disk_margin = machine.disk_avail_gb - sample.est_disk_need_gb
    if disk_margin < 20:
        warnings.append(f"磁盘余量较小 ({disk_margin:.0f}GB)，建议清理空间")
    
    reason = (
        f"可以运行: {threads}线程, {sort_memory}/线程, "
        f"预估 {est_hours}小时, 内存 ~{total_memory}GB"
    )
    
    return AlignmentPlan(
        can_run=True,
        reason=reason,
        threads=threads,
        sort_memory=sort_memory,
        total_memory_gb=total_memory,
        est_hours=est_hours,
        docker_memory_limit=docker_memory_limit,
        warnings=warnings,
    )


def plan_batch(
    samples: list,
    machine: MachineResources,
) -> dict:
    """
    批量规划: 哪些能跑、哪些跑不了、总耗时预估、时间线
    
    Args:
        samples: [(sample_id, r1_path, r2_path), ...]
        machine: 机器资源
    
    Returns:
        完整的批量执行计划，包含时间线
    """
    runnable = []
    skipped = []
    total_hours = 0
    cumulative_disk = 0  # 累计磁盘占用 (前面样本的 BAM 会占空间)
    
    for sample_id, r1, r2 in samples:
        est = estimate_sample(sample_id, r1, r2)
        
        # 模拟磁盘: 前面样本的 BAM 已经占了空间
        adjusted_machine = MachineResources(
            cpu_count=machine.cpu_count,
            total_memory_gb=machine.total_memory_gb,
            avail_memory_gb=machine.avail_memory_gb,
            disk_avail_gb=machine.disk_avail_gb - int(cumulative_disk),
            disk_path=machine.disk_path,
        )
        
        plan = plan_alignment(est, adjusted_machine)
        
        if plan.can_run:
            runnable.append({
                "sample_id": sample_id,
                "input_gb": est.input_total_gb,
                "est_bam_gb": est.est_bam_gb,
                "est_hours": plan.est_hours,
                "threads": plan.threads,
                "sort_memory": plan.sort_memory,
                "cumulative_hours": round(total_hours + plan.est_hours, 1),
                "warnings": plan.warnings,
            })
            total_hours += plan.est_hours
            cumulative_disk += est.est_bam_gb  # BAM 留在磁盘上
        else:
            skipped.append({
                "sample_id": sample_id,
                "input_gb": est.input_total_gb,
                "reason": plan.reason,
            })
    
    # 时间线摘要
    total_days = round(total_hours / 24, 1)
    timeline = _build_timeline(runnable, total_hours)
    
    # 按大小排序建议 (小的先跑，快速出结果)
    sorted_by_size = sorted(runnable, key=lambda x: x["input_gb"])
    
    return {
        "runnable": runnable,
        "skipped": skipped,
        "runnable_count": len(runnable),
        "skipped_count": len(skipped),
        "total_hours": round(total_hours, 1),
        "total_days": total_days,
        "total_disk_gb": round(cumulative_disk, 1),
        "timeline": timeline,
        "recommendation": _build_recommendation(
            runnable, skipped, total_hours, cumulative_disk, machine
        ),
    }


def _build_timeline(runnable: list, total_hours: float) -> dict:
    """
    构建时间线: 什么时候完成多少
    """
    if not runnable:
        return {"checkpoints": [], "summary": "无可运行样本"}
    
    checkpoints = []
    hours_so_far = 0
    
    # 每完成 25% 记一个节点
    milestones = [0.25, 0.50, 0.75, 1.0]
    milestone_idx = 0
    
    for i, s in enumerate(runnable):
        hours_so_far += s["est_hours"]
        progress = (i + 1) / len(runnable)
        
        if milestone_idx < len(milestones) and progress >= milestones[milestone_idx]:
            checkpoints.append({
                "progress_pct": int(milestones[milestone_idx] * 100),
                "samples_done": i + 1,
                "hours_elapsed": round(hours_so_far, 1),
                "days_elapsed": round(hours_so_far / 24, 1),
            })
            milestone_idx += 1
    
    # 最小/最大/平均单样本耗时
    hours_list = [s["est_hours"] for s in runnable]
    
    return {
        "checkpoints": checkpoints,
        "per_sample": {
            "min_hours": round(min(hours_list), 1),
            "max_hours": round(max(hours_list), 1),
            "avg_hours": round(sum(hours_list) / len(hours_list), 1),
        },
        "summary": (
            f"预计 {round(total_hours / 24, 1)} 天完成全部 {len(runnable)} 个样本, "
            f"单样本 {round(min(hours_list), 1)}-{round(max(hours_list), 1)} 小时"
        ),
    }


def _build_recommendation(
    runnable: list, skipped: list,
    total_hours: float, total_disk_gb: float,
    machine: MachineResources,
) -> list:
    """
    生成执行建议
    """
    recs = []
    
    # 磁盘建议
    if total_disk_gb > machine.disk_avail_gb * 0.7:
        recs.append(
            f"⚠️ BAM 输出预计占 {total_disk_gb:.0f}GB，"
            f"接近磁盘可用空间 {machine.disk_avail_gb}GB 的 70%。"
            f"建议分批跑，或准备更多磁盘。"
        )
    
    # 时间建议
    if total_hours > 168:  # 超过一周
        recs.append(
            f"⏰ 预计总耗时 {total_hours / 24:.1f} 天。"
            f"建议先跑小样本快速出结果，大样本排后面。"
        )
    
    # 跳过的样本
    if skipped:
        recs.append(
            f"❌ {len(skipped)} 个样本因资源不足无法运行，"
            f"需要清理磁盘或增加资源后重试。"
        )
    
    # 并行建议
    if machine.total_memory_gb >= 64 and machine.cpu_count >= 16:
        recs.append(
            f"💡 机器资源充足 ({machine.cpu_count}核/{machine.total_memory_gb}GB)，"
            f"可以考虑同时跑 2 个样本（各用一半资源），总耗时减半。"
        )
    
    if not recs:
        recs.append("✅ 资源充足，可以直接开始批量比对。")
    
    return recs
