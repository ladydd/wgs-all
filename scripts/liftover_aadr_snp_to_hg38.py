#!/usr/bin/env python3
"""
把 AADR .snp 文件从 hg19 反向 liftOver 到 hg38。

输入（EIGENSTRAT 6 列）:
    rsID  chrom  genetic_pos  phys_pos  ref  alt
    例: rs3094315  1  0.020130  752566  G  A

输出:
    1. <prefix>.hg38.snp  — 6 列 EIGENSTRAT 格式，坐标已转成 hg38 (无 chr 前缀，染色体用数字)
    2. <prefix>.hg38.pos  — 2 列 samtools mpileup 位点表 (无 chr 前缀，染色体用数字)
    3. <prefix>.hg38.chr.pos  — 2 列 samtools mpileup 位点表 (带 chr 前缀)
    4. <prefix>.liftover_log.tsv  — 失败/多映射/跨染色体的位点记录

染色体编码约定 (AADR):
    1-22 → 常染色体
    23 → X
    24 → Y
    25 → MT (1240K 不含)

LiftOver 输入:
    chain 文件: /home/ladydd/reference/hg19ToHg38.over.chain.gz
    (Ensembl 版本，源端同时支持带/不带 chr 前缀，目标端无 chr)
"""

import argparse
import gzip
import sys
from pathlib import Path
from typing import Optional, Tuple

from pyliftover import LiftOver


# AADR 数字染色体 ↔ pyliftover 用的 UCSC 命名
NUMERIC_TO_UCSC = {str(i): f"chr{i}" for i in range(1, 23)}
NUMERIC_TO_UCSC.update({"23": "chrX", "24": "chrY", "25": "chrM"})

# 反向查表时兼容两种风格：
#   Ensembl chain 目标端是 "1"/"X"/"Y"/"MT"（无 chr 前缀）
#   UCSC chain 目标端是 "chr1"/"chrX"/"chrY"/"chrM"
# 都归一到 AADR 数字编码
UCSC_TO_NUMERIC = {v: k for k, v in NUMERIC_TO_UCSC.items()}
UCSC_TO_NUMERIC.update({str(i): str(i) for i in range(1, 23)})
UCSC_TO_NUMERIC.update({"X": "23", "Y": "24", "MT": "25", "M": "25"})


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snp", required=True, help="输入 AADR .snp 文件 (hg19 6列格式)")
    ap.add_argument("--chain", required=True, help="hg19ToHg38 chain 文件 (.gz)")
    ap.add_argument("--out-prefix", required=True, help="输出前缀")
    return ap.parse_args()


def load_snp(path: str):
    """解析 AADR 6 列 .snp 格式"""
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) != 6:
                print(f"[warn] line {lineno}: 期望 6 列实际 {len(parts)}，跳过: {line[:80]}", file=sys.stderr)
                continue
            rsid, chrom, gen_pos, phys_pos, ref, alt = parts
            yield lineno, rsid, chrom, gen_pos, int(phys_pos), ref, alt


def liftover_coord(lo: LiftOver, chrom_numeric: str, pos: int) -> Optional[Tuple[str, int, str]]:
    """
    把 hg19 (chrom_numeric, pos) 转成 hg38。

    Returns:
        (new_chrom_numeric, new_pos, strand)  成功
        None  失败或跨染色体
    """
    ucsc_chrom = NUMERIC_TO_UCSC.get(chrom_numeric)
    if ucsc_chrom is None:
        return None

    # pyliftover 用 0-based 输入，EIGENSTRAT 的 phys_pos 是 1-based
    # UCSC liftOver 规范: 输入 0-based，输出 0-based
    results = lo.convert_coordinate(ucsc_chrom, pos - 1)
    if not results:
        return None

    # 多映射取第一条（UCSC 标准做法，chain 按打分排序）
    new_chrom_ucsc, new_pos_0based, strand, _conv_chain_id = results[0]
    new_chrom_numeric = UCSC_TO_NUMERIC.get(new_chrom_ucsc)
    if new_chrom_numeric is None:
        # 落到 alt contig / patch，丢弃
        return None

    # 跨染色体丢弃（古 DNA 分析不接受跨染色体映射）
    if new_chrom_numeric != chrom_numeric:
        return None

    return new_chrom_numeric, new_pos_0based + 1, strand  # 转回 1-based


