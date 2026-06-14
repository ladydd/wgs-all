# WGS-All | 古DNA全基因组分析平台

[English](README_EN.md) | 🇨🇳 中文

---

一个自包含的 Docker 镜像，用于古DNA全基因组测序数据分析。从 FASTQ 到祖源报告，无需联网、无需配置环境，`docker load` 即用。

## 功能

- **比对**: FASTQ → BAM（hg38 / hg19 / T2T 三套参考基因组）
- **Y 单倍群**: Yleaf v4（ISOGG / YFull / FTDNA 树，古DNA模式）
- **MT 单倍群**: Haplogrep3（PhyloTree 17）
- **EIGENSTRAT 导出**: BAM → 古DNA标准交付格式（1240K / 2M AADR）
- **芯片格式**: 11 种（23andMe / AncestryDNA / FTDNA / MyHeritage / LivingDNA）
- **祖源计算器**: 28 个（E11, K13, K36, K47, HarappaWorld 等）
- **G25 距离计算**: 与 10,927 个现代 + 1,003 个古代人群比较
- **群体工具**: smartpca (PCA) / qpAdm (ADMIXTOOLS) / PLINK / ADMIXTURE
- **HTML 报告**: 一页纸总结所有结果

## 快速开始

```bash
# 加载镜像
docker load < wgs-all.tar

# 比对（hg38 / hg19 / T2T）
docker run --rm -v /data:/data wgs-all align SAMPLE R1.fq.gz R2.fq.gz
docker run --rm -v /data:/data wgs-all align-hg19 SAMPLE R1.fq.gz R2.fq.gz
docker run --rm -v /data:/data wgs-all align-t2t SAMPLE R1.fq.gz R2.fq.gz

# Y 单倍群
docker run --rm -v /data:/data wgs-all extract-chr /data/x.bam chrY -o /data -s SAMPLE
docker run --rm -v /data:/data wgs-all analyze-y /data/SAMPLE.chrY.bam -o /data/yleaf

# EIGENSTRAT 导出
docker run --rm -v /data:/data wgs-all bam-to-eigenstrat \
    --bam /data/x.bam -p Pop -o /data/out -n dataset --deliver-hg19

# 芯片格式 + 祖源计算器
docker run --rm -v /data:/data wgs-all extract-chip /data/x.bam -o /data/chip -s SAMPLE
docker run --rm -v /data:/data wgs-all admixture-calc /data/chip/SAMPLE_23andMe_V5.txt -c E11,K36

# G25 距离
docker run --rm wgs-all g25 --coords "0.02,-0.015,..." --top 20

# 查看所有命令
docker run --rm wgs-all help
```

## 系统要求

- Docker 20+
- 磁盘: 50 GB（镜像）+ 数据空间
- 内存: 4 GB（分析）/ 16 GB（比对）
- 系统: Linux / macOS / Windows (Docker Desktop)

## 文档

- [用户手册](docs/user-manual.md)
- [致谢与引用](docs/credits.md)
- [项目进度](docs/project_review.md)

## 许可

MIT（平台代码）。各工具的许可证详见 [credits.md](docs/credits.md)。

## 联系

hello@ladydd.com | [guren.xin](https://guren.xin)
