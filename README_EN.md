# WGS-All | Ancient DNA Analysis Platform

🇨🇳 [中文](README.md) | English

A self-contained Docker image for whole-genome sequencing analysis of ancient DNA. From FASTQ to ancestry reports — no internet, no dependencies, just `docker load` and run.

## Download

Docker image (14 GB) available at: **[guren.xin](https://guren.xin)**

After download:
```bash
docker load < wgs-all.tar
docker run --rm wgs-all help
```

## Features

- **Alignment**: FASTQ → BAM (hg38 / hg19 / T2T — three reference genomes)
- **Y Haplogroup**: Yleaf v4 (ISOGG / YFull / FTDNA trees, ancient DNA mode)
- **MT Haplogroup**: Haplogrep3 (PhyloTree 17)
- **EIGENSTRAT Export**: BAM → ancient DNA standard delivery format (1240K / 2M AADR)
- **Chip Formats**: 11 formats (23andMe / AncestryDNA / FTDNA / MyHeritage / LivingDNA)
- **Ancestry Calculators**: 28 models (E11, K13, K36, K47, HarappaWorld, etc.)
- **G25 Distance**: Compare with 10,927 modern + 1,003 ancient populations
- **Population Tools**: smartpca (PCA) / qpAdm (ADMIXTOOLS) / PLINK / ADMIXTURE
- **HTML Report**: One-page summary of all results

## Quick Start

```bash
# Load image
docker load < wgs-all.tar

# Align (hg38 / hg19 / T2T)
docker run --rm -v /data:/data wgs-all align SAMPLE R1.fq.gz R2.fq.gz
docker run --rm -v /data:/data wgs-all align-hg19 SAMPLE R1.fq.gz R2.fq.gz
docker run --rm -v /data:/data wgs-all align-t2t SAMPLE R1.fq.gz R2.fq.gz

# Y haplogroup
docker run --rm -v /data:/data wgs-all extract-chr /data/x.bam chrY -o /data -s SAMPLE
docker run --rm -v /data:/data wgs-all analyze-y /data/SAMPLE.chrY.bam -o /data/yleaf

# EIGENSTRAT export
docker run --rm -v /data:/data wgs-all bam-to-eigenstrat \
    --bam /data/x.bam -p Pop -o /data/out -n dataset --deliver-hg19

# Chip formats + ancestry calculator
docker run --rm -v /data:/data wgs-all extract-chip /data/x.bam -o /data/chip -s SAMPLE
docker run --rm -v /data:/data wgs-all admixture-calc /data/chip/SAMPLE_23andMe_V5.txt -c E11,K36

# G25 distance
docker run --rm wgs-all g25 --coords "0.02,-0.015,..." --top 20

# All commands
docker run --rm wgs-all help
```

## Requirements

- Docker 20+
- Disk: 50 GB (image) + data space
- RAM: 4 GB (analysis) / 16 GB (alignment)
- OS: Linux / macOS / Windows (Docker Desktop)

## Built-in Tools

| Tool | Version | Purpose |
|---|---|---|
| BWA | 0.7.19 | Sequence alignment |
| samtools | 1.16.1 | BAM processing |
| bcftools | 1.16 | Variant calling / VCF |
| pileupCaller | 1.6.0 | Ancient DNA genotyping (randomHaploid) |
| Yleaf | v4.0.2 | Y-chromosome haplogroup |
| Haplogrep3 | 3.2.2 | Mitochondrial haplogroup |
| PLINK | 1.9 | Genome data conversion |
| ADMIXTURE | 1.3 | Ancestry estimation |
| smartpca | v16000 | PCA |
| ADMIXTOOLS | v810 | qpAdm / f-statistics |

## Key Design Choices

- **Zero dependencies**: All reference genomes and tools bundled inside the image
- **Offline**: No internet required after `docker load`
- **Auto-detection**: Automatically identifies BAM reference version (hg38/hg19/T2T)
- **Chromosome naming**: Automatically adapts between `chrY`↔`Y`, `chrM`↔`MT`
- **Three references**: hg38, hg19 (hs37d5), and T2T (CHM13v2) — all with BWA indices

## Documentation

- [User Manual (中文)](docs/user-manual.md)
- [Credits & Citations](docs/credits.md)
- [Project Status](docs/project_review.md)

## License

MIT (platform code). See [credits.md](docs/credits.md) for individual tool licenses.

## Contact

hello@ladydd.com | [guren.xin](https://guren.xin)