def main():
    args = parse_args()

    chain = Path(args.chain)
    if not chain.exists():
        sys.exit(f"chain 文件不存在: {chain}")

    out_prefix = Path(args.out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    # 注意: 不能用 with_suffix()，因为前缀里可能包含 "." (如 v42.4.1240K.hg38)
    snp_out = out_prefix.parent / (out_prefix.name + ".snp")
    pos_out = out_prefix.parent / (out_prefix.name + ".pos")           # 无 chr 前缀
    pos_chr_out = out_prefix.parent / (out_prefix.name + ".chr.pos")  # 带 chr 前缀
    log_out = out_prefix.parent / (out_prefix.name + ".liftover_log.tsv")

    print(f"[info] 加载 chain: {chain}", file=sys.stderr)
    lo = LiftOver(str(chain))
    print(f"[info] chain 加载完成", file=sys.stderr)

    total = 0
    ok = 0
    fail_no_map = 0
    fail_cross_chrom = 0
    fail_alt_contig = 0
    strand_flipped = 0

    with open(snp_out, "w") as f_snp, \
         open(pos_out, "w") as f_pos, \
         open(pos_chr_out, "w") as f_pos_chr, \
         open(log_out, "w") as f_log:

        f_log.write("lineno\trsid\thg19_chrom\thg19_pos\thg38_chrom\thg38_pos\tstatus\n")

        for lineno, rsid, chrom, gen_pos, phys_pos, ref, alt in load_snp(args.snp):
            total += 1
            if total % 200000 == 0:
                print(f"[info] 处理 {total} 位点 ({ok} 成功)...", file=sys.stderr)

            ucsc_chrom = NUMERIC_TO_UCSC.get(chrom)
            if ucsc_chrom is None:
                fail_alt_contig += 1
                f_log.write(f"{lineno}\t{rsid}\t{chrom}\t{phys_pos}\t.\t.\tunknown_chrom\n")
                continue

            results = lo.convert_coordinate(ucsc_chrom, phys_pos - 1)
            if not results:
                fail_no_map += 1
                f_log.write(f"{lineno}\t{rsid}\t{chrom}\t{phys_pos}\t.\t.\tno_mapping\n")
                continue

            new_chrom_ucsc, new_pos_0based, strand, _ = results[0]
            new_chrom_numeric = UCSC_TO_NUMERIC.get(new_chrom_ucsc)
            if new_chrom_numeric is None:
                fail_alt_contig += 1
                f_log.write(f"{lineno}\t{rsid}\t{chrom}\t{phys_pos}\t{new_chrom_ucsc}\t{new_pos_0based+1}\talt_contig\n")
                continue

            if new_chrom_numeric != chrom:
                fail_cross_chrom += 1
                f_log.write(f"{lineno}\t{rsid}\t{chrom}\t{phys_pos}\t{new_chrom_numeric}\t{new_pos_0based+1}\tcross_chrom\n")
                continue

            new_pos = new_pos_0based + 1

            # 负链 - 坐标已由 pyliftover 处理，但等位基因需要 flip 吗？
            # 对于 SNP 位点：liftOver 只转坐标，不碰 ref/alt。下游 pileupCaller
            # 会从 BAM 重新 call 基因型，不依赖我们的 ref/alt（但 .snp 的 ref/alt
            # 字段是 EIGENSTRAT 元数据，定义"这个位点哪个是 0/1 allele"）。
            # 保守做法：记录 strand，但 ref/alt 保持 AADR 原值。下游合并时以 AADR 为准。
            if strand == "-":
                strand_flipped += 1

            # 写 .snp
            f_snp.write(f"{rsid:>20s}\t{new_chrom_numeric}\t{gen_pos}\t{new_pos}\t{ref}\t{alt}\n")
            # 写 .pos（无 chr）
            f_pos.write(f"{new_chrom_numeric}\t{new_pos}\n")
            # 写 .chr.pos
            chr_name = NUMERIC_TO_UCSC[new_chrom_numeric]
            f_pos_chr.write(f"{chr_name}\t{new_pos}\n")
            ok += 1

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"[完成] 总位点: {total}", file=sys.stderr)
    print(f"  成功转换: {ok}  ({100*ok/total:.2f}%)", file=sys.stderr)
    print(f"  无映射:   {fail_no_map}  ({100*fail_no_map/total:.2f}%)", file=sys.stderr)
    print(f"  跨染色体: {fail_cross_chrom}  ({100*fail_cross_chrom/total:.4f}%)", file=sys.stderr)
    print(f"  alt contig: {fail_alt_contig}  ({100*fail_alt_contig/total:.4f}%)", file=sys.stderr)
    print(f"  负链位点: {strand_flipped}  ({100*strand_flipped/total:.2f}%)", file=sys.stderr)

    # hg19 → hg38 后 chrom+pos 顺序可能被打乱 (局部染色体结构重排)
    # pileupCaller 严格要求 .snp/.pos 按 chrom+pos 升序，需要重新排序
    print(f"\n[排序] 按 hg38 chrom+pos 重排输出文件...", file=sys.stderr)
    _sort_in_place(snp_out, chrom_col=1, pos_col=3)
    _sort_in_place(pos_out, chrom_col=0, pos_col=1)
    _sort_in_place(pos_chr_out, chrom_col=0, pos_col=1, chrom_transform=lambda c: c.lstrip("chr"))

    print(f"\n输出文件:", file=sys.stderr)
    print(f"  SNP:    {snp_out}", file=sys.stderr)
    print(f"  POS:    {pos_out}", file=sys.stderr)
    print(f"  CHRPOS: {pos_chr_out}", file=sys.stderr)
    print(f"  LOG:    {log_out}", file=sys.stderr)


def _sort_in_place(path: Path, chrom_col: int, pos_col: int, chrom_transform=None):
    """
    就地排序一个文本文件，按 (chrom 数字序, pos 数字序)。

    Args:
        path: 文件路径
        chrom_col: 染色体列 index (0-based)
        pos_col: 位置列 index
        chrom_transform: 可选，对 chrom 值做变换后再排序 (如去 chr 前缀)
    """
    def chrom_key(c: str) -> int:
        if chrom_transform:
            c = chrom_transform(c)
        try:
            return int(c)
        except ValueError:
            # X=23, Y=24, MT=25 (但 AADR 里已经是数字了，这里只为健壮)
            return {"X": 23, "Y": 24, "MT": 25, "M": 25}.get(c, 99)

    with open(path) as f:
        lines = f.readlines()

    def line_key(line):
        parts = line.split()
        return (chrom_key(parts[chrom_col]), int(parts[pos_col]))

    lines.sort(key=line_key)
    with open(path, "w") as f:
        f.writelines(lines)


if __name__ == "__main__":
    main()
