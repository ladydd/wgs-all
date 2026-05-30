# wgs-all 全能镜像使用指南

> 一个镜像搞定：hg38/hg19 比对、EIGENSTRAT 数据集导出、Y/MT 单倍群分析、芯片格式导出。
> 单镜像含全部参考数据和工具，目标机器无需配环境。

---

## 镜像内容

| 组件 | 版本 / 说明 |
|---|---|
| 基础系统 | Debian bookworm-slim |
| bwa | 0.7.19 |
| samtools | 1.21 |
| bcftools | 1.21 |
| pileupCaller | 1.6.0 (sequencetools) |
| PLINK | 1.9 |
| ADMIXTURE | 1.3 |
| smartpca | EIGENSOFT 16000 |
| ADMIXTOOLS | 5.1 (qpAdm, qpDstat, convertf, mergeit) |
| yleaf | Y 单倍群分析 (ISOGG 树) |
| Haplogrep3 | 3.2.2 (MT 单倍群, phylotree-fu-rcrs@1.2) |
| admix | 28 个祖源计算器 (E11/K13/K36/K47/HarappaWorld 等) |
| Java | OpenJDK 17 (Haplogrep3 依赖) |
| Python | 3.11 + pandas, numpy, scipy, pyliftover, pydantic, fastapi |
| hg38 参考基因组 | hs38.fa + 完整 BWA 索引 (7.5 GB) |
| hg19 参考基因组 | hs37d5.fa + 完整 BWA 索引 (8.3 GB)，无 chr 前缀 |
| 1240K 位点 (hg38) | 1,231,730 位点 |
| 1240K 位点 (hg19 AADR 原版) | 1,233,013 位点 |
| 2M AADR 位点 (hg38) | 2,140,129 位点 |
| 2M AADR 位点 (hg19 AADR 原版) | 2,142,271 位点 |
| Y-SNP 位点表 | WGS_hg38.txt / WGS_hg19.txt (~13 万位点) |
| 芯片模板 | 11 种格式 (23andMe/Ancestry/FTDNA/MyHeritage/LDNA) |
| liftOver chains | hg38↔hg19 |

**镜像大小**: ~20 GB（导出 tar.gz 约 7-8 GB）

---

## 加载镜像（目标机器）

```bash
# 1. 拷贝 tar.gz 到目标机器
scp wgs-all.tar.gz user@target:/path/

# 2. 在目标机器加载
docker load < wgs-all.tar.gz
# 或
gunzip -c wgs-all.tar.gz | docker load

# 3. 验证
docker images | grep wgs-all
docker run --rm wgs-all:latest help
```

---

## 快速开始：FASTQ 比对

### 比对到 hg38（默认，chr 前缀风格）

```bash
docker run --rm \
    -v /path/to/data:/data \
    wgs-all:latest \
    align SAMPLE_ID /data/R1.fastq.gz /data/R2.fastq.gz
```

输出 `/data/output/SAMPLE_ID/SAMPLE_ID.sorted.bam`，染色体命名 `chr1/chr2/.../chrX/chrY/chrM`。

### 比对到 hg19 / hs37d5（无 chr 前缀风格）

```bash
docker run --rm \
    -v /path/to/data:/data \
    wgs-all:latest \
    align-hg19 SAMPLE_ID /data/R1.fastq.gz /data/R2.fastq.gz
```

输出同上路径，染色体命名 `1/2/.../X/Y/MT`。

**别名**: `align-hg19` = `align-hs37d5` = `align-grch37`（三个名字等价）。

支持环境变量：`-e THREADS=16 -e SORT_MEM=2G -e SAFE_MODE=1`

---

## 快速开始：BAM → EIGENSTRAT 交付数据集

### 单样本

```bash
docker run --rm \
    -v /path/to/bam_dir:/input:ro \
    -v /path/to/output_dir:/output \
    wgs-all:latest \
    bam-to-eigenstrat \
        --bam /input/SAMPLE.sorted.bam \
        --population MyPop \
        -o /output \
        -n SAMPLE \
        --deliver-hg19
```

