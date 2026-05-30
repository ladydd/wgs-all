#!/bin/bash
# 比对前预检 - 检查资源是否足够
# 用法: bash preflight_check.sh <r1.fastq.gz> <r2.fastq.gz> [output_dir]
#
# 检查项:
#   1. 内存是否够 (BWA 8GB + sort)
#   2. 磁盘是否够 (BAM ≈ 输入的 0.8x, 临时文件 ≈ 输入的 3x)
#   3. 推荐最优参数

set -e

R1=${1:?"用法: preflight_check.sh <r1.fastq.gz> <r2.fastq.gz> [output_dir]"}
R2=${2:?"缺少 R2 文件"}
OUTPUT_DIR=${3:-"."}

echo "=== 比对预检 ==="
echo ""

# ===== 输入文件大小 =====
R1_SIZE_GB=$(du -BG "$R1" 2>/dev/null | awk '{print int($1)}')
R2_SIZE_GB=$(du -BG "$R2" 2>/dev/null | awk '{print int($1)}')
INPUT_TOTAL_GB=$((R1_SIZE_GB + R2_SIZE_GB))
echo "输入文件:"
echo "  R1: ${R1_SIZE_GB}GB"
echo "  R2: ${R2_SIZE_GB}GB"
echo "  合计: ${INPUT_TOTAL_GB}GB"
echo ""

# ===== 内存检查 =====
TOTAL_MEM_GB=$(free -g | awk '/Mem:/{print $2}')
AVAIL_MEM_GB=$(free -g | awk '/Mem:/{print $7}')
echo "内存:"
echo "  总计: ${TOTAL_MEM_GB}GB"
echo "  可用: ${AVAIL_MEM_GB}GB"

# BWA 需要 ~8GB, 最少需要 12GB 才能跑
MIN_MEM=12
if [ "$AVAIL_MEM_GB" -lt "$MIN_MEM" ]; then
    echo "  ⚠️  可用内存不足 ${MIN_MEM}GB，可能 OOM!"
    echo "  建议: 关闭其他程序，或用 SAFE_MODE=1"
    MEM_OK=0
else
    echo "  ✓ 内存充足"
    MEM_OK=1
fi
echo ""

# ===== 磁盘检查 =====
DISK_AVAIL_GB=$(df -BG "$OUTPUT_DIR" | tail -1 | awk '{print int($4)}')
# 预估需要: BAM ≈ 输入的 0.8x, 临时文件 ≈ 输入的 2x (sort 过程中)
BAM_EST_GB=$(( INPUT_TOTAL_GB * 8 / 10 ))
TEMP_EST_GB=$(( INPUT_TOTAL_GB * 2 ))
DISK_NEED_GB=$(( BAM_EST_GB + TEMP_EST_GB + 5 ))  # +5GB 余量

echo "磁盘 (${OUTPUT_DIR}):"
echo "  可用: ${DISK_AVAIL_GB}GB"
echo "  预估需要: ${DISK_NEED_GB}GB (BAM ~${BAM_EST_GB}GB + 临时 ~${TEMP_EST_GB}GB)"

if [ "$DISK_AVAIL_GB" -lt "$DISK_NEED_GB" ]; then
    echo "  ⚠️  磁盘空间可能不足!"
    DISK_OK=0
else
    echo "  ✓ 磁盘充足"
    DISK_OK=1
fi
echo ""

# ===== 推荐参数 =====
CPU_COUNT=$(nproc)
# 推荐线程: CPU 数 - 2，但不超过 16 (更多线程内存压力大，收益递减)
REC_THREADS=$((CPU_COUNT - 2))
[ "$REC_THREADS" -lt 2 ] && REC_THREADS=2
[ "$REC_THREADS" -gt 16 ] && REC_THREADS=16

# 推荐 sort 内存: (可用内存 * 60% - 8GB BWA) / 线程数
USABLE_MEM=$(( AVAIL_MEM_GB * 60 / 100 - 8 ))
[ "$USABLE_MEM" -lt 2 ] && USABLE_MEM=2
REC_SORT=$(( USABLE_MEM / REC_THREADS ))
[ "$REC_SORT" -lt 1 ] && REC_SORT=1
[ "$REC_SORT" -gt 4 ] && REC_SORT=4

# 预估时间 (非常粗略: 1GB 压缩 FASTQ ≈ 30分钟 @ 8线程)
EST_HOURS=$(( INPUT_TOTAL_GB * 30 / 60 / (REC_THREADS / 8 + 1) ))
[ "$EST_HOURS" -lt 1 ] && EST_HOURS=1

echo "推荐参数 (${CPU_COUNT} 核, ${AVAIL_MEM_GB}GB 可用):"
echo "  线程: ${REC_THREADS}"
echo "  排序内存: ${REC_SORT}G/线程"
echo "  总内存预估: $(( 8 + REC_SORT * REC_THREADS ))GB"
echo "  预估耗时: ~${EST_HOURS} 小时"
echo ""

# ===== 总结 =====
if [ "$MEM_OK" = "1" ] && [ "$DISK_OK" = "1" ]; then
    echo "✓ 预检通过，可以开始比对"
    echo ""
    echo "推荐命令:"
    echo "  docker run --rm \\"
    echo "    -e THREADS=${REC_THREADS} \\"
    echo "    -e SORT_MEM=${REC_SORT}G \\"
    echo "    -v ... wgs-align sample_id R1.fastq.gz R2.fastq.gz"
else
    echo "⚠️  预检有警告，请处理后再开始"
    exit 1
fi
