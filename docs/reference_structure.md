# Reference 目录结构设计

> WGS 平台参考数据的统一组织规范。每个基因组版本自包含，结构一致，缺什么一目了然。

---

## 设计原则

1. **按基因组版本分文件夹**：hg38 / hg19 / t2t，每个版本内部结构完全一致
2. **版本无关的资源单独放**：芯片模板、liftOver chain、分析工具、群体参考数据
3. **新增版本只需复制骨架，往里填文件**

---

## 完整目录结构

```
/reference/
│
├── hg38/                                  # ===== hg38 (GRCh38, 2013) =====
│   ├── genome/                            # 比对用
│   │   ├── hs38.fa                        #   参考基因组 FASTA
│   │   ├── hs38.fa.fai                    #   samtools 索引
│   │   ├── hs38.fa.bwt                    #   BWA 索引
│   │   ├── hs38.fa.amb                    #   BWA 索引
│   │   ├── hs38.fa.ann                    #   BWA 索引
│   │   ├── hs38.fa.pac                    #   BWA 索引
│   │   └── hs38.fa.sa                     #   BWA 索引
│   ├── snp/                               # SNP 注释（芯片提取、SNP calling 用）
│   │   ├── All_SNPs_hg38_ref.tab.gz       #   全 SNP 注释（bcftools annotate 用）
│   │   ├── All_SNPs_hg38_ref.tab.gz.tbi
│   │   ├── snps_hg38.vcf.gz              #   SNP VCF（yleaf 等工具用）
│   │   ├── snps_hg38.vcf.gz.tbi
│   │   └── snps_hg38.vcf.gz.gzi
│   ├── y_chromosome/                      # Y 染色体分析
│   │   ├── WGS_hg38.txt                   #   yleaf Y-SNP 位点文件
│   │   ├── BigY3_hg38.bed                 #   FTDNA BigY 区域定义
│   │   └── BigY3_hg38num.bed
│   ├── mt/                                # 线粒体分析
│   │   └── (Haplogrep 相关文件，待补)
│   └── 1240k/                             # 古 DNA 1240K 位点
│       └── 1240K_hg38.tab.gz
│
├── hg19/                                  # ===== hg19 (GRCh37, 2009) =====
│   ├── genome/
│   │   ├── hs37d5.fa
│   │   ├── hs37d5.fa.fai
│   │   └── (BWA 索引待建: bwa index hs37d5.fa，需几小时)
│   ├── snp/
│   │   ├── All_SNPs_hg19_ref.tab.gz
│   │   ├── All_SNPs_hg19_ref.tab.gz.tbi
│   │   ├── snps_hg19.vcf.gz
│   │   └── snps_hg19.vcf.gz.tbi
│   ├── y_chromosome/
│   │   ├── WGS_hg19.txt
│   │   ├── BigY3_hg37.bed
│   │   └── BigY3_hg37num.bed
│   ├── mt/
│   │   └── (待补)
│   └── 1240k/
│       └── (待准备 hg19 版 1240K)
│
├── t2t/                                   # ===== T2T-CHM13v2 (2022) =====
│   ├── genome/
│   │   └── (chm13v2.fa 待下载 + 建 BWA 索引)
│   ├── snp/
│   │   └── (待准备)
│   ├── y_chromosome/
│   │   └── (待准备)
│   ├── mt/
│   │   └── (待准备)
│   └── 1240k/
│       └── (待准备)
│
├── liftover/                              # ===== 坐标转换 chain 文件 =====
│   ├── hg38ToHg19.over.chain.gz           #   hg38 → hg19
│   ├── grch38-chm13v2.chain               #   hg38 → T2T
│   ├── hg19-chm13v2.chain                 #   hg19 → T2T
│   ├── chm13v2-hg19.chain                 #   T2T → hg19
│   └── chm13v2-grch38.chain               #   T2T → hg38
│
├── microarray/                            # ===== 芯片模板（版本无关）=====
│   ├── raw_file_templates/
│   │   ├── body/                          #   11种芯片格式模板体
│   │   │   ├── 23andMe_V3.txt
│   │   │   ├── 23andMe_V5.txt
│   │   │   ├── 23andMe_V35.txt
│   │   │   ├── Ancestry_V1.txt
│   │   │   ├── Ancestry_V2.txt
│   │   │   ├── FTDNA_V2.csv
│   │   │   ├── FTDNA_V3.csv
│   │   │   ├── LDNA_V1.txt
│   │   │   ├── LDNA_V2.txt
│   │   │   ├── MyHeritage_V1.csv
│   │   │   └── MyHeritage_V2.csv
│   │   └── head/                          #   各格式文件头
│   └── ploidy.txt
│
├── population/                            # ===== 群体参考数据（PLINK 分析用）=====
│   ├── g25/                               #   G25 坐标数据集
│   │   └── (现代+古代群体参考坐标，待准备)
│   ├── 1000genomes/                       #   千人基因组计划数据
│   │   └── (现代人群 PLINK 数据集，PCA 对比用，待准备)
│   ├── aadr/                              #   Allen Ancient DNA Resource
│   │   └── (古 DNA 大数据集，qpAdm 用，待准备)
│   └── README.md                          #   数据来源和版本说明
│
└── tools/                                 # ===== 分析工具 =====
    ├── yleaf/                             #   Y 单倍群分析
    │   ├── yleaf.py
    │   ├── predict_haplogroup.py
    │   └── Hg_Prediction_tables/
    ├── haplogrep/                         #   MT 单倍群分析（待安装）
    └── plink/                             #   PLINK 群体遗传分析（待安装）
```