**产出**（在 `/path/to/output_dir/`）：
- `SAMPLE.geno` / `SAMPLE.snp` / `SAMPLE.ind` — hg38 坐标
- `SAMPLE.hg19.geno` / `SAMPLE.hg19.snp` / `SAMPLE.hg19.ind` — **hg19 坐标（交付这个）**
- `SAMPLE.stats.txt` — 覆盖度统计
- `SAMPLE.mpileup.log` — samtools 日志

### 批量多样本（合并成一个数据集）

```bash
# 在宿主机准备 bam 列表文件
ls /path/to/bams/*.sorted.bam > /path/to/bamlist.txt

docker run --rm \
    -v /path/to:/data \
    wgs-all:latest \
    bam-to-eigenstrat \
        --bam-list /data/bamlist.txt \
        --population MyPop \
        -o /data/output \
        -n batch_2026_01 \
        --deliver-hg19 \
        --seed 42
```

多个 BAM 会被**合并到一个 EIGENSTRAT 数据集**（每个样本一列，群体标签相同）。

---

## 参数详解

### 必填
- `--bam FILE [FILE...]` 或 `--bam-list FILE` — 输入 BAM
- `-o OUTPUT` — 输出目录
- `-n NAME` — 数据集名（输出文件前缀）

### 常用
- `-p, --population NAME` — 群体标签（写入 .ind）
- `--deliver-hg19` — **交付必加**，额外产 hg19 坐标版本
- `--position-set v42.4.1240K` 或 `v66.2M.aadr` — 位点集（默认 1240K）
- `--seed N` — 随机种子（randomHaploid 复现用）
- `--sample-ids "id1,id2,..."` — 覆盖默认样本名
- `--sex "sample1:M,sample2:F"` — 指定样本性别（默认 U=未知）

### 古 DNA 专用
- `--skip-transitions` — 忽略 C↔T / G↔A 位点（避开 aDNA damage 假阳性）
- `--method majorityCall` — 多数投票而非随机抽取（覆盖度高时用）
- `--min-mapq 30` — 最低比对质量
- `--min-baseq 30` — 最低碱基质量

完整参数：`docker run --rm wgs-all:latest help`

---

## 其他能力

### Y 单倍群分析

```bash
# 先从全基因组 BAM 提取 chrY
docker run --rm -v /data:/data wgs-all:latest \
    cli extract-chr /data/SAMPLE.sorted.bam chrY -o /data/output

# 跑 Y 单倍群 (yleaf)
docker run --rm -v /data:/data wgs-all:latest \
    analyze-y /data/output/SAMPLE.chrY.bam -o /data/yleaf_out
```

产出: Y 单倍群判定 (如 O-M175, D-M174, R-M269 等)

**⚠️ 已升级到 Yleaf v4.0.2** (2026-05-27 发布)：
- 内置 4 种 Y-SNP 树：`isogg`(默认)、`yfull`、`yfull_v10`、`ftdna`
- 支持 hg38 / hg19 / t2t 三种参考系
- 支持古 DNA 模式 (`-aDNA`，默认开启)
- 自带 samtools/bcftools，无外部依赖
- 首次运行会自动下载参考基因组 (~938 MB)，之后缓存

```bash
# 用不同的树
docker run ... wgs-all analyze-y /data/x.chrY.bam -o /data/out --tree yfull
docker run ... wgs-all analyze-y /data/x.chrY.bam -o /data/out --tree ftdna

# 关闭古 DNA 模式（现代高覆盖样本）
docker run ... wgs-all analyze-y /data/x.chrY.bam -o /data/out --no-adna
```

### MT 单倍群分析

```bash
# 先提取 chrM + SNP calling
docker run --rm -v /data:/data wgs-all:latest \
    cli extract-chr /data/SAMPLE.sorted.bam chrM -o /data/output

# 跑 MT 单倍群 (Haplogrep3)
docker run --rm -v /data:/data wgs-all:latest \
    analyze-mt /data/output/SAMPLE.chrM.vcf.gz -o /data/mt_result.txt
```

产出: MT 单倍群判定 (如 H4a1a4b, D4, B4a1 等)

### 芯片格式导出

从 BAM 提取基因型，生成各家基因检测公司的芯片结果文件格式。
可上传到 GEDmatch、DNA.Land 等第三方平台做祖源分析。

```bash
docker run --rm -v /data:/data wgs-all:latest \
    cli extract-chip /data/SAMPLE.sorted.bam -o /data/chip_formats
```

