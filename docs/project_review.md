# WGS 分析平台 — 项目进度

> 最后更新: 2026-05-30

## 当前版本: wgs-all v1.2.0 (31.4 GB)

已构建并测试通过的 Docker 镜像。下次重建将包含 T2T 参考 (~39 GB)。

---

## ✅ 已完成功能

### 比对 (FASTQ → BAM)
| 参考基因组 | 命令 | 状态 |
|---|---|---|
| hg38 (GRCh38) | `align` | ✅ 已测试 (242 样本) |
| hg19 (hs37d5) | `align-hg19` | ✅ 已测试 |
| T2T (CHM13v2) | `align-t2t` | ✅ 代码完成，待打包 |

### BAM 分析
| 功能 | 命令 | 状态 |
|---|---|---|
| 参考基因组识别 | `detect-bam` | ✅ 支持 hg38/hg19/T2T |
| 染色体提取 | `extract-chr` | ✅ |
| Y 单倍群 (Yleaf v4) | `analyze-y` | ✅ 离线，支持 hg38/hg19/t2t |
| MT 单倍群 (Haplogrep3) | `analyze-mt` | ✅ 离线 |
| EIGENSTRAT 导出 | `bam-to-eigenstrat` | ✅ 1240K + 2M AADR，支持 --deliver-hg19 |
| 芯片格式导出 | `extract-chip` | ✅ 11 种格式 |
| 祖源计算器 | `admixture-calc` | ✅ 28 个 (E11/K13/K36/K47 等) |
| G25 距离计算 | `g25` | ✅ 10927 现代 + 1003 古代参考 |
| HTML 报告 | `report` | ✅ |
| 一键全流程 | `full-pipeline` | ⚠️ 代码完成，未端到端测试 |

### 工具
| 工具 | 版本 | 状态 |
|---|---|---|
| samtools | 1.16.1 | ✅ |
| bcftools | 1.16 | ✅ |
| PLINK | 1.9 | ✅ |
| smartpca | 16000 | ✅ |
| qpAdm | 810 | ✅ |
| ADMIXTURE | 1.3 | ✅ |
| pileupCaller | - | ✅ |

---

## 🔧 本轮改进 (待下次构建生效)

1. ✅ T2T 比对 — align-t2t.sh + 全链路适配
2. ✅ LiftOver chain 文件离线 — 不再联网下载
3. ✅ 文件权限自动修复 — 输出文件不再属于 root
4. ✅ Yleaf v4 女性样本提示 — chrY <1x 时 warning
5. ✅ MT 单倍群格式统一 — 输出变异位点数 + 文件路径
6. ✅ HTML 报告生成 — 一页纸总结
7. ✅ entrypoint help 更新 — 所有命令示例

---

## ❌ 未实现 / 受限

| 功能 | 原因 |
|---|---|
| G25 坐标生成 (BAM → 25维) | Vahaduo PCA loadings 不公开 |
| 多样本并行 | 暂不需要 |
| PCA 可视化 | 用户说"暂时不搞" |

---

## 📋 待办 (下一阶段)

| # | 功能 | 优先级 | 说明 |
|---|---|---|---|
| 1 | 样本质量报告 | 高 | 覆盖度、内源 DNA 比例、损伤模式 (mapDamage2) |
| 2 | 污染评估 | 高 | MT 污染 (schmutzi)、X 染色体污染 (ANGSD/DICE) |
| 3 | full-pipeline 自动出报告 | 中 | 串联 full-pipeline + report，跑完直接出 HTML |
| 4 | ROH 近亲婚配检测 | 中 | Runs of Homozygosity，古 DNA 论文常用 |
| 5 | 性别判定 | 中 | X/Y 覆盖度比值，代码量极小但很实用 |
| 6 | kinship 亲缘关系 | 低 | 多样本间亲缘判定 (READ/lcMLkin) |
| 7 | 版本 changelog | 低 | 用户拿到新镜像知道改了什么 |
| 8 | 错误恢复/断点续跑 | 低 | 大批量时跑到一半断了不用从头来 |

---

## 📦 下次构建预期

- 镜像大小: ~39 GB (加 T2T 8.1 GB)
- 新增: T2T 比对 + chain 文件离线 + 权限修复 + Yleaf 修复
- 版本号: wgs-all v1.3.0

---

## 参考数据清单

| 数据 | 路径 (镜像内) | 大小 |
|---|---|---|
| hg38 + BWA 索引 | /reference/hg38/genome/ | ~16 GB |
| hg19 + BWA 索引 | /reference/hg19/genome/ | ~8.3 GB |
| T2T + BWA 索引 | /reference/t2t/genome/ | ~8.1 GB |
| AADR 1240K hg38 位点 | /reference/population/eigenstrat/ | ~50 MB |
| AADR hg19 .snp | /reference/aadr_positions/ | ~80 MB |
| 芯片模板 + SNP 注释 | /reference/microarray/ | ~406 MB |
| LiftOver chain | /reference/liftover/ | ~1.5 MB |
| Haplogrep3 + phylotree | /reference/tools/haplogrep/ | ~55 MB |
| G25 参考坐标 | /reference/population/g25/ | ~3 MB |
| admix 计算器模型 (28个) | pip 安装 | ~509 MB |
| Yleaf v4 (pip) | pip 安装 | ~102 MB |
