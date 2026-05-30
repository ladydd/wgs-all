#!/bin/bash
# 将现有 reference 目录按新结构重新组织
# 用法: bash scripts/reorganize_reference.sh /home/ladydd/reference
#
# 注意: 此脚本使用符号链接，不移动原始文件，安全可逆

set -e

REF_DIR=${1:-"/home/ladydd/reference"}

echo "=== 重组 Reference 目录结构 ==="
echo "目标: ${REF_DIR}"
echo ""

# ===== hg38 =====
echo "--- hg38 ---"
mkdir -p "${REF_DIR}/hg38/genome"
mkdir -p "${REF_DIR}/hg38/snp"
mkdir -p "${REF_DIR}/hg38/y_chromosome"
mkdir -p "${REF_DIR}/hg38/mt"
mkdir -p "${REF_DIR}/hg38/1240k"

# genome
for ext in "" ".fai" ".bwt" ".amb" ".ann" ".pac" ".sa" ".dict"; do
    src="${REF_DIR}/genomes/hs38.fa${ext}"
    dst="${REF_DIR}/hg38/genome/hs38.fa${ext}"
    if [ -f "$src" ] && [ ! -e "$dst" ]; then
        ln -s "$src" "$dst"
        echo "  链接: hs38.fa${ext}"
    fi
done

# snp
for f in All_SNPs_hg38_ref.tab.gz All_SNPs_hg38_ref.tab.gz.tbi; do
    src="${REF_DIR}/microarray/${f}"
    dst="${REF_DIR}/hg38/snp/${f}"
    if [ -f "$src" ] && [ ! -e "$dst" ]; then
        ln -s "$src" "$dst"
        echo "  链接: ${f}"
    fi
done

for f in snps_hg38.vcf.gz snps_hg38.vcf.gz.tbi snps_hg38.vcf.gz.gzi; do
    src="${REF_DIR}/${f}"
    dst="${REF_DIR}/hg38/snp/${f}"
    if [ -f "$src" ] && [ ! -e "$dst" ]; then
        ln -s "$src" "$dst"
        echo "  链接: ${f}"
    fi
done

# y_chromosome
src="${REF_DIR}/yleaf/Position_files/WGS_hg38.txt"
dst="${REF_DIR}/hg38/y_chromosome/WGS_hg38.txt"
if [ -f "$src" ] && [ ! -e "$dst" ]; then
    ln -s "$src" "$dst"
    echo "  链接: WGS_hg38.txt"
fi

for f in BigY3_hg38.bed BigY3_hg38num.bed; do
    src="${REF_DIR}/${f}"
    dst="${REF_DIR}/hg38/y_chromosome/${f}"
    if [ -f "$src" ] && [ ! -e "$dst" ]; then
        ln -s "$src" "$dst"
        echo "  链接: ${f}"
    fi
done

# 1240k
src="${REF_DIR}/1240K_hg38.tab.gz"
dst="${REF_DIR}/hg38/1240k/1240K_hg38.tab.gz"
if [ -f "$src" ] && [ ! -e "$dst" ]; then
    ln -s "$src" "$dst"
    echo "  链接: 1240K_hg38.tab.gz"
fi

# ===== hg19 =====
echo ""
echo "--- hg19 ---"
mkdir -p "${REF_DIR}/hg19/genome"
mkdir -p "${REF_DIR}/hg19/snp"
mkdir -p "${REF_DIR}/hg19/y_chromosome"
mkdir -p "${REF_DIR}/hg19/mt"
mkdir -p "${REF_DIR}/hg19/1240k"

# genome
for ext in "" ".fai"; do
    src="${REF_DIR}/genomes/hs37d5.fa${ext}"
    dst="${REF_DIR}/hg19/genome/hs37d5.fa${ext}"
    if [ -f "$src" ] && [ ! -e "$dst" ]; then
        ln -s "$src" "$dst"
        echo "  链接: hs37d5.fa${ext}"
    fi
done

# snp
for f in All_SNPs_hg19_ref.tab.gz All_SNPs_hg19_ref.tab.gz.tbi; do
    src="${REF_DIR}/microarray/${f}"
    dst="${REF_DIR}/hg19/snp/${f}"
    if [ -f "$src" ] && [ ! -e "$dst" ]; then
        ln -s "$src" "$dst"
        echo "  链接: ${f}"
    fi
done

for f in snps_hg19.vcf.gz snps_hg19.vcf.gz.tbi snps_hg19.vcf.gz.gzi; do
    src="${REF_DIR}/${f}"
    dst="${REF_DIR}/hg19/snp/${f}"
    if [ -f "$src" ] && [ ! -e "$dst" ]; then
        ln -s "$src" "$dst"
        echo "  链接: ${f}"
    fi
done

# y_chromosome
src="${REF_DIR}/yleaf/Position_files/WGS_hg19.txt"
dst="${REF_DIR}/hg19/y_chromosome/WGS_hg19.txt"
if [ -f "$src" ] && [ ! -e "$dst" ]; then
    ln -s "$src" "$dst"
    echo "  链接: WGS_hg19.txt"
fi

for f in BigY3_hg37.bed BigY3_hg37num.bed; do
    src="${REF_DIR}/${f}"
    dst="${REF_DIR}/hg19/y_chromosome/${f}"
    if [ -f "$src" ] && [ ! -e "$dst" ]; then
        ln -s "$src" "$dst"
        echo "  链接: ${f}"
    fi
done

# ===== t2t =====
echo ""
echo "--- t2t ---"
mkdir -p "${REF_DIR}/t2t/genome"
mkdir -p "${REF_DIR}/t2t/snp"
mkdir -p "${REF_DIR}/t2t/y_chromosome"
mkdir -p "${REF_DIR}/t2t/mt"
mkdir -p "${REF_DIR}/t2t/1240k"
echo "  (目录已创建，文件待下载)"

# ===== liftover =====
echo ""
echo "--- liftover ---"
mkdir -p "${REF_DIR}/liftover"

for f in hg38ToHg19.over.chain.gz grch38-chm13v2.chain hg19-chm13v2.chain chm13v2-hg19.chain chm13v2-grch38.chain; do
    src="${REF_DIR}/${f}"
    dst="${REF_DIR}/liftover/${f}"
    if [ -f "$src" ] && [ ! -e "$dst" ]; then
        ln -s "$src" "$dst"
        echo "  链接: ${f}"
    fi
done

# ===== tools =====
echo ""
echo "--- tools ---"
mkdir -p "${REF_DIR}/tools"

src="${REF_DIR}/yleaf"
dst="${REF_DIR}/tools/yleaf"
if [ -d "$src" ] && [ ! -e "$dst" ]; then
    ln -s "$src" "$dst"
    echo "  链接: yleaf/"
fi

mkdir -p "${REF_DIR}/tools/haplogrep"
mkdir -p "${REF_DIR}/tools/plink"
echo "  (haplogrep, plink 待安装)"

# ===== population =====
echo ""
echo "--- population ---"
mkdir -p "${REF_DIR}/population/g25"
mkdir -p "${REF_DIR}/population/1000genomes"
mkdir -p "${REF_DIR}/population/aadr"
echo "  (群体参考数据待准备)"

echo ""
echo "=== 完成 ==="
echo ""
echo "验证:"
echo "  ls -la ${REF_DIR}/hg38/genome/"
echo "  ls -la ${REF_DIR}/hg19/genome/"
echo "  ls -la ${REF_DIR}/t2t/genome/"
