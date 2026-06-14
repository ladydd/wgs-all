---
name: wgs-platform
description: WGS古DNA分析平台的完整知识库。包含Docker镜像使用、所有CLI命令、参数说明、开发构建流程。当用户询问wgs-all镜像、古DNA分析、比对、单倍群、EIGENSTRAT、芯片格式、祖源计算器等相关问题时使用。
---

# WGS-All 古DNA分析平台

## 概述

wgs-all 是一个自包含的 Docker 镜像（v1.3.0, 44.7 GB），覆盖古DNA全基因组测序分析的完整流程。目标机器只需要 Docker，docker load 后即可使用，无需联网、无需配置环境。

## 项目位置

- 代码: `/home/ladydd/wgs-platform/`
- 镜像 tar: `/home/ladydd/wgs-all.tar` (14 GB)
- 参考数据: `/home/ladydd/reference/` (33 GB, 构建镜像用)
- 测试样本: `/home/ladydd/data/JP244/` (4 GB, hg38 BAM)
- 开发环境: conda `ychr` (`/home/ladydd/miniconda3/envs/ychr/`)
- 网站: guren.xin (古基因数据分析平台)

## Docker 镜像使用

### 加载镜像
```bash
docker load < wgs-all.tar       # Linux/macOS
docker load -i wgs-all.tar      # Windows PowerShell
docker run --rm wgs-all help    # 验证
```

### 通用命令格式
```bash
docker run --rm -v /你的数据目录:/data wgs-all <命令> [参数]
```

### 文件权限
容器以 root 运行，输出文件默认属于 root。自动修复机制已内置（检测挂载目录属主）。手动指定：
```bash
docker run --rm -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) -v /data:/data wgs-all ...
```

## 所有命令

### align — FASTQ比对 (hg38)
```bash
docker run --rm -v /data:/data wgs-all align SAMPLE R1.fq.gz R2.fq.gz [threads]
```
- 输出: `/data/output/SAMPLE/SAMPLE.sorted.bam`
- 参考: hg38 (GRCh38, chr前缀)

### align-hg19 — FASTQ比对 (hg19)
```bash
docker run --rm -v /data:/data wgs-all align-hg19 SAMPLE R1.fq.gz R2.fq.gz [threads]
```
- 输出: `/data/output/SAMPLE/SAMPLE.sorted.bam`
- 参考: hs37d5 (GRCh37, 无chr前缀)

### align-t2t — FASTQ比对 (T2T)
```bash
docker run --rm -v /data:/data wgs-all align-t2t SAMPLE R1.fq.gz R2.fq.gz [threads]
```
- 输出: `/data/output/SAMPLE/SAMPLE.sorted.bam`
- 参考: CHM13v2 (T2T, chr前缀)

### detect-bam — 识别BAM参考版本
```bash
docker run --rm -v /data:/data wgs-all detect-bam /data/x.bam
```
- 自动识别: hg38 (chr1=248956422), hg19 (chr1=249250621), T2T (chr1=248387328)
- 输出参考版本和染色体命名风格

### extract-chr — 提取染色体
```bash
docker run --rm -v /data:/data wgs-all extract-chr /data/x.bam chrY -o /data -s SAMPLE
docker run --rm -v /data:/data wgs-all extract-chr /data/x.bam chrM -o /data -s SAMPLE
```
- 自动适配染色体命名: chrY↔Y, chrM↔MT
- 自动检测BAM参考版本
- 输出: BAM + VCF + 覆盖度统计

### analyze-y — Y单倍群 (Yleaf v4)
```bash
docker run --rm -v /data:/data wgs-all analyze-y /data/x.chrY.bam -o /data/yleaf --tree isogg
```
参数:
- `--tree`: isogg (默认), yfull, yfull_v10, ftdna
- `--reference`: hg38 (默认), hg19, t2t (通常自动检测)
- `--no-adna`: 关闭古DNA模式
- 离线运行，不联网
- 女性样本自动检测（全基因组BAM时chrY reads占比<0.1%会warning）

### analyze-mt — MT单倍群 (Haplogrep3)
```bash
docker run --rm -v /data:/data wgs-all analyze-mt /data/x.chrM.vcf.gz -o /data/mt.txt
```
- 使用 phylotree-fu-rcrs@1.2
- 输出: 单倍群 + 质量分数 + 变异位点

### bam-to-eigenstrat — BAM转EIGENSTRAT
```bash
docker run --rm -v /data:/data wgs-all bam-to-eigenstrat \
    --bam /data/x.bam \
    -p Population \
    -o /data/output \
    -n dataset_name \
    --deliver-hg19
```
参数:
- `--bam`: 单个BAM文件
- `--bam-list`: BAM列表文件（批量）
- `-p/--population`: 群体标签
- `-o/--output-dir`: 输出目录
- `-n/--name`: 数据集名称
- `--position-set`: v42.4.1240K (默认, 1.23M位点) 或 v66.2M.aadr (2.14M位点)
- `--deliver-hg19`: 额外输出hg19坐标版本（交付用）
- `--seed`: 随机种子（randomHaploid的随机数）
- 支持 hg38/hg19/T2T BAM（T2T自动走hg38位点表）
- 输出: .geno + .snp + .ind 三件套

### extract-chip — 芯片格式导出
```bash
docker run --rm -v /data:/data wgs-all extract-chip /data/x.bam -o /data/chip -s SAMPLE
```
- 自动检测BAM参考版本
- hg38 BAM: mpileup → liftover → 匹配模板
- hg19 BAM: mpileup → 直接匹配模板（跳过liftover）
- 输出 11 种格式: 23andMe V3/V5/V35, Ancestry V1/V2, FTDNA V2/V3, LDNA V1/V2, MyHeritage V1/V2

