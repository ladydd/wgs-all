#!/bin/bash
# 构建全能镜像 wgs-all:latest
# 继承 wgs-align:latest，增加 Python + pileupCaller + EIGENSTRAT 位点 + app 代码
#
# 依赖:
#   • wgs-align:latest 镜像已存在 (`docker images | grep wgs-align`)
#   • /home/ladydd/reference/population/eigenstrat/ 已有 liftOver 产物
#   • /home/ladydd/wgs-platform/adna_to_dataset/positions/ 已 git lfs pull
#   • /home/ladydd/miniconda3/envs/ychr/bin/pileupCaller 已安装
#
# 用法:
#   bash docker/eigenstrat/build.sh

set -e

IMAGE_NAME="wgs-all"
VERSION="1.3.0"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REF_DIR="/home/ladydd/reference"
CONDA_ENV="/home/ladydd/miniconda3/envs/ychr"
BUILD_DIR="${SCRIPT_DIR}/build_context"

echo "=== 构建 WGS 全能镜像 (继承 wgs-align) ==="
echo "镜像: ${IMAGE_NAME}:${VERSION}"
echo "构建上下文: ${BUILD_DIR}"
echo ""

# ---------- 前置检查 ----------
if ! docker image inspect wgs-align:latest >/dev/null 2>&1; then
    echo "❌ 前置镜像缺失: wgs-align:latest"
    echo "   请先构建基础镜像: bash docker/alignment/build.sh"
    exit 1
fi

if [ ! -f "${CONDA_ENV}/bin/pileupCaller" ]; then
    echo "❌ pileupCaller 未装: ${CONDA_ENV}/bin/pileupCaller"
    echo "   请先运行: conda install -n ychr -c bioconda sequencetools"
    exit 1
fi

EIGENSTRAT_REF="${REF_DIR}/population/eigenstrat/v42.4.1240K.hg38.snp"
if [ ! -f "${EIGENSTRAT_REF}" ]; then
    echo "❌ EIGENSTRAT 位点文件缺失: ${EIGENSTRAT_REF}"
    echo "   请先运行: python scripts/liftover_aadr_snp_to_hg38.py ..."
    exit 1
fi

AADR_HG19_SNP="${PROJECT_DIR}/adna_to_dataset/positions/v42.4.1240K.snp"
if [ ! -s "${AADR_HG19_SNP}" ] || [ "$(stat -c%s "${AADR_HG19_SNP}")" -lt 1000000 ]; then
    echo "❌ AADR hg19 .snp 不完整 (可能是 LFS 指针): ${AADR_HG19_SNP}"
    echo "   请先运行: cd adna_to_dataset && git lfs pull"
    exit 1
fi

# ---------- 准备构建上下文 ----------
echo "--- 准备构建上下文 ---"
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}/tools/lib"
mkdir -p "${BUILD_DIR}/reference/population/eigenstrat"
mkdir -p "${BUILD_DIR}/reference/aadr_positions"
cp "${PROJECT_DIR}/adna_to_dataset/positions/"* "${BUILD_DIR}/reference/aadr_positions/"
mkdir -p "${BUILD_DIR}/reference/liftover"
cp -L "${REF_DIR}/liftover/"* "${BUILD_DIR}/reference/liftover/" 2>/dev/null || true
# 确保关键 chain 文件存在
cp -L "${REF_DIR}/hg38ToHg19.over.chain.gz" "${BUILD_DIR}/reference/liftover/" 2>/dev/null || true
cp -L "${REF_DIR}/hg19ToHg38.over.chain.gz" "${BUILD_DIR}/reference/liftover/" 2>/dev/null || true

# Dockerfile + entrypoint
cp "${SCRIPT_DIR}/Dockerfile" "${BUILD_DIR}/Dockerfile"
cp "${SCRIPT_DIR}/entrypoint.sh" "${BUILD_DIR}/entrypoint.sh"

# requirements.txt (给 pip 用)
cp "${PROJECT_DIR}/requirements.txt" "${BUILD_DIR}/requirements.txt"

