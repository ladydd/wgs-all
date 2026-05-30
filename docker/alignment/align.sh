#!/bin/bash
# WGS 比对脚本 - hg38
# 用法: 
#   docker run -v /path/to/data:/data wgs-align sample_id R1.fastq.gz R2.fastq.gz
#   docker run -v /path/to/data:/data wgs-align sample_id R1.fastq.gz R2.fastq.gz [threads]
#
# 输入文件放在 /data 目录下，输出也在 /data 目录下
# 输出: /data/{sample_id}/{sample_id}.sorted.bam + .bai

set -e

# 参数
SAMPLE_ID=${1:?"用法: align.sh <sample_id> <r1.fastq.gz> <r2.fastq.gz> [threads]"}
R1=${2:?"缺少 R1 文件"}
R2=${3:?"缺少 R2 文件"}

# 线程数: 命令行参数 > 环境变量 > 自动检测
if [ -n "$4" ]; then
    THREADS=$4
elif [ "$THREADS" = "0" ] || [ -z "$THREADS" ]; then
    THREADS=$(($(nproc) - 2))
    [ "$THREADS" -lt 2 ] && THREADS=2
fi

# ===== 内存安全策略 =====
# BWA 固定占用约 8GB (加载 hg38 索引)
# samtools sort 每线程分配内存，不够时自动写临时文件（慢但不 OOM）
#
# 用户可通过环境变量覆盖:
#   THREADS     - 线程数
#   MAX_MEM_GB  - 最大总内存限制 (0=自动)
#   SORT_MEM    - 直接指定每线程排序内存 (如 "1G", "768M")
#   SAFE_MODE   - 设为 1 则用最保守配置

TOTAL_MEM_GB=$(free -g | awk '/Mem:/{print $2}')

if [ "${SAFE_MODE}" = "1" ]; then
    # 安全模式: 最保守，绝不 OOM
    # 每线程只给 768M，sort 会频繁写磁盘但绝对安全
    SORT_MEM="768M"
    # 线程也压低
    [ "$THREADS" -gt 4 ] && THREADS=4
    echo "  [安全模式] 线程=${THREADS}, 排序内存=${SORT_MEM}/线程"
elif [ -n "$SORT_MEM" ] && [ "$SORT_MEM" != "0" ]; then
    # 用户直接指定了 SORT_MEM，尊重用户
    echo "  [用户指定] 排序内存=${SORT_MEM}/线程"
else
    # 自动计算: 总内存的 60% 留给比对流程
    if [ -z "$MAX_MEM_GB" ] || [ "$MAX_MEM_GB" = "0" ]; then
        MAX_MEM_GB=$(( TOTAL_MEM_GB * 60 / 100 ))
    fi
    
    # BWA 固定 8GB，剩余给 sort
    BWA_MEM=8
    SORT_TOTAL=$(( MAX_MEM_GB - BWA_MEM ))
    [ "$SORT_TOTAL" -lt 2 ] && SORT_TOTAL=2
    
    # 每线程排序内存 (最低 768M，最高 4G)
    SORT_PER_THREAD=$(( SORT_TOTAL / THREADS ))
    [ "$SORT_PER_THREAD" -lt 1 ] && SORT_PER_THREAD=1
    [ "$SORT_PER_THREAD" -gt 4 ] && SORT_PER_THREAD=4
    SORT_MEM="${SORT_PER_THREAD}G"
fi

# 路径
REF="/reference/hg38/genome/hs38.fa"
OUTPUT_BASE="${OUTPUT_BASE:-/data/output}"
OUTPUT_DIR="${OUTPUT_BASE}/${SAMPLE_ID}"
SORTED_BAM="${OUTPUT_DIR}/${SAMPLE_ID}.sorted.bam"
TMP_DIR="${OUTPUT_DIR}/tmp"

# 处理输入文件路径 (如果不是绝对路径，加上 /data 前缀)
[[ "$R1" != /* ]] && R1="/data/${R1}"
[[ "$R2" != /* ]] && R2="/data/${R2}"

# 检查
if [ ! -f "$R1" ]; then
    echo "错误: R1 文件不存在: $R1"
    exit 1
fi
if [ ! -f "$R2" ]; then
    echo "错误: R2 文件不存在: $R2"
    exit 1
fi

# 创建输出目录
mkdir -p "$OUTPUT_DIR"
mkdir -p "$TMP_DIR"

echo "=========================================="
echo "  WGS 比对 (hg38)"
echo "=========================================="
echo "  样本 ID:  ${SAMPLE_ID}"
echo "  R1:       ${R1}"
echo "  R2:       ${R2}"
echo "  线程数:   ${THREADS}"
echo "  排序内存: ${SORT_MEM}/线程"
echo "  输出:     ${SORTED_BAM}"
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

echo "[$(date '+%H:%M:%S')] Step 2: 建立索引..."
samtools index -@ ${THREADS} "${SORTED_BAM}"

# Step 3: 统计
echo "[$(date '+%H:%M:%S')] Step 3: 统计..."
samtools flagstat "${SORTED_BAM}" > "${OUTPUT_DIR}/${SAMPLE_ID}.flagstat.txt"
samtools flagstat "${SORTED_BAM}"

# 清理临时文件
rm -rf "$TMP_DIR"

echo ""
echo "=========================================="
echo "  完成!"
echo "  BAM:   ${SORTED_BAM}"
echo "  索引:  ${SORTED_BAM}.bai"
echo "  统计:  ${OUTPUT_DIR}/${SAMPLE_ID}.flagstat.txt"
echo "=========================================="
