# WGS Analysis Platform

全基因组测序 (WGS) 数据分析平台，面向古 DNA 研究。

## 功能

- **比对**: FASTQ → BAM (hg38 / hg19 / T2T)
- **EIGENSTRAT 导出**: BAM → 古 DNA 标准交付格式 (1240K / 2M AADR)
- **Y 单倍群**: Yleaf v4 (isogg/yfull/ftdna 树，支持 hg38/hg19/t2t)
- **MT 单倍群**: Haplogrep3
- **芯片格式**: 11 种格式 (23andMe/Ancestry/FTDNA/MyHeritage/LDNA)
- **祖源计算器**: 28 个 (E11/K13/K36/K47/HarappaWorld 等)
- **G25 距离计算**: 与 10927 现代 + 1003 古代人群比较
- **群体分析工具**: PCA (smartpca) / qpAdm (ADMIXTOOLS) / PLINK
- **HTML 报告**: 一页纸总结所有分析结果

## 使用

通过 Docker 镜像使用，无需配置环境，不联网：

```bash
# 加载镜像
docker load < wgs-all.tar.gz

# 比对 (三套参考)
docker run --rm -v /data:/data wgs-all align SAMPLE R1.fq.gz R2.fq.gz
docker run --rm -v /data:/data wgs-all align-hg19 SAMPLE R1.fq.gz R2.fq.gz
docker run --rm -v /data:/data wgs-all align-t2t SAMPLE R1.fq.gz R2.fq.gz

# Y 单倍群
docker run --rm -v /data:/data wgs-all analyze-y /data/x.chrY.bam -o /data/yleaf

# MT 单倍群
docker run --rm -v /data:/data wgs-all analyze-mt /data/x.chrM.vcf.gz -o /data/mt.txt

# EIGENSTRAT 导出
docker run --rm -v /data:/data wgs-all bam-to-eigenstrat \
    --bam /data/x.bam -p Pop -o /data/out -n dataset --deliver-hg19

# 芯片格式
docker run --rm -v /data:/data wgs-all extract-chip /data/x.bam -o /data/chip -s SAMPLE

# 祖源计算器
docker run --rm -v /data:/data wgs-all admixture-calc /data/chip/x_23andMe_V5.txt -c E11,K36

# G25 距离
docker run --rm wgs-all g25 --coords "0.02,-0.015,..." --top 20

# 查看所有命令
docker run --rm wgs-all help
```

详细文档见 `docs/wgs_all_docker_guide.md`。

## 开发

```bash
# 本地开发环境
conda activate ychr
cd wgs-platform
python -m app.cli --help

# 构建镜像
bash docker/eigenstrat/build_bg.sh start

# 导出镜像
bash docker/eigenstrat/export_bg.sh start
```

## 文档

- [镜像使用指南](docs/wgs_all_docker_guide.md)
- [项目进度](docs/project_review.md)

## License

MIT