# admix 包 (28 个祖源计算器)
echo "  复制 admix 包..."
cp -r "${SCRIPT_DIR}/admix_repo" "${BUILD_DIR}/admix_repo"

# app/ 目录 (排除 __pycache__)
echo "  复制 app/ 代码..."
rsync -a --exclude='__pycache__' --exclude='*.pyc' \
    "${PROJECT_DIR}/app/" "${BUILD_DIR}/app/"

# pileupCaller 二进制 (解引用软链，拿真实文件)
echo "  复制 pileupCaller..."
cp -L "${CONDA_ENV}/bin/pileupCaller" "${BUILD_DIR}/tools/pileupCaller"
chmod +x "${BUILD_DIR}/tools/pileupCaller"

# bcftools + tabix (extract-chr / extract-chip / extract-1240k 需要)
echo "  复制 bcftools + tabix..."
cp -L "${CONDA_ENV}/bin/bcftools" "${BUILD_DIR}/tools/bcftools"
cp -L "${CONDA_ENV}/bin/tabix" "${BUILD_DIR}/tools/tabix"
chmod +x "${BUILD_DIR}/tools/bcftools" "${BUILD_DIR}/tools/tabix"

# smartpca + ADMIXTOOLS + PLINK + ADMIXTURE
echo "  复制 smartpca + ADMIXTOOLS + PLINK + ADMIXTURE..."
for tool in smartpca qpAdm convertf mergeit plink admixture; do
    if [ -f "${CONDA_ENV}/bin/${tool}" ]; then
        cp -L "${CONDA_ENV}/bin/${tool}" "${BUILD_DIR}/tools/${tool}"
        chmod +x "${BUILD_DIR}/tools/${tool}"
    fi
done

# 依赖库 (libgmp + libgsl + libopenblas + libcblas + libgfortran + libquadmath + libgcc_s)
echo "  复制依赖库..."
for lib in libgmp.so* libgsl.so* libopenblas.so* libcblas.so* libgfortran.so* libquadmath.so* libgcc_s.so* libcurl.so*; do
    for f in ${CONDA_ENV}/lib/${lib}; do
        if [ -e "$f" ]; then
            cp -L "$f" "${BUILD_DIR}/tools/lib/$(basename "$f")" 2>/dev/null || true
        fi
    done
done

# EIGENSTRAT 位点文件 (hg38 liftOver 版)
echo "  复制 EIGENSTRAT hg38 位点文件..."
for f in "${REF_DIR}/population/eigenstrat/"*.hg38.*; do
    if [ -f "$f" ]; then
        fname=$(basename "$f")
        cp "$f" "${BUILD_DIR}/reference/population/eigenstrat/${fname}"
    fi
done

# ===== hg19 参考基因组 (hs37d5) + BWA 索引 (~8.3GB) =====
echo ""
echo "--- 复制 hg19 参考基因组 + BWA 索引 (约 8.3GB，请耐心等待) ---"
mkdir -p "${BUILD_DIR}/reference/hg19/genome"
for f in hs37d5.fa hs37d5.fa.fai hs37d5.fa.bwt hs37d5.fa.amb hs37d5.fa.ann hs37d5.fa.pac hs37d5.fa.sa; do
    dst="${BUILD_DIR}/reference/hg19/genome/${f}"
    if [ ! -f "$dst" ]; then
        # -L 解引用软链，拿到真实文件
        src="${REF_DIR}/hg19/genome/${f}"
        if [ -e "$src" ]; then
            echo "  复制: ${f} ($(du -h "$(readlink -f "$src")" | cut -f1))"
            cp -L "$src" "$dst"
        else
            echo "  ⚠️ 缺失: ${f}"
        fi
    else
        echo "  跳过: ${f} (已存在)"
    fi
done

# ===== align-hg19.sh 脚本 =====
cp "${SCRIPT_DIR}/align-hg19.sh" "${BUILD_DIR}/align-hg19.sh"

# ===== align-t2t.sh 脚本 =====
cp "${SCRIPT_DIR}/align-t2t.sh" "${BUILD_DIR}/align-t2t.sh"