### admixture-calc — 祖源计算器
```bash
docker run --rm -v /data:/data wgs-all admixture-calc /data/chip/x_23andMe_V5.txt -c E11,K36
docker run --rm -v /data:/data wgs-all admixture-calc /data/chip/x_23andMe_V5.txt  # 跑全部
```
- 输入: 任意芯片格式文件
- 28个计算器: E11, K12b, K13, K36, K47, globe13, HarappaWorld 等
- `-c`: 指定计算器（逗号分隔），不指定则跑全部

### g25 — G25距离计算
```bash
docker run --rm wgs-all g25 --coords "0.02,-0.015,0.008,..." --top 20
docker run --rm -v /data:/data wgs-all g25 --file /data/my_coords.csv --top 20
```
- 参考: 10927个现代人群 + 1003个古代样本
- 输出: 最近的现代/古代人群排名（欧氏距离）
- 注意: G25坐标需要从外部获取（exploreyourdna.com 2.5€ 或 Davidski）

### report — HTML报告
```bash
docker run --rm -v /data:/data wgs-all report -s SAMPLE -o /data/report.html \
    --y-hg "N1a2a" --y-qc 1.0 \
    --mt-hg "A11" --mt-quality 0.882 \
    --eigen-snps 1231730 --chip-n 11
```

### full-pipeline — 一键全流程
```bash
docker run --rm -v /data:/data wgs-all full-pipeline --bam /data/x.bam -o /data/results
```
- 串联: extract-chr → analyze-y → analyze-mt → extract-chip → admixture-calc → eigenstrat
- ⚠️ 未经全量端到端测试

### shell — 交互式终端
```bash
docker run --rm -it -v /data:/data wgs-all shell
```

## 内置工具版本

| 工具 | 版本 | 用途 |
|---|---|---|
| BWA | 0.7.19 | 序列比对 |
| samtools | 1.16.1 | BAM处理 |
| bcftools | 1.16 | 变异检测/VCF处理 |
| pileupCaller | 1.6.0 | 古DNA基因型抽取 (randomHaploid) |
| Yleaf | v4.0.2 | Y染色体单倍群 |
| Haplogrep3 | 3.2.2 | 线粒体单倍群 |
| PLINK | 1.9 | 基因组格式转换 |
| ADMIXTURE | 1.3 | 祖源成分估算 |
| smartpca | v16000 | PCA主成分分析 |
| ADMIXTOOLS (qpAdm) | v810 | 祖源建模/f-statistics |
| admix | 28 models | 祖源计算器 |

## 系统要求

- Docker 20+
- 磁盘: 50 GB（镜像）+ 数据空间
- 内存: 4 GB（分析）/ 16 GB（比对）
- CPU: 越多越快，比对时自动用全部核心
- Windows: 需要 Docker Desktop (WSL2)

## 开发与构建

### 本地开发
```bash
conda activate ychr
cd /home/ladydd/wgs-platform
python -m app.cli --help
```

### 构建镜像
```bash
cd /home/ladydd/wgs-platform
bash docker/eigenstrat/build_bg.sh start    # 后台构建 (~25分钟)
bash docker/eigenstrat/build_bg.sh status   # 查看进度
bash docker/eigenstrat/build_bg.sh log      # 跟随日志
bash docker/eigenstrat/build_bg.sh stop     # 终止
```
构建需要网络（pip install yleaf 从 GitHub）。代理: `192.168.0.214:7897`

### 导出镜像
```bash
docker save wgs-all:latest -o /home/ladydd/wgs-all.tar
```

### 关键文件
| 文件 | 用途 |
|---|---|
| docker/eigenstrat/Dockerfile | 镜像定义 |
| docker/eigenstrat/build.sh | 构建脚本 |
| docker/eigenstrat/entrypoint.sh | 容器入口 |
| app/cli.py | CLI命令定义 |
| app/pipeline/ | 核心分析逻辑 |
| app/core/bam_detector.py | BAM参考版本检测 |
| app/pipeline/haplogroup.py | Y/MT单倍群分析 |
| app/pipeline/eigenstrat.py | EIGENSTRAT导出 |
| app/pipeline/extraction.py | 芯片格式导出 |
| app/pipeline/calculator.py | 祖源计算器 |
| app/pipeline/g25.py | G25距离计算 |
| app/pipeline/report.py | HTML报告 |

## 参考数据（镜像内）

| 数据 | 路径 | 大小 |
|---|---|---|
| hg38 + BWA索引 | /reference/hg38/genome/ | ~16 GB |
| hg19 + BWA索引 | /reference/hg19/genome/ | ~8.3 GB |
| T2T + BWA索引 | /reference/t2t/genome/ | ~8.1 GB |
| AADR 1240K hg38位点 | /reference/population/eigenstrat/ | ~50 MB |
| AADR hg19 .snp | /reference/aadr_positions/ | ~80 MB |
| 芯片模板+SNP注释 | /reference/microarray/ | ~406 MB |
| LiftOver chain | /reference/liftover/ | ~1.5 MB |
| Haplogrep3+phylotree | /reference/tools/haplogrep/ | ~55 MB |
| G25参考坐标 | /reference/population/g25/ | ~3 MB |
| Yleaf v4 (pip) | site-packages | ~102 MB |
| admix计算器 (pip) | site-packages | ~509 MB |

## 待办事项

1. 样本质量报告（覆盖度、内源DNA、损伤模式）
2. 污染评估（MT/X染色体）
3. full-pipeline 自动出报告
4. ROH 近亲婚配检测
5. 性别判定（X/Y覆盖度比值）
6. kinship 亲缘关系
7. G25坐标逆向（训练映射模型）
