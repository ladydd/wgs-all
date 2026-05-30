"""
EIGENSTRAT 数据集提取模块 - 批量 BAM → EIGENSTRAT 三件套

用途:
    古 DNA 群体遗传分析 (qpAdm, smartpca, ADMIXTOOLS2) 的标准输入格式。
    和 K1240Extractor 的区别:
    - K1240Extractor: 单样本，bcftools call，输出人类可读 TSV
    - EigenstratExtractor: 多样本合并，pileupCaller randomHaploid，输出 .geno/.snp/.ind

参考自:
    https://github.com/teepean/adna_to_dataset (hg19 版本)
    本模块是 hg38 原生实现。

核心管道:
    samtools mpileup -B -q30 -Q30 -l <pos> -f <ref> <bam1> <bam2> ...
      | awk (chr 前缀剥离 + X/Y/MT→23/24/90 数字化)
      | sort -k1,1n -k2,2n
      | pileupCaller --randomHaploid --snpFile <snp> --eigenstratOut <prefix>
"""

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..core.bam_detector import detect_bam_reference, map_to_system_version
from ..core.config import settings
from ..core.logging import logger
from ..core.reference import reference_manager


# ===== 数据模型 =====

@dataclass
class EigenstratResult:
    """EIGENSTRAT 提取结果"""
    output_prefix: str             # 输出前缀 (无后缀)
    geno_file: str                 # .geno 文件
    snp_file: str                  # .snp 文件
    ind_file: str                  # .ind 文件
    stats_file: str                # pileupCaller 统计日志
    sample_ids: List[str]          # 样本 ID 列表
    population: str                # 群体标签
    position_set: str              # 位点集名 (v42.4.1240K / v66.2M.aadr)
    total_snps: int                # 输出 SNP 数
    reference_version: str         # 输入 BAM 的参考版本 (hg38)
    coord_system: str              # 输出坐标系 (hg38 / hg19)


# ===== 工具函数 =====

def _run_pipeline(cmd: str, desc: str = "") -> Tuple[int, str]:
    """
    运行 shell 管道命令

    管道命令需要 shell=True 才能正确解析 `|`。捕获 stderr 返回，方便排错。
    """
    if desc:
        logger.info(f"▶ {desc}")
    logger.debug(f"  $ {cmd}")

    proc = subprocess.Popen(
        cmd, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, executable="/bin/bash",
    )
    stdout, stderr = proc.communicate()

    if proc.returncode != 0:
        logger.error(f"命令失败 (exit={proc.returncode}): {desc}")
        logger.error(f"stderr:\n{stderr}")
        raise RuntimeError(f"Pipeline failed: {desc}\n{stderr}")

    return proc.returncode, stderr


def _detect_sort() -> str:
    """
    检测 sort 命令。adna_to_dataset 作者指出 uutils coreutils sort 对大 pileup 数据
    有 bug，只有 GNU sort 可靠。
    """
    # 优先使用 gnusort (Homebrew 环境常见别名)
    if shutil.which("gnusort"):
        return "gnusort"

    # 验证系统 sort 是 GNU 版本
    if shutil.which("sort"):
        try:
            r = subprocess.run(["sort", "--version"], capture_output=True, text=True, timeout=5)
            if "GNU coreutils" in r.stdout:
                return "sort"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    logger.warning(
        "未检测到 GNU sort (系统可能是 uutils coreutils)，"
        "处理大型 pileup 数据时可能出错。建议安装 GNU coreutils。"
    )
    return "sort"


def _find_executable(name: str, conda_env: Optional[str] = None) -> str:
    """查找可执行文件，可选指定 conda 环境"""
    if conda_env:
        cand = Path.home() / "miniconda3" / "envs" / conda_env / "bin" / name
        if cand.exists():
            return str(cand)
    path = shutil.which(name)
    if path:
        return path
    raise FileNotFoundError(f"找不到工具: {name} (conda env: {conda_env})")


# ===== awk 染色体重命名脚本 =====
#
# 输入: samtools mpileup 输出 (列: chrom pos ref depth ...)
# 规则:
#   chr1 → 1, chr2 → 2, ... chrX → 23, chrY → 24, chrM → 90
#   1 → 1 (无 chr 风格保持不变), X → 23, Y → 24, MT → 90
# 丢弃:
#   非主染色体 (alt contig / decoy / random / patch / HLA 等)
#
# AADR 的 MT 编号是 90 不是 25 —— 这是 adna_to_dataset 脚本的约定
# (原话: if($1=="MT")$1=90)，维持兼容。
_AWK_RENAME = r'''
BEGIN { OFS="\t" }
{
    c = $1
    sub(/^chr/, "", c)
    if (c == "X") c = "23"
    else if (c == "Y") c = "24"
    else if (c == "M" || c == "MT") c = "90"
    # 只接受纯数字染色体
    if (c ~ /^[0-9]+$/) {
        $1 = c
        print
    }
}
'''