# ===== T2T 参考基因组 + BWA 索引 (约 8.1GB) =====
echo ""
echo "--- 复制 T2T 参考基因组 + BWA 索引 ---"
T2T_DIR="${BUILD_DIR}/reference/t2t/genome"
mkdir -p "${T2T_DIR}"
for f in chm13v2.fa chm13v2.fa.fai chm13v2.fa.bwt chm13v2.fa.amb chm13v2.fa.ann chm13v2.fa.pac chm13v2.fa.sa; do
    src="${REF_DIR}/t2t/genome/${f}"
    dst="${T2T_DIR}/${f}"
    if [ -f "$src" ] && [ ! -f "$dst" ]; then
        echo "  复制: ${f} ($(du -sh "$src" | cut -f1))"
        cp -L "$src" "$dst"
    elif [ -f "$dst" ]; then
        echo "  跳过: ${f} (已存在)"
    else
        echo "  ⚠️ 缺失: ${f}"
    fi
done

# ===== 芯片模板 + SNP 注释 (~406MB) =====
echo ""
echo "--- 复制芯片模板 + SNP 注释 ---"
mkdir -p "${BUILD_DIR}/reference/microarray"
cp -rL "${REF_DIR}/microarray/"* "${BUILD_DIR}/reference/microarray/"
echo "  ✓ microarray 复制完成 (模板 + SNP 注释)"

# ===== 1240K 位点文件 (15MB) =====
echo "--- 复制 1240K 位点文件 ---"
mkdir -p "${BUILD_DIR}/reference/hg38/1240k"
cp -L "${REF_DIR}/hg38/1240k/1240K_hg38.tab.gz" "${BUILD_DIR}/reference/hg38/1240k/"
echo "  ✓ 1240K_hg38.tab.gz 复制完成"

# ===== Haplogrep3 MT 单倍群工具 (~55MB) =====
echo ""
echo "--- 复制 Haplogrep3 ---"
mkdir -p "${BUILD_DIR}/reference/tools/haplogrep"
cp -r "${REF_DIR}/tools/haplogrep/"* "${BUILD_DIR}/reference/tools/haplogrep/"
echo "  ✓ Haplogrep3 复制完成"

# ===== G25 参考坐标 (~3MB) =====
echo ""
echo "--- 复制 G25 参考坐标 ---"
mkdir -p "${BUILD_DIR}/reference/population/g25"
cp "${REF_DIR}/population/g25/"*.txt "${BUILD_DIR}/reference/population/g25/"
echo "  ✓ G25 复制完成"


# ===== 执行 Docker 构建 =====
echo ""
echo "--- 开始 docker build ---"
echo "  Dockerfile: ${SCRIPT_DIR}/Dockerfile"
echo "  上下文: ${BUILD_DIR}"
echo ""

# 复制 Dockerfile 到构建上下文
cp "${SCRIPT_DIR}/Dockerfile" "${BUILD_DIR}/Dockerfile"
cp "${SCRIPT_DIR}/entrypoint.sh" "${BUILD_DIR}/entrypoint.sh"

cd "${BUILD_DIR}"
docker build \
    --build-arg http_proxy=http://192.168.0.214:7897 \
    --build-arg https_proxy=http://192.168.0.214:7897 \
    --network=host \
    -t "${IMAGE_NAME}:${VERSION}" \
    -t "${IMAGE_NAME}:latest" \
    -f Dockerfile \
    .

echo ""
echo "=== ✅ 构建完成 ==="
echo "镜像:"
docker images "${IMAGE_NAME}" --format "  {{.Repository}}:{{.Tag}}  {{.Size}}"
echo ""
echo "基础层:"
docker images wgs-align --format "  {{.Repository}}:{{.Tag}}  {{.Size}}"
echo ""
echo "导出镜像 (搬迁用):"
echo "  docker save ${IMAGE_NAME}:latest | gzip > ${IMAGE_NAME}.tar.gz"
echo ""
echo "快速自检:"
echo "  docker run --rm ${IMAGE_NAME}:latest help"
echo ""
echo "清理构建上下文 (可选):"
echo "  rm -rf ${BUILD_DIR}"