产出 11 种格式:
- 23andMe V3 / V5 / V35
- AncestryDNA V1 / V2
- FamilyTreeDNA V2 / V3
- LivingDNA V1 / V2
- MyHeritage V1 / V2

### 1240K 古 DNA 位点提取 (TSV 格式)

```bash
docker run --rm -v /data:/data wgs-all:latest \
    extract-1240k /data/SAMPLE.sorted.bam -o /data/sample_1240k.txt
```

产出: 人类可读的 TSV 文件 (rsID / chrom / pos / genotype)，和 EIGENSTRAT 不同格式但同样的位点。

### 常染色体祖源计算器 (28 个)

从芯片格式文件计算祖源成分比例。支持 E11、K13、K36、K47、HarappaWorld 等 28 个计算器。

```bash
# 先导出芯片格式
docker run --rm -v /data:/data wgs-all:latest \
    extract-chip /data/SAMPLE.sorted.bam -o /data/chip

# 跑指定计算器
docker run --rm -v /data:/data wgs-all:latest \
    admixture-calc /data/chip/SAMPLE_23andMe_V5.txt -c E11,K12b,K36

# 跑全部 28 个
docker run --rm -v /data:/data wgs-all:latest \
    admixture-calc /data/chip/SAMPLE_23andMe_V5.txt

# 列出所有可用计算器
docker run --rm wgs-all:latest admixture-calc --list-models
```

可用计算器: E11, K12b, K13, K13M2, K14M1, K18M4, K25R1, K36, K47, K7b, K7M1,
K7AMI, K8AMI, EUtest13, Eurasia7, globe10, globe13, HarappaWorld, Jtest14,
Africa9, AncientNearEast13, KurdishK10, MDLPk27, MichalK25, puntDNAL,
TurkicK11, weac2, world9

### PCA 主成分分析

将样本投影到参考人群的 PCA 空间，看样本和哪些人群最接近。

**需要用户提供参考人群 EIGENSTRAT 数据**（如 AADR 子集）。

```bash
# 参考人群数据挂载到 /ref
docker run --rm -v /data:/data -v /path/to/ref:/ref:ro wgs-all:latest \
    pca /data/eigenstrat/my_sample --ref /ref/aadr_subset -o /data/pca_out
```

产出: PCA 坐标 (PC1-PC10) + 最近参考人群列表。

### qpAdm 祖源建模

使用 ADMIXTOOLS qpAdm 估算目标样本由哪些源人群混合而成。

**需要用户提供合并后的 EIGENSTRAT 数据**（含样本 + 参考人群）。

```bash
docker run --rm -v /data:/data wgs-all:latest \
    cli full-pipeline --bam /data/SAMPLE.bam -o /data/results
```

### 一键全流程

一条命令跑完所有分析（chrY/chrM 提取 → Y/MT 单倍群 → EIGENSTRAT → 芯片格式 → 祖源计算器）：

```bash
docker run --rm -v /data:/data wgs-all:latest \
    full-pipeline --bam /data/SAMPLE.sorted.bam -o /data/full_results -p MyPop
```

产出目录结构:
```
full_results/
├── SAMPLE/
│   ├── SAMPLE.chrY.bam + .vcf.gz     # chrY 提取
│   ├── SAMPLE.chrM.bam + .vcf.gz     # chrM 提取
│   ├── yleaf/                          # Y 单倍群结果
│   ├── mt_haplogroup.txt               # MT 单倍群结果
│   └── chip/                           # 11 种芯片格式 + 祖源计算器
└── eigenstrat/
    └── dataset.geno/.snp/.ind          # 合并 EIGENSTRAT 数据集
```

## 完整命令速查