# ===== 主类 =====

class EigenstratExtractor:
    """
    hg38 BAM 批量 → EIGENSTRAT 数据集

    典型用法:
        extractor = EigenstratExtractor()
        result = extractor.extract(
            bam_files=["a.bam", "b.bam", ...],
            sample_ids=["sampleA", "sampleB", ...],
            population="Ancient_CN",
            output_dir="/data/output",
            output_name="batch1",
            position_set="v42.4.1240K",
        )
    """

    SUPPORTED_POSITION_SETS = ["v42.4.1240K", "v66.2M.aadr"]
    CALLING_METHODS = ["randomHaploid", "majorityCall", "randomDiploid"]

    def __init__(
        self,
        reference_version: str = "hg38",
        calling_method: str = "randomHaploid",
        min_mapq: int = 30,
        min_baseq: int = 30,
        min_depth: int = 1,
        skip_transitions: bool = False,
        seed: Optional[int] = None,
        conda_env: str = "ychr",
    ):
        """
        Args:
            reference_version: BAM 对应的参考版本 (目前只支持 hg38)
            calling_method: pileupCaller 抽基因型方法
                - randomHaploid: 每位点随机抽 1 条 read (古 DNA 标准)
                - majorityCall: 多数投票
                - randomDiploid: 随机抽 2 条 read 成二倍体
            min_mapq: samtools mpileup -q 参数 (比对质量阈值)
            min_baseq: samtools mpileup -Q 参数 (碱基质量阈值)
            min_depth: pileupCaller -d 参数 (最小深度)
            skip_transitions: 古 DNA 中 C→T/G→A 转换是常见 damage，
                              开启此项忽略这些位点以避免 damage 偏差
            seed: 随机种子 (复现用)
            conda_env: samtools/pileupCaller 所在 conda 环境
        """
        if reference_version not in ("hg38", "hg19", "t2t"):
            raise ValueError(f"支持 hg38 / hg19 / t2t (请求: {reference_version})")
        # T2T 常染色体坐标与 hg38 差异 <0.01%，直接复用 hg38 位点表
        if reference_version == "t2t":
            logger.info("T2T BAM: 使用 hg38 位点表 (常染色体坐标兼容)")
            reference_version = "hg38"
        if calling_method not in self.CALLING_METHODS:
            raise ValueError(
                f"未知 calling method: {calling_method}，"
                f"支持: {self.CALLING_METHODS}"
            )

        self.reference_version = reference_version
        self.calling_method = calling_method
        self.min_mapq = min_mapq
        self.min_baseq = min_baseq
        self.min_depth = min_depth
        self.skip_transitions = skip_transitions
        self.seed = seed
        self.conda_env = conda_env

        # 定位工具
        self.samtools = _find_executable("samtools", conda_env)
        self.pileup_caller = _find_executable("pileupCaller", conda_env)
        self.sort_cmd = _detect_sort()

        # 定位参考基因组
        self.ref_genome = reference_manager.get_genome_path(reference_version)
        if not self.ref_genome.exists():
            raise FileNotFoundError(f"参考基因组不存在: {self.ref_genome}")
        if not Path(f"{self.ref_genome}.fai").exists():
            raise FileNotFoundError(
                f"参考基因组未建 fai 索引: {self.ref_genome}.fai，"
                f"请运行 `samtools faidx {self.ref_genome}`"
            )

    # -------------------------------------------------------------- #
    # BAM 命名风格识别
    # -------------------------------------------------------------- #

    def _detect_bam_style(self, bam_files: List[str]) -> Tuple[bool, List[str]]:
        """
        检测 BAM 的染色体命名风格，并验证所有 BAM 是 hg38。

        Returns:
            (has_chr_prefix, warnings)
        """
        warnings = []
        styles = set()

        for bam in bam_files:
            info = detect_bam_reference(bam)
            try:
                sys_ver = map_to_system_version(info)
            except ValueError:
                raise RuntimeError(
                    f"BAM 参考系无法识别: {bam} ({info.reference_display})"
                )
            if sys_ver != self.reference_version:
                # hg19 BAM 也可能被识别为 "hg19"（grch37 映射到 hg19）
                if not (self.reference_version == "hg19" and sys_ver == "hg19"):
                    raise RuntimeError(
                        f"BAM 参考系不匹配: {bam} (识别为 {info.reference_display})，"
                        f"期望 {self.reference_version}。"
                    )
            styles.add(info.has_chr_prefix)

        if len(styles) > 1:
            raise RuntimeError(
                "输入 BAM 混用了 chr 前缀风格 (部分带 chr 部分不带)，"
                "请统一后再处理。"
            )

        has_chr_prefix = styles.pop()
        logger.info(
            f"BAM 命名风格: {'chr前缀 (chr1/chrX/chrM)' if has_chr_prefix else '无前缀 (1/X/MT)'}"
        )
        return has_chr_prefix, warnings

    # -------------------------------------------------------------- #
    # 核心 pipeline
    # -------------------------------------------------------------- #

    def extract(
        self,
        bam_files: List[str],
        sample_ids: Optional[List[str]] = None,
        population: str = "Unknown",
        output_dir: str = ".",
        output_name: str = "dataset",
        position_set: str = "v42.4.1240K",
        sex_by_sample: Optional[Dict[str, str]] = None,
    ) -> EigenstratResult:
        """
        批量提取

        Args:
            bam_files: 输入 BAM 文件列表 (hg38，命名风格需一致)
            sample_ids: 对应的样本 ID 列表，None 则用文件名 (去 .bam 后缀)
            population: 群体标签 (用于 .ind 文件)
            output_dir: 输出目录
            output_name: 输出前缀 (不含路径、不含扩展名)
            position_set: 位点集，支持 v42.4.1240K / v66.2M.aadr
            sex_by_sample: 样本性别 {sample_id: "M"/"F"/"U"}，默认全部 "U"
        """
        # ---------- 参数与输入校验 ----------
        if not bam_files:
            raise ValueError("bam_files 不能为空")

        if position_set not in self.SUPPORTED_POSITION_SETS:
            raise ValueError(
                f"未知位点集: {position_set}，支持: {self.SUPPORTED_POSITION_SETS}"
            )

        bam_paths = []
        for b in bam_files:
            p = Path(b).resolve()
            if not p.exists():
                raise FileNotFoundError(f"BAM 不存在: {b}")
            if not Path(f"{p}.bai").exists() and not Path(str(p).replace(".bam", ".bai")).exists():
                logger.warning(f"BAM 缺少 .bai 索引: {p} (samtools mpileup 不强制需要，但建议建)")
            bam_paths.append(str(p))

        if sample_ids is None:
            sample_ids = [Path(b).stem.replace(".sorted", "").replace(".dedup", "") for b in bam_paths]
        if len(sample_ids) != len(bam_paths):
            raise ValueError(f"sample_ids 数量 ({len(sample_ids)}) 与 BAM 数量 ({len(bam_paths)}) 不符")

        # 样本名不能含逗号 (pileupCaller --sampleNames 用逗号分隔)
        for sid in sample_ids:
            if "," in sid:
                raise ValueError(f"样本 ID 不能包含逗号: {sid}")

        sex_by_sample = sex_by_sample or {}

        # ---------- 识别 BAM 命名风格 ----------
        has_chr_prefix, warns = self._detect_bam_style(bam_paths)

        # ---------- 找位点文件 ----------
        pos_info = reference_manager.get_eigenstrat_positions(
            version=self.reference_version,
            position_set=position_set,
            with_chr_prefix=has_chr_prefix,
        )
        snp_file = pos_info["snp"]
        pos_file = pos_info["pos"]
        logger.info(f"位点集: {position_set} @ {snp_file}")

        # ---------- 准备输出 ----------
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_prefix = out_dir / output_name
        stats_file = out_dir / f"{output_name}.stats.txt"

        # 临时 BAM list 文件 (命令行可能太长)
        bam_list_file = out_dir / f".{output_name}.bamlist.tmp"
        with open(bam_list_file, "w") as f:
            for b in bam_paths:
                f.write(b + "\n")

        # ---------- 组装 pipeline ----------
        sample_names_csv = ",".join(sample_ids)

        # pileupCaller 参数
        pc_args = [
            f"--{self.calling_method}",
            f"-f {_shell_quote(str(snp_file))}",
            f"--sampleNames {_shell_quote(sample_names_csv)}",
            f"--samplePopName {_shell_quote(population)}",
            f"-e {_shell_quote(str(out_prefix))}",  # eigenstratOut
            f"-d {self.min_depth}",
        ]
        if self.skip_transitions:
            pc_args.append("--skipTransitions")
        if self.seed is not None:
            pc_args.append(f"--seed {self.seed}")

        cmd = (
            f"{_shell_quote(self.samtools)} mpileup "
            f"-B -q {self.min_mapq} -Q {self.min_baseq} "
            f"-l {_shell_quote(str(pos_file))} "
            f"-f {_shell_quote(str(self.ref_genome))} "
            f"-b {_shell_quote(str(bam_list_file))} "
            f"  2> {_shell_quote(str(out_dir / f'{output_name}.mpileup.log'))} "
            f"| awk {_shell_quote(_AWK_RENAME)} "
            f"| {self.sort_cmd} -t $'\\t' -k1,1n -k2,2n "
            f"| {_shell_quote(self.pileup_caller)} {' '.join(pc_args)} "
            f"  > {_shell_quote(str(stats_file))} 2>&1"
        )

        logger.info("=" * 70)
        logger.info(f"EIGENSTRAT 提取开始:")
        logger.info(f"  样本数: {len(bam_paths)}")
        logger.info(f"  群体: {population}")
        logger.info(f"  位点集: {position_set}")
        logger.info(f"  方法: {self.calling_method}")
        logger.info(f"  输出: {out_prefix}.{{geno,snp,ind}}")
        logger.info("=" * 70)

        try:
            _run_pipeline(cmd, desc=f"mpileup + pileupCaller ({len(bam_paths)} BAMs)")
        finally:
            # 清理 bamlist
            if bam_list_file.exists():
                bam_list_file.unlink()

        # ---------- 输出校验 ----------
        geno_file = Path(f"{out_prefix}.geno")
        snp_out = Path(f"{out_prefix}.snp")
        ind_out = Path(f"{out_prefix}.ind")

        for f in [geno_file, snp_out, ind_out]:
            if not f.exists() or f.stat().st_size == 0:
                logger.error(f"stats:\n{stats_file.read_text() if stats_file.exists() else '(无)'}")
                raise RuntimeError(f"pileupCaller 输出缺失或为空: {f}")

        # 写样本性别到 .ind (pileupCaller 默认写 "U")
        if sex_by_sample:
            self._patch_ind_sex(ind_out, sample_ids, sex_by_sample)

        # 统计 SNP 数
        total_snps = sum(1 for _ in open(snp_out))

        logger.info(f"✅ 完成! 输出 {total_snps} 个 SNP，{len(sample_ids)} 个样本")

        return EigenstratResult(
            output_prefix=str(out_prefix),
            geno_file=str(geno_file),
            snp_file=str(snp_out),
            ind_file=str(ind_out),
            stats_file=str(stats_file),
            sample_ids=list(sample_ids),
            population=population,
            position_set=position_set,
            total_snps=total_snps,
            reference_version=self.reference_version,
            coord_system="hg38",
        )

    # -------------------------------------------------------------- #
    # 辅助: 性别写入 .ind
    # -------------------------------------------------------------- #

    def _patch_ind_sex(
        self,
        ind_file: Path,
        sample_ids: List[str],
        sex_by_sample: Dict[str, str],
    ):
        """
        重写 .ind 文件，把性别列从 'U' 改成用户指定的值。
        .ind 格式: sample_id  sex  population  (3 列，空格/tab 分隔)
        """
        lines = ind_file.read_text().splitlines()
        out_lines = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 3:
                sid, _sex, pop = parts[0], parts[1], parts[2]
                new_sex = sex_by_sample.get(sid, _sex).upper()
                if new_sex not in ("M", "F", "U"):
                    logger.warning(f"样本 {sid} 性别值无效 '{new_sex}'，使用 'U'")
                    new_sex = "U"
                out_lines.append(f"{sid}\t{new_sex}\t{pop}")
            else:
                out_lines.append(line)
        ind_file.write_text("\n".join(out_lines) + "\n")


