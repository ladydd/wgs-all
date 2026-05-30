#!/bin/bash
# WGS 比对脚本 - hg19 (hs37d5)
# 用法:
#   docker run -v /data:/data wgs-all align-hg19 sample_id R1.fastq.gz R2.fastq.gz [threads]
#
# 输出: /data/output/{sample_id}/{sample_id}.sorted.bam + .bai
# 注意: 产出 BAM 染色体命名无 chr 前缀 (1/2/.../X/Y/MT)

set -e

SAMPLE_ID=${1:?"用法: align-hg19 <sample_id> <r1.fastq.gz> <r2.fastq.gz> [threads]"}
R1=${2:?"缺少 R1 文件"}
R2=${3:?"缺少 R2 文件"}

# 线程数
if [ -n "$4" ]; then
    THREADS=$4
elif [ "$THREADS" = "0" ] || [ -z "$THREADS" ]; then
    THREADS=$(($(nproc) - 2))
    [ "$THREADS" -lt 2 ] && THREADS=2
fi

# 内存策略 (和 align.sh 相同逻辑)
if [ "${SAFE_MODE}" = "1" ]; then
    SORT_MEM="768M"
    [ "$THREADS" -gt 4 ] && THREADS=4
elif [ -n "$SORT_MEM" ] && [ "$SORT_MEM" != "0" ]; then
    :
else
    TOTAL_MEM_GB=$(free -g 2>/dev/null | awk '/Mem:/{print $2}' || echo 16)
    MAX_MEM_GB=${MAX_MEM_GB:-$(( TOTAL_MEM_GB * 60 / 100 ))}
    BWA_MEM=8
    SORT_TOTAL=$(( MAX_MEM_GB - BWA_MEM ))
    [ "$SORT_TOTAL" -lt 2 ] && SORT_TOTAL=2
    SORT_PER_THREAD=$(( SORT_TOTAL / THREADS ))
    [ "$SORT_PER_THREAD" -lt 1 ] && SORT_PER_THREAD=1
    [ "$SORT_PER_THREAD" -gt 4 ] && SORT_PER_THREAD=4
    SORT_MEM="${SORT_PER_THREAD}G"
fi

# 路径
REF="/reference/hg19/genome/hs37d5.fa"
OUTPUT_BASE="${OUTPUT_BASE:-/data/output}"
OUTPUT_DIR="${OUTPUT_BASE}/${SAMPLE_ID}"
SORTED_BAM="${OUTPUT_DIR}/${SAMPLE_ID}.sorted.bam"
TMP_DIR="${OUTPUT_DIR}/tmp"

# 输入文件路径处理
[[ "$R1" != /* ]] && R1="/data/${R1}"
[[ "$R2" != /* ]] && R2="/data/${R2}"

# 检查
[ ! -f "$R1" ] && echo "错误: R1 不存在: $R1" && exit 1
[ ! -f "$R2" ] && echo "错误: R2 不存在: $R2" && exit 1
[ ! -f "$REF" ] && echo "错误: 参考基因组不存在: $REF" && exit 1

mkdir -p "$OUTPUT_DIR" "$TMP_DIR"

echo "=========================================="
echo "  WGS 比对 (hg19 / hs37d5 / GRCh37)"
echo "=========================================="
echo "  样本 ID:  ${SAMPLE_ID}"
echo "  R1:       ${R1}"
echo "  R2:       ${R2}"
echo "  参考:     hs37d5 (GRCh37 + decoy)"
echo "  线程数:   ${THREADS}"
echo "  排序内存: ${SORT_MEM}/线程"
echo "  输出:     ${SORTED_BAM}"
echo "  染色体:   无 chr 前缀 (1/2/.../X/Y/MT)"
echo "=========================================="
echo ""

# Step 1: BWA-MEM + samtools sort
echo "[$(date '+%H:%M:%S')] Step 1: BWA-MEM 比对 + 排序..."
bwa mem -t ${THREADS} \
    -R "@RG\tID:${SAMPLE_ID}\tSM:${SAMPLE_ID}\tPL:ILLUMINA" \
    "${REF}" "${R1}" "${R2}" | \
    samtools sort -@ ${THREADS} -m ${SORT_MEM} \
    -T "${TMP_DIR}/${SAMPLE_ID}.tmp" \
    -o "${SORTED_BAM}"

# Step 2: 建索引
echo "[$(date '+%H:%M:%S')] Step 2: 建立索引..."
samtools index -@ ${THREADS} "${SORTED_BAM}"

# Step 3: 统计
echo "[$(date '+%H:%M:%S')] Step 3: 统计..."
samtools flagstat "${SORTED_BAM}" > "${OUTPUT_DIR}/${SAMPLE_ID}.flagstat.txt"
samtools flagstat "${SORTED_BAM}"

# 清理
rm -rf "$TMP_DIR"

echo ""
echo "=========================================="
echo "  完成!"
echo "  BAM:   ${SORTED_BAM}"
echo "  索引:  ${SORTED_BAM}.bai"
echo "  统计:  ${OUTPUT_DIR}/${SAMPLE_ID}.flagstat.txt"
echo "  参考:  hs37d5 (hg19/GRCh37, 无 chr 前缀)"
echo "=========================================="
