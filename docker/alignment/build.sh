#!/bin/bash
# 构建比对专用 Docker 镜像 (内含 hg38 参考基因组)
# 全部从本地复制，不需要联网
# 用法: bash docker/alignment/build.sh
#
# 注意: 镜像约 10GB+，包含完整 hg38 参考基因组和 BWA 索引

set -e

IMAGE_NAME="wgs-align"
VERSION="1.0.0"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REF_DIR="/home/ladydd/reference"
CONDA_ENV="/home/ladydd/miniconda3/envs/ychr"

echo "=== 构建 WGS 比对镜像 (hg38, 纯本地构建) ==="
echo "镜像: ${IMAGE_NAME}:${VERSION}"
echo ""

# 准备构建上下文
BUILD_DIR="${SCRIPT_DIR}/build_context"
mkdir -p "${BUILD_DIR}/reference/hg38/genome"
mkdir -p "${BUILD_DIR}/tools/bin"
mkdir -p "${BUILD_DIR}/tools/lib"

# ===== 复制生信工具 (从 conda 环境) =====
echo "--- 复制生信工具 ---"
for tool in bwa samtools; do
    src="${CONDA_ENV}/bin/${tool}"
    dst="${BUILD_DIR}/tools/bin/${tool}"
    if [ -f "$src" ] && [ ! -f "$dst" ]; then
        cp "$src" "$dst"
        echo "  复制: ${tool}"
    fi
done

# 复制依赖库
echo "--- 复制依赖库 ---"
for lib in libhts.so* libz.so* libdeflate.so* liblzma.so* libbz2.so* libncursesw.so* libtinfow.so*; do
    for f in ${CONDA_ENV}/lib/${lib}; do
        if [ -f "$f" ]; then
            fname=$(basename "$f")
            dst="${BUILD_DIR}/tools/lib/${fname}"
            if [ ! -e "$dst" ]; then
                cp -P "$f" "$dst"
                echo "  复制: ${fname}"
            fi
        fi
    done
done

# ===== 复制 hg38 参考基因组 =====
echo ""
echo "--- 复制 hg38 参考基因组 (约 9GB，请耐心等待) ---"
for f in hs38.fa hs38.fa.fai hs38.fa.bwt hs38.fa.amb hs38.fa.ann hs38.fa.pac hs38.fa.sa; do
    src="${REF_DIR}/genomes/${f}"
    dst="${BUILD_DIR}/reference/hg38/genome/${f}"
    if [ -f "$src" ] && [ ! -f "$dst" ]; then
        echo "  复制: ${f} ($(du -h "$src" | cut -f1))"
        cp "$src" "$dst"
    fi
done

# 复制 Dockerfile 和脚本
cp "${SCRIPT_DIR}/Dockerfile" "${BUILD_DIR}/"
cp "${SCRIPT_DIR}/align.sh" "${BUILD_DIR}/"

echo ""
echo "--- 构建 Docker 镜像 ---"
docker build -t ${IMAGE_NAME}:${VERSION} -t ${IMAGE_NAME}:latest "${BUILD_DIR}"

echo ""
echo "=== 构建完成 ==="
echo "镜像大小:"
docker images ${IMAGE_NAME}:latest --format "  {{.Size}}"
echo ""
echo "导出镜像 (搬迁用):"
echo "  docker save ${IMAGE_NAME}:latest | gzip > ${IMAGE_NAME}.tar.gz"
echo ""
echo "使用方法:"
echo "  docker run --rm -v /path/to/data:/data ${IMAGE_NAME} sample_id R1.fastq.gz R2.fastq.gz"
echo ""
echo "清理构建上下文 (可选，释放 ~9GB):"
echo "  rm -rf ${BUILD_DIR}"