---

## 各版本就绪状态

| 版本 | genome | BWA索引 | SNP注释 | Y染色体 | MT | 1240K | 状态 |
|------|--------|---------|---------|---------|-----|-------|------|
| hg38 | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | **可用** |
| hg19 | ✅ | ❌ 待建 | ✅ | ✅ | ❌ | ❌ | 差 BWA 索引 |
| t2t  | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 全部待准备 |

---

## 分析流程与 reference 的对应关系

```
FASTQ (R1+R2)
  │
  ▼
比对 (BWA-MEM)  ──────────── 用 {version}/genome/*.fa
  │
  ▼
BAM
  │
  ├─→ 提取 chrY ──────────── 用 {version}/genome/*.fa (samtools)
  │     └─→ Y 单倍群 ─────── 用 {version}/y_chromosome/WGS_*.txt + tools/yleaf/
  │
  ├─→ 提取 chrM ──────────── 用 {version}/genome/*.fa (samtools)
  │     └─→ MT 单倍群 ────── 用 {version}/mt/ + tools/haplogrep/
  │
  ├─→ 芯片格式导出 ────────── 用 {version}/snp/ + microarray/ + liftover/
  │
  ├─→ 1240K 提取 ──────────── 用 {version}/1240k/ + {version}/genome/*.fa
  │
  └─→ PLINK 群体分析 ──────── 用 population/ + tools/plink/
       ├─→ PCA（跟现代人群对比）
       ├─→ ADMIXTURE（祖源成分）
       └─→ qpAdm（古DNA 祖源建模）
```

---

## 待办

- [ ] hg19: 建 BWA 索引 (`bwa index hs37d5.fa`)
- [ ] hg19: 准备 1240K 位点文件
- [ ] t2t: 下载 chm13v2.fa + 建 BWA 索引
- [ ] t2t: 准备 SNP 注释、Y 染色体、1240K 等配套文件
- [ ] MT: 安装 Haplogrep，准备 MT 分析所需文件
- [ ] PLINK: 安装 plink，准备群体参考数据集（1000genomes、AADR、G25）
- [ ] 代码适配: 更新 reference.py 匹配新目录结构
- [ ] 迁移脚本: 把现有 reference 文件按新结构重新组织

---

## 已完成

- [x] reference 目录新结构设计完成
- [x] 迁移脚本执行完成（符号链接方式，hg38 全套就绪）
- [x] `app/core/reference.py` 重写，适配新目录结构
- [x] `app/core/bam_detector.py` BAM 参考系自动识别模块
- [x] Docker 比对镜像构建成功（wgs-align:latest, 13GB, 含 hg38 全套）
- [x] 镜像导出 wgs-align.tar.gz (4.1GB)，已在目标机器成功运行
- [x] 批量比对脚本 `scripts/batch_align.sh`
- [x] 预检脚本 `scripts/preflight_check.sh`

## 待讨论

- [ ] 资源分配策略：大样本 OOM / 磁盘不足的处理方案（下次重点讨论）