| 命令 | 功能 | 示例 |
|---|---|---|
| `align` | FASTQ → hg38 BAM | `wgs-all align SAMPLE R1.fq R2.fq` |
| `align-hg19` | FASTQ → hg19 BAM (hs37d5) | `wgs-all align-hg19 SAMPLE R1.fq R2.fq` |
| `bam-to-eigenstrat` | BAM → EIGENSTRAT 数据集 | `wgs-all bam-to-eigenstrat --bam x.bam --deliver-hg19 ...` |
| `analyze-y` | chrY BAM → Y 单倍群 | `wgs-all analyze-y x.chrY.bam -o out/` |
| `analyze-mt` | chrM VCF → MT 单倍群 | `wgs-all analyze-mt x.chrM.vcf.gz -o result.txt` |
| `extract-chr` | 全基因组 BAM → chrY/chrM BAM + VCF | `wgs-all extract-chr x.bam chrY -o out/` |
| `extract-chip` | BAM → 11 种芯片格式 | `wgs-all extract-chip x.bam -o chip/` |
| `extract-1240k` | BAM → 1240K TSV | `wgs-all extract-1240k x.bam -o result.txt` |
| `admixture-calc` | 芯片文件 → 祖源成分 (28 个计算器) | `wgs-all admixture-calc x_23andMe_V5.txt -c E11,K36` |
| `pca` | EIGENSTRAT → PCA 坐标 (需参考人群) | `wgs-all pca sample --ref ref_data -o pca_out/` |
| `full-pipeline` | 一键全流程 (BAM → 全部结果) | `wgs-all full-pipeline --bam x.bam -o out/` | ⚠️ 未经全量测试 |
| `detect-bam` | 识别 BAM 参考版本 | `wgs-all detect-bam x.bam` |
| `cli <cmd>` | 透传任意 CLI 子命令 | `wgs-all cli check-references` |
| `shell` | 交互式 bash | `wgs-all shell` |
| `help` | 显示帮助 | `wgs-all help` |

所有命令都支持 `--help` 查看详细参数。

```bash
# 检测 BAM 参考版本
docker run --rm -v /data:/data wgs-all:latest \
    cli detect-bam /data/SAMPLE.sorted.bam

# Y 单倍群分析
docker run --rm -v /data:/data wgs-all:latest \
    cli analyze-y /data/SAMPLE.chrY.bam

# 提取 1240K (自定义 TSV 格式)
docker run --rm -v /data:/data wgs-all:latest \
    cli extract-1240k /data/SAMPLE.sorted.bam -o /data/result.txt
```

### 交互式 shell（调试用）

```bash
docker run --rm -it -v /data:/data wgs-all:latest shell
# 进入容器 bash，可以手动跑命令、检查数据
```

---

## 功能测试状态

| 功能 | 测试状态 | 说明 |
|---|---|---|
| align (hg38) | ✅ 真实数据验证 | JP244、111-1953-3143、目标机器 242 样本 |
| align-hg19 | ✅ 真实数据验证 | 111-1953-3143 比对到 hs37d5 |
| bam-to-eigenstrat (hg38) | ✅ 真实数据 + 字节级验证 + 两条路线对比 | 95.67% 基因型一致 |
| bam-to-eigenstrat (hg19) | ✅ 真实数据验证 | 111-1953-3143 hg19 BAM |
| extract-chr chrY/chrM | ✅ 真实数据验证 | JP244: chrY 18.14x, chrM 163.21x |
| analyze-y (yleaf) | ⚠️ 管道跑通，结果 Unknown | yleaf 位点表过旧，后续更新 |
| analyze-mt (Haplogrep3) | ✅ 真实数据验证 | JP244: A11+16234 (质量 0.882) |
| extract-chip | ✅ 真实数据验证 | JP244: 12 个文件，232 MB |
| extract-1240k | ✅ 容器内跑通 | 需进一步验证输出内容 |
| admixture-calc | ✅ 真实数据验证 | JP244 E11: East Chinese 34.56% |
| pca (smartpca) | ⚠️ 工具可用，未跑完整流程 | 需要用户提供参考人群数据 |
| qpAdm | ⚠️ 工具可用，未跑完整流程 | 需要用户提供参考人群 + 外群 |
| full-pipeline | ❌ 未测试 | 串联逻辑待验证 |

### 关于 PCA / qpAdm 的说明

这两个功能**工具已就绪**（smartpca v16000、qpAdm v810），代码也写好了，但需要**用户自行提供参考人群数据**才能跑。

原因：参考人群因研究方向而异（做东亚用东亚参考，做欧洲用欧洲参考），不适合写死在镜像里。

用户需要准备：
- **PCA**: 参考人群的 EIGENSTRAT 三件套（如 AADR 子集），挂载到容器
- **qpAdm**: 合并后的 EIGENSTRAT（含样本 + 参考 + 外群），通过 `mergeit` 工具合并

