# WGS-All 用户手册

> 版本: v1.3.0 | 更新: 2026-06-14

## 简介

WGS-All 是一个自包含的 Docker 镜像，用于古DNA全基因组测序数据分析。一个文件搬到目标机器，`docker load` 即可使用，无需联网、无需安装任何依赖。

**支持的分析：**
- FASTQ → BAM 比对（hg38 / hg19 / T2T 三套参考基因组）
- Y 染色体单倍群判定（Yleaf v4）
- 线粒体单倍群判定（Haplogrep3）
- EIGENSTRAT 数据集导出（古DNA标准交付格式）
- 芯片格式导出（11种，可上传 GEDmatch/Vahaduo 等平台）
- 祖源计算器（28个，含 E11/K13/K36 等）
- G25 遗传距离计算
- HTML 报告生成

---

## 安装

### 系统要求
| 项目 | 最低 | 推荐 |
|---|---|---|
| Docker | 20+ | 最新版 |
| 磁盘 | 50 GB | 100 GB+ |
| 内存 | 4 GB（分析） | 16 GB（比对） |
| 系统 | Linux / macOS / Windows (Docker Desktop) | Linux |

### 加载镜像
```bash
# Linux / macOS
docker load < wgs-all.tar

# Windows PowerShell
docker load -i wgs-all.tar

# 验证安装
docker run --rm wgs-all help
```

---

## 基本用法

所有命令格式统一：
```bash
docker run --rm -v /你的数据目录:/data wgs-all <命令> [参数]
```

`-v /你的数据目录:/data` 将本地目录挂载到容器内的 `/data`，输入输出都在这里。

---

## 命令详解

### 1. 比对 (FASTQ → BAM)

将原始测序数据比对到参考基因组。

```bash
# hg38 (GRCh38) — 最常用
docker run --rm -v /data:/data wgs-all align SAMPLE R1.fq.gz R2.fq.gz

# hg19 (hs37d5/GRCh37)
docker run --rm -v /data:/data wgs-all align-hg19 SAMPLE R1.fq.gz R2.fq.gz

# T2T (CHM13v2)
docker run --rm -v /data:/data wgs-all align-t2t SAMPLE R1.fq.gz R2.fq.gz
```

**参数：**
- `SAMPLE` — 样本名称（输出文件以此命名）
- `R1.fq.gz` — 正向 reads（相对于 /data 的路径）
- `R2.fq.gz` — 反向 reads
- 可选第四个参数：线程数（默认自动）

**输出：**
```
/data/output/SAMPLE/
├── SAMPLE.sorted.bam       # 比对结果
├── SAMPLE.sorted.bam.bai   # 索引
└── SAMPLE.flagstat.txt     # 统计信息
```

**三套参考的区别：**
| 参考 | 染色体命名 | 适用场景 |
|---|---|---|
| hg38 | chr1, chrX, chrY, chrM | 大多数现代分析 |
| hg19 | 1, X, Y, MT | 兼容旧数据/旧工具 |
| T2T | chr1, chrX, chrY, chrM | 最完整参考，含着丝粒 |

---

### 2. BAM 参考版本识别

```bash
docker run --rm -v /data:/data wgs-all detect-bam /data/SAMPLE.sorted.bam
```

自动识别 BAM 文件是对齐到哪个参考基因组的。后续命令（extract-chr、extract-chip 等）都会自动调用此功能，通常不需要手动运行。

---

### 3. 提取染色体

从全基因组 BAM 中提取特定染色体。

```bash
# 提取 Y 染色体
docker run --rm -v /data:/data wgs-all extract-chr /data/SAMPLE.bam chrY -o /data -s SAMPLE

# 提取线粒体
docker run --rm -v /data:/data wgs-all extract-chr /data/SAMPLE.bam chrM -o /data -s SAMPLE
```

**自动适配：** 无论 BAM 里染色体叫 `chrY` 还是 `Y`（取决于参考版本），传 `chrY` 即可，系统自动处理。

**输出：**
```
/data/SAMPLE.chrY.bam       # Y 染色体 BAM
/data/SAMPLE.chrY.bam.bai   # 索引
/data/SAMPLE.chrY.vcf.gz    # VCF（变异）
```

---

### 4. Y 单倍群分析

```bash
docker run --rm -v /data:/data wgs-all analyze-y /data/SAMPLE.chrY.bam -o /data/yleaf --tree isogg
```

