#!/usr/bin/env python3
"""
造一个最小测试 BAM 用于验证 EigenstratExtractor。

做法:
    1. 从 hg38 参考 fa 取 5 个 1240K 位点前后 50bp 序列
    2. 把中心碱基换成 alt (模拟变异)
    3. 每个位点生成 3 条 read (覆盖度 3x)，写成 FASTQ
    4. bwa mem 比对到 hg38 → sorted BAM
    5. samtools index
"""

import os
import subprocess
import sys
from pathlib import Path

SAMTOOLS = "/home/ladydd/miniconda3/envs/ychr/bin/samtools"
BWA = "/home/ladydd/miniconda3/envs/ychr/bin/bwa"
HG38_FA = "/home/ladydd/reference/hg38/genome/hs38.fa"

# 5 个 1240K 位点 + 对应 alt 碱基
POSITIONS = [
    ("chr1", 817186, "A"),   # ref=G alt=A
    ("chr1", 841166, "G"),   # ref=A alt=G
    ("chr1", 897538, "C"),   # ref=T alt=C
    ("chr1", 906633, "G"),   # ref=T alt=G
    ("chr1", 911484, "C"),   # ref=G alt=C
]

READ_LEN_HALF = 50   # 每条 read 100bp, 位点在中心
READS_PER_POS = 3    # 每个位点 3 条 read


def run(cmd, capture=False):
    print(f"$ {cmd}")
    if capture:
        return subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True).stdout
    subprocess.run(cmd, shell=True, check=True)


def get_ref_context(chrom, pos, half_len):
    """取 pos 前后 half_len bp，返回 100bp 序列 (pos 在中心)"""
    start = pos - half_len
    end = pos + half_len - 1  # 100bp 总长
    region = f"{chrom}:{start}-{end}"
    out = subprocess.run(
        [SAMTOOLS, "faidx", HG38_FA, region],
        check=True, capture_output=True, text=True
    ).stdout
    seq = "".join(line.strip() for line in out.splitlines() if not line.startswith(">"))
    return seq.upper()


def build_fastq(output_fq, sample_name):
    """为每个位点生成带 alt 碱基的 read"""
    with open(output_fq, "w") as f:
        for idx, (chrom, pos, alt) in enumerate(POSITIONS):
            ref_ctx = get_ref_context(chrom, pos, READ_LEN_HALF)
            # 替换中心碱基为 alt
            # faidx chr:start-end 区间 [start, end] 1-based 闭区间，返回长度 end-start+1
            # 我们取 [pos-50, pos+49]，共 100bp；pos 在 read 中的 0-based 索引是 50
            assert len(ref_ctx) == 2 * READ_LEN_HALF, f"Got {len(ref_ctx)} bp"
            alt_read = ref_ctx[:READ_LEN_HALF] + alt + ref_ctx[READ_LEN_HALF + 1:]
            # 质量串: Q40 = 'I'
            qual = "I" * len(alt_read)
            for r in range(READS_PER_POS):
                read_id = f"{sample_name}_{chrom}_{pos}_r{r}"
                f.write(f"@{read_id}\n{alt_read}\n+\n{qual}\n")
    print(f"  wrote {output_fq}")


def main():
    if len(sys.argv) < 3:
        print("Usage: make_test_bam.py <output_dir> <sample_name>")
        sys.exit(1)

    out_dir = Path(sys.argv[1])
    sample = sys.argv[2]
    out_dir.mkdir(parents=True, exist_ok=True)

    fq = out_dir / f"{sample}.fq"
    sam = out_dir / f"{sample}.sam"
    bam = out_dir / f"{sample}.bam"
    sorted_bam = out_dir / f"{sample}.sorted.bam"

    print(f"[1/4] 生成 FASTQ")
    build_fastq(fq, sample)

    print(f"[2/4] BWA-MEM 比对")
    # 单端 read，简化
    run(
        f'{BWA} mem -R "@RG\\tID:{sample}\\tSM:{sample}\\tPL:ILLUMINA" '
        f'{HG38_FA} {fq} > {sam} 2>/dev/null'
    )

    print(f"[3/4] SAM → 排序 BAM")
    run(f"{SAMTOOLS} sort -o {sorted_bam} {sam}")

    print(f"[4/4] 建索引")
    run(f"{SAMTOOLS} index {sorted_bam}")

    # 清理中间文件
    for f in [fq, sam]:
        if f.exists():
            f.unlink()

    if bam.exists():
        bam.unlink()

    print(f"\n✅ 测试 BAM 就绪: {sorted_bam}")
    # 统计
    n = run(f"{SAMTOOLS} view -c {sorted_bam}", capture=True).strip()
    print(f"   read 数: {n}")
    mapped = run(f"{SAMTOOLS} view -c -F 4 {sorted_bam}", capture=True).strip()
    print(f"   比对上: {mapped}")


if __name__ == "__main__":
    main()