镜像内已包含 `mergeit`、`convertf` 等数据准备工具，用户可以在容器内完成数据合并。

---

## 性能参考

| 任务 | 样本 | 耗时 |
|---|---|---|
| FASTQ → hg38 BAM (6.2 GB FASTQ) | 111-1953-3143 | ~23 分钟 |
| FASTQ → hg19 BAM (6.2 GB FASTQ) | 111-1953-3143 | ~15 分钟 |
| 单 BAM → EIGENSTRAT + hg19 回换 | JP244 (4 GB) | ~47 秒 |
| 300 个 BAM 合并跑 EIGENSTRAT（估算） | — | 1-6 小时 |

**批量跑 300 样本的建议**：
- 确保目标机器有 ≥ 100 GB 临时空间（mpileup 输出很大）
- 预估最终 .geno ≈ 5-10 MB / 样本（300 样本 ≈ 2 GB）
- 一次跑全部样本合并好（一个 EIGENSTRAT 方便下游分析，不用再合并）

---

## 挂载路径说明

| 宿主机 | 容器 | 用途 |
|---|---|---|
| `-v /path/to/bams:/input:ro` | `/input` | 只读输入 BAM |
| `-v /path/to/out:/output` | `/output` | 输出目录（需要写权限） |
| `-v /path:/data` | `/data` | 或者一个目录同时承担输入输出 |

**无需挂载参考数据** — hg38 FASTA、1240K 位点等全部在镜像内 `/reference/` 下。

---

## 交付物说明（给下游分析师）

一次 `--deliver-hg19` 跑完，你交付的是：

```
SAMPLE.hg19.geno   # 基因型矩阵 (123 万行 × N 样本)
SAMPLE.hg19.snp    # 位点信息 (hg19 坐标)
SAMPLE.hg19.ind    # 样本信息
SAMPLE.stats.txt   # 每个样本覆盖度统计（可附带）
```

对方用法：
- **smartpca**：直接读三件套做 PCA
- **qpAdm / qpDstat**：ADMIXTOOLS 原生格式
- **ADMIXTURE**：需先 `convertf` 转 PLINK bed/bim/fam
- **合并 AADR**：用 `mergeit` (ADMIXTOOLS 工具) 按 rsID 合并

三件套按 AADR v42.4 1240K 位点定义产出，**rsID / ref / alt / 坐标完全对齐 AADR**，可无缝合并全球古 DNA 数据。

---

## 故障排查

### 报错：`BAM 不是 hg38`
检查 BAM header：`docker run --rm -v /data:/data wgs-all cli detect-bam /data/x.bam`。
本镜像只支持 hg38 BAM。hg19 样本请直接用原版 `adna_to_dataset` 工具。

### 报错：`输入 BAM 混用了 chr 前缀风格`
一批 BAM 里既有 `chr1` 风格又有 `1` 风格。用 `samtools reheader` 统一。

### 输出 NonMissingCalls 很少（<5%）
样本覆盖度低或 BAM 区域受限。正常古 DNA 可能只有 5-15%，够用。
高覆盖现代样本应该 > 80%，低于此值检查 --min-mapq/--min-baseq 是否过严。

### 容器跑的结果和另一次不同
randomHaploid 有随机性。加 `--seed 42` 复现。

---

## 版本历史

| 版本 | 日期 | 变更 |
|---|---|---|
| 1.0.0 | 2026-05-10 | 初版：hg38 比对 + bam-to-eigenstrat (1240K) |
| 1.1.0 | 2026-05-10 | 加 v66.2M.aadr 位点集支持 |
| 1.2.0 | 2026-05-28 | 全能版：hg19 比对、Y/MT 单倍群、芯片格式、28 个祖源计算器、PCA、qpAdm、全流程一键命令、bcftools/smartpca/ADMIXTOOLS/PLINK/ADMIXTURE |

## 更新镜像（开发者）

```bash
cd /home/ladydd/wgs-platform
# 重新构建
bash docker/eigenstrat/build_bg.sh start
bash docker/eigenstrat/build_bg.sh log

# 重新导出 tar.gz
bash docker/eigenstrat/export_bg.sh start
bash docker/eigenstrat/export_bg.sh log
```

镜像是增量构建（基于 wgs-align:latest），如果改了 app/ 代码只会重建最后几层，很快。