**参数：**
| 参数 | 说明 | 默认 |
|---|---|---|
| `--tree` | 系统树：isogg / yfull / yfull_v10 / ftdna | isogg |
| `--reference` | 参考版本：hg38 / hg19 / t2t | 自动检测 |
| `--no-adna` | 关闭古DNA模式 | 默认开启 |

**输出示例：**
```
Y 单倍群: N1a2a*(xN1a2a1a)
QC-score: 1.0
使用标记: 5503
```

**注意：**
- 需要先用 `extract-chr` 提取 chrY BAM
- 覆盖度建议 ≥1x 才有可靠结果
- 女性样本会自动警告（全基因组 BAM 时）

---

### 5. MT 单倍群分析

```bash
docker run --rm -v /data:/data wgs-all analyze-mt /data/SAMPLE.chrM.vcf.gz -o /data/mt.txt
```

**输入：** chrM 的 VCF 文件（由 `extract-chr` 产生）

**输出示例：**
```
MT 单倍群: A11+16234
质量分数: 0.882
变异位点: 15
```

---

### 6. EIGENSTRAT 数据集导出

古DNA 领域标准交付格式，用于 PCA、qpAdm 等群体遗传分析。

```bash
# 单个样本
docker run --rm -v /data:/data wgs-all bam-to-eigenstrat \
    --bam /data/SAMPLE.bam \
    -p MyPopulation \
    -o /data/eigenstrat \
    -n dataset_name \
    --deliver-hg19

# 批量（多个样本合并为一个数据集）
docker run --rm -v /data:/data wgs-all bam-to-eigenstrat \
    --bam-list /data/bam_list.txt \
    -p MyPopulation \
    -o /data/eigenstrat \
    -n batch_dataset \
    --deliver-hg19
```

**参数：**
| 参数 | 说明 | 默认 |
|---|---|---|
| `--bam` | 单个 BAM 文件 | — |
| `--bam-list` | BAM 列表文件（每行一个路径） | — |
| `-p` | 群体标签 | 必填 |
| `-o` | 输出目录 | 必填 |
| `-n` | 数据集名称 | 必填 |
| `--position-set` | 位点集 | v42.4.1240K (1.23M位点) |
| `--deliver-hg19` | 额外输出 hg19 坐标版本 | 不输出 |
| `--seed` | 随机种子 | 42 |

**输出：**
```
/data/eigenstrat/
├── dataset_name.geno      # 基因型矩阵
├── dataset_name.snp       # SNP 信息（hg38 坐标）
├── dataset_name.ind       # 样本信息
├── dataset_name.hg19.geno # hg19 坐标版本（--deliver-hg19 时）
├── dataset_name.hg19.snp
└── dataset_name.hg19.ind
```

---

### 7. 芯片格式导出

从 BAM 提取基因型，输出 11 种商用芯片格式文件。

```bash
docker run --rm -v /data:/data wgs-all extract-chip /data/SAMPLE.bam -o /data/chip -s SAMPLE
```

**自动行为：**
- 自动检测 BAM 参考版本
- hg38 BAM → mpileup → LiftOver hg38→hg19 → 匹配芯片模板
- hg19 BAM → mpileup → 直接匹配（跳过 LiftOver）
- T2T BAM → 走 hg38 流程

**输出格式：**
| 格式 | 文件名 |
|---|---|
| 23andMe V3 | SAMPLE_23andMe_V3.txt |
| 23andMe V5 | SAMPLE_23andMe_V5.txt |
| 23andMe V35 (合并) | SAMPLE_23andMe_V35.txt |
| AncestryDNA V1 | SAMPLE_Ancestry_V1.txt |
| AncestryDNA V2 | SAMPLE_Ancestry_V2.txt |
| FTDNA V2 | SAMPLE_FTDNA_V2.csv |
| FTDNA V3 | SAMPLE_FTDNA_V3.csv |
| LivingDNA V1 | SAMPLE_LDNA_V1.txt |
| LivingDNA V2 | SAMPLE_LDNA_V2.txt |
| MyHeritage V1 | SAMPLE_MyHeritage_V1.csv |
| MyHeritage V2 | SAMPLE_MyHeritage_V2.csv |

**用途：** 上传到 GEDmatch、Vahaduo、exploreyourdna.com 等平台做祖源分析。

---

### 8. 祖源计算器

从芯片格式文件计算祖源成分比例。

```bash
# 指定计算器
docker run --rm -v /data:/data wgs-all admixture-calc /data/chip/SAMPLE_23andMe_V5.txt -c E11,K36

# 跑全部 28 个
docker run --rm -v /data:/data wgs-all admixture-calc /data/chip/SAMPLE_23andMe_V5.txt
```