# ===== 工具函数: shell 转义 =====

def _shell_quote(s: str) -> str:
    """把字符串包成适合 bash 的单引号形式"""
    if not s:
        return "''"
    # 单引号内部单引号需要特殊处理
    return "'" + s.replace("'", "'\\''") + "'"


# ===== hg38 → hg19 坐标回换 (交付用) =====

class HgCoordRewriter:
    """
    把 hg38 坐标的 EIGENSTRAT 数据集重写成 hg19 坐标，用于对外交付
    (下游 AADR 生态全是 hg19 坐标)。

    做法:
        1. 读 hg38 版本的 .snp (rsID + hg38 坐标 + ref/alt)
        2. 从 AADR 原始 hg19 .snp 建 rsID → hg19_pos 的映射
        3. 按 rsID 把 .snp 里的坐标换成 hg19 值
        4. 只动 .snp，.geno 和 .ind 保持不动 (基因型和坐标无关)
        5. 丢弃在 AADR hg19 .snp 里找不到 rsID 的位点 (理论上不会有)
    """

    def rewrite_to_hg19(
        self,
        eigenstrat_prefix: str,
        aadr_hg19_snp: str,
        output_prefix: str,
    ) -> Dict[str, str]:
        """
        Args:
            eigenstrat_prefix: 输入 EIGENSTRAT 前缀 (hg38 坐标)
            aadr_hg19_snp: AADR 官方 hg19 .snp 文件
                (/home/ladydd/wgs-platform/adna_to_dataset/positions/v42.4.1240K.snp)
            output_prefix: 输出前缀 (hg19 坐标)

        Returns:
            {"geno": ..., "snp": ..., "ind": ...}
        """
        in_geno = Path(f"{eigenstrat_prefix}.geno")
        in_snp = Path(f"{eigenstrat_prefix}.snp")
        in_ind = Path(f"{eigenstrat_prefix}.ind")
        for f in [in_geno, in_snp, in_ind]:
            if not f.exists():
                raise FileNotFoundError(f"输入文件缺失: {f}")

        out_geno = Path(f"{output_prefix}.geno")
        out_snp = Path(f"{output_prefix}.snp")
        out_ind = Path(f"{output_prefix}.ind")
        out_geno.parent.mkdir(parents=True, exist_ok=True)

        # 1. 建 rsID → (chrom, gen_pos, pos, ref, alt) 映射 (AADR hg19)
        logger.info(f"加载 AADR hg19 .snp: {aadr_hg19_snp}")
        hg19_by_rsid = {}
        with open(aadr_hg19_snp) as f:
            for line in f:
                parts = line.split()
                if len(parts) != 6:
                    continue
                rsid, chrom, gen_pos, pos, ref, alt = parts
                hg19_by_rsid[rsid] = (chrom, gen_pos, pos, ref, alt)
        logger.info(f"  加载 {len(hg19_by_rsid)} 个位点")

        # 2. 并行读 .geno 和 .snp，按 rsID 查 hg19 坐标
        logger.info(f"重写 .snp + 过滤 .geno ({in_snp.name} → hg19)")
        kept = 0
        dropped = 0
        allele_mismatch = 0

        with open(in_snp) as f_snp, open(in_geno) as f_geno, \
             open(out_snp, "w") as out_snp_fp, open(out_geno, "w") as out_geno_fp:
            for snp_line, geno_line in zip(f_snp, f_geno):
                snp_parts = snp_line.split()
                if len(snp_parts) != 6:
                    continue
                rsid = snp_parts[0]
                hg38_ref, hg38_alt = snp_parts[4], snp_parts[5]

                hg19 = hg19_by_rsid.get(rsid)
                if hg19 is None:
                    dropped += 1
                    continue

                hg19_chrom, hg19_gen, hg19_pos, hg19_ref, hg19_alt = hg19

                # 等位基因一致性 (应该 100% 一致，因为我们的 hg38 位点本来就是从 hg19 转的)
                if (hg38_ref, hg38_alt) != (hg19_ref, hg19_alt):
                    allele_mismatch += 1

                # 写 .snp (用 AADR 原版 hg19 坐标)
                out_snp_fp.write(
                    f"{rsid:>20s}\t{hg19_chrom}\t{hg19_gen}\t{hg19_pos}\t{hg19_ref}\t{hg19_alt}\n"
                )
                # 写 .geno (原样复制)
                out_geno_fp.write(geno_line)
                kept += 1

        # 3. .ind 原样复制
        shutil.copyfile(in_ind, out_ind)

        logger.info(f"✅ 重写完成:")
        logger.info(f"  保留: {kept} 位点")
        logger.info(f"  丢弃 (AADR 找不到 rsID): {dropped}")
        if allele_mismatch:
            logger.warning(f"  ⚠ 等位基因不一致: {allele_mismatch} (理论不该有)")

        return {
            "geno": str(out_geno),
            "snp": str(out_snp),
            "ind": str(out_ind),
            "kept": kept,
            "dropped": dropped,
        }
