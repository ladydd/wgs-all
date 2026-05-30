# 批量比对脚本 - 自动扫描目录中的 FASTQ 对，逐个比对
# 用法: bash batch_align.sh /data/yunnan/node_data /data/yunnan/bam_output [threads]
#
# 会自动识别 *_combined_R1.fastq.gz 和 *_combined_R2.fastq.gz 配对
# 输出: /output_dir/{sample_id}/{sample_id}.sorted.bam

set -e

FASTQ_DIR=${1:?"用法: batch_align.sh <fastq_dir> <output_dir> [threads]"}
OUTPUT_DIR=${2:?"缺少输出目录"}
THREADS=${3:-0}  # 0=自动检测

IMAGE="wgs-align:latest"

# 检查镜像
if ! docker image inspect ${IMAGE} > /dev/null 2>&1; then
    echo "错误: Docker 镜像 ${IMAGE} 不存在"
    echo "请先加载: docker load < wgs-align.tar.gz"
    exit 1
fi

# 创建输出目录
mkdir -p "${OUTPUT_DIR}"

# 日志文件
LOG_FILE="${OUTPUT_DIR}/batch_align.log"
echo "=== 批量比对开始: $(date) ===" | tee -a "$LOG_FILE"
echo "FASTQ 目录: ${FASTQ_DIR}" | tee -a "$LOG_FILE"
echo "输出目录: ${OUTPUT_DIR}" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 扫描所有 R1 文件，提取样本 ID
TOTAL=0
DONE=0
FAILED=0

# 收集所有样本 ID
SAMPLES=()
for r1 in ${FASTQ_DIR}/*_combined_R1.fastq.gz; do
    [ -f "$r1" ] || continue
    sample_id=$(basename "$r1" | sed 's/_combined_R1.fastq.gz//')
    SAMPLES+=("$sample_id")
done

TOTAL=${#SAMPLES[@]}
echo "找到 ${TOTAL} 个样本" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 逐个比对
for sample_id in "${SAMPLES[@]}"; do
    r1="${FASTQ_DIR}/${sample_id}_combined_R1.fastq.gz"
    r2="${FASTQ_DIR}/${sample_id}_combined_R2.fastq.gz"
    
    # 检查 R2 是否存在
    if [ ! -f "$r2" ]; then
        echo "[跳过] ${saßßmple_id}: R2 文件不存在" | tee -a "$LOG_FILE"
        FAILED=$((FAILED + 1))
        continue
    fi
    
    # 检查是否已经比对过
    bam_file="${OUTPUT_DIR}/${sample_id}/${sample_id}.sorted.bam"
    if [ -f "$bam_file" ]; then
        echo "[跳过] ${sample_id}: BAM 已存在" | tee -a "$LOG_FILE"
        DONE=$((DONE + 1))
        continue
    fi
    
    # 运行比对
    DONE=$((DONE + 1))
    echo "[${DONE}/${TOTAL}] 比对: ${sample_id} ($(date '+%H:%M:%S'))" | tee -a "$LOG_FILE"
    
    # 挂载 FASTQ 目录和输出目录
    if docker run --rm \
        -v "${FASTQ_DIR}:/data/fastq:ro" \
        -v "${OUTPUT_DIR}:/data/output" \
        -e THREADS=${THREADS} \
        ${IMAGE} \
        "${sample_id}" \
        "/data/fastq/${sample_id}_combined_R1.fastq.gz" \
        "/data/fastq/${sample_id}_combined_R2.fastq.gz" \
        2>&1 | tee -a "$LOG_FILE"; then
        echo "[完成] ${sample_id}" | tee -a "$LOG_FILE"
    else
        echo "[失败] ${sample_id}" | tee -a "$LOG_FILE"
        FAILED=$((FAILED + 1))
    fi
    
    echo "" | tee -a "$LOG_FILE"
done

echo "=== 批量比对结束: $(date) ===" | tee -a "$LOG_FILE"
echo "总计: ${TOTAL}, 完成: ${DONE}, 失败: ${FAILED}" | tee -a "$LOG_FILE"