**可用计算器（28个）：** E11, K12b, K13, K15, K36, K47, globe13, globe10, world9, Jtest, HarappaWorld, EthioHelix, MDLP_World, puntDNAL, Dodecad_World9 等。

**输出示例 (E11)：**
```
E11:
  East Chinese: 34.56%
  Southwest Chinese Yi: 30.75%
  South Chinese Dai: 12.01%
  Malay: 11.37%
  North Chinese Oroqen: 5.94%
  India: 3.00%
  Yakut: 1.36%
  ...
```

---

### 9. G25 距离计算

给定 G25 坐标（25个数字），找到遗传距离最近的人群。

```bash
# 直接输入坐标
docker run --rm wgs-all g25 --coords "0.02,-0.015,0.008,-0.01,..." --top 20

# 从文件读取
docker run --rm -v /data:/data wgs-all g25 --file /data/my_coords.csv --top 20
```

**参考数据：** 10,927 个现代人群 + 1,003 个古代样本

**G25 坐标获取方式：**
1. 用 `extract-chip` 导出 23andMe 格式文件
2. 上传到 [exploreyourdna.com](https://www.exploreyourdna.com/rawtosimg25.aspx) (2.50€) 获取坐标
3. 用本命令计算距离

---

### 10. HTML 报告

生成一份总结报告。

```bash
docker run --rm -v /data:/data wgs-all report -s SAMPLE -o /data/report.html \
    --y-hg "N1a2a*(xN1a2a1a)" --y-qc 1.0 \
    --mt-hg "A11+16234" --mt-quality 0.882 \
    --eigen-snps 1231730 --chip-n 11
```

---

### 11. 一键全流程

串联所有分析步骤。

```bash
docker run --rm -v /data:/data wgs-all full-pipeline --bam /data/SAMPLE.bam -o /data/results
```

自动执行：提取 chrY/chrM → Y/MT 单倍群 → EIGENSTRAT → 芯片格式 → 祖源计算器

---

## 典型工作流

### 流程 A：从 FASTQ 开始（最完整）
```bash
DATA=/path/to/data

# 1. 比对
docker run --rm -v $DATA:/data wgs-all align MySample R1.fq.gz R2.fq.gz

# 2. 提取 chrY + chrM
docker run --rm -v $DATA:/data wgs-all extract-chr /data/output/MySample/MySample.sorted.bam chrY -o /data -s MySample
docker run --rm -v $DATA:/data wgs-all extract-chr /data/output/MySample/MySample.sorted.bam chrM -o /data -s MySample

# 3. 单倍群
docker run --rm -v $DATA:/data wgs-all analyze-y /data/MySample.chrY.bam -o /data/yleaf --tree isogg
docker run --rm -v $DATA:/data wgs-all analyze-mt /data/MySample.chrM.vcf.gz -o /data/mt.txt

# 4. EIGENSTRAT
docker run --rm -v $DATA:/data wgs-all bam-to-eigenstrat \
    --bam /data/output/MySample/MySample.sorted.bam -p Han -o /data -n MySample --deliver-hg19

# 5. 芯片格式 + 祖源
docker run --rm -v $DATA:/data wgs-all extract-chip /data/output/MySample/MySample.sorted.bam -o /data/chip -s MySample
docker run --rm -v $DATA:/data wgs-all admixture-calc /data/chip/MySample_23andMe_V5.txt -c E11,K36
```

### 流程 B：已有 BAM 文件
跳过第 1 步，从第 2 步开始。系统自动检测 BAM 参考版本。

---

## FAQ

**Q: 支持 Windows 吗？**
A: 支持。安装 Docker Desktop (WSL2 后端) 后命令完全一样，路径用 `D:\data:/data`。

**Q: 需要联网吗？**
A: 不需要。所有参考数据和工具都内置在镜像里。

**Q: 占多少内存？**
A: 磁盘 45 GB（镜像本身），运行时内存取决于命令：分析命令 1-4 GB，比对命令 8-16 GB。

**Q: 可以同时跑多个样本吗？**
A: 可以。开多个 `docker run` 即可，每个容器独立。注意内存和磁盘 IO。

**Q: 输出文件权限是 root 怎么办？**
A: 系统会自动修复挂载目录的文件权限。如果还有问题，加 `-e HOST_UID=$(id -u) -e HOST_GID=$(id -g)`。

**Q: 如何查看所有可用命令？**
A: `docker run --rm wgs-all help`
