# 致谢与引用

本平台集成了以下开源工具和公开数据，感谢原作者的贡献。

## 工具

| 工具 | 版本 | 作者/团队 | License | 引用 |
|---|---|---|---|---|
| BWA | 0.7.19 | Heng Li | GPL-3 | Li H. (2013) Aligning sequence reads. arXiv:1303.3997 |
| samtools | 1.16 | Genome Research Ltd | MIT | Danecek P. et al. (2021) Twelve years of SAMtools. GigaScience |
| bcftools | 1.16 | Genome Research Ltd | MIT | 同上 |
| pileupCaller | 1.6.0 | Stephan Schiffels | GPL-3 | Schiffels S. et al. sequenceTools (GitHub) |
| Yleaf | v4.0.2 | Genid Lab | MIT | Ralf A. et al. (2024) Yleaf v4. Forensic Sci Int Genet |
| Haplogrep3 | 3.2.2 | Sebastian Schönherr | MIT | Weissensteiner H. et al. (2016) Haplogrep 2. NAR |
| PLINK | 1.9 | Shaun Purcell | GPL-3 | Purcell S. et al. (2007) PLINK. Am J Hum Genet |
| ADMIXTURE | 1.3 | David Alexander | Free (academic) | Alexander D. et al. (2009) Fast model-based estimation. Genome Res |
| smartpca | v16000 | Nick Patterson | Free (academic) | Patterson N. et al. (2006) Population structure. PLoS Genet |
| ADMIXTOOLS (qpAdm) | v810 | Nick Patterson | Free (academic) | Haak W. et al. (2015) Massive migration. Nature |
| admix | - | stevenliuyi | MIT | github.com/stevenliuyi/admix |
| WGSExtract | v4 | WGS Extract Dev Team | GPL-3 | wgsextract.github.io (芯片模板 + SNP 注释数据) |

## 数据

| 数据 | 来源 | 引用 |
|---|---|---|
| hg38 (GRCh38) | Genome Reference Consortium | GRC (2013) |
| hg19 (hs37d5) | 1000 Genomes Project | 1000 Genomes (2015) |
| T2T (CHM13v2) | T2T Consortium | Nurk S. et al. (2022) Science |
| AADR v42.4 1240K | David Reich Lab | Mallick S. et al. (2024) |
| G25 坐标 | Davidski / Vahaduo | Eurogenes Blog |
| PhyloTree | van Oven & Kayser | van Oven M. (2009) Hum Mutat |
| 芯片 SNP 注释 | 各厂商公开 | 23andMe, Illumina, etc. |

## 许可说明

- 本平台代码采用 MIT License
- 集成的 GPL 工具（BWA, pileupCaller, PLINK）要求：如果修改并分发这些工具的源码，需公开修改后的代码。使用其二进制文件不受此限制
- ADMIXTURE 和 ADMIXTOOLS 仅限学术/非商业使用
- G25 坐标数据使用需遵循 Vahaduo 的使用条款

## 如何引用本平台

如果您在研究中使用了本平台，请引用：

```
古基因数据分析平台 (WGS-All) v1.3.0
https://guren.xin
```

同时请引用上述对应工具的原始论文。
