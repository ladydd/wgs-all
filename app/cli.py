#!/usr/bin/env python3
"""
命令行接口 - 用于测试各个 Pipeline 模块
"""

import os
import sys
import argparse
from pathlib import Path

from .core.config import settings
from .core.logging import logger
from .core.reference import reference_manager


def cmd_check_references(args):
    """检查参考文件"""
    version = args.version
    
    if version:
        # 检查单个版本
        logger.info(f"检查参考文件 ({version})...")
        results = reference_manager.validate_references(version)
        config = reference_manager.get_config(version)
        
        print(f"\n参考文件状态: {config.display_name}")
        print("-" * 40)
        for name, exists in results.items():
            status = "✓" if exists else "✗"
            print(f"  {status} {name}")
        
        all_ok = all(results.values())
        if all_ok:
            print("\n所有文件就绪!")
        else:
            print("\n有文件缺失，请检查!")
            sys.exit(1)
    else:
        # 检查所有版本
        summary = reference_manager.get_readiness_summary()
        print("\n参考文件状态总览:")
        print("=" * 50)
        for ver, info in summary.items():
            status = "✅" if info["ready"] else "⚠️"
            ok_count = sum(1 for v in info["files"].values() if v)
            total = len(info["files"])
            print(f"\n{status} {info['display_name']}  ({ok_count}/{total})")
            for name, exists in info["files"].items():
                mark = "✓" if exists else "✗"
                print(f"    {mark} {name}")


def cmd_detect_bam(args):
    """检测 BAM 参考基因组"""
    from .core.bam_detector import detect_bam_reference, map_to_system_version
    
    bam_file = args.bam
    logger.info(f"检测 BAM: {bam_file}")
    
    info = detect_bam_reference(bam_file)
    
    print(f"\nBAM 文件: {info.file_path}")
    print(f"参考基因组: {info.reference_display}")
    print(f"chr1 长度: {info.chr1_length:,}")
    print(f"chr 前缀: {'是' if info.has_chr_prefix else '否'}")
    print(f"线粒体名称: {info.mt_name or '未知'}")
    print(f"置信度: {info.confidence}")
    
    if info.confidence == "high":
        system_ver = map_to_system_version(info)
        print(f"系统版本: {system_ver}")
    else:
        print("⚠️ 无法识别参考基因组版本")


def cmd_plan(args):
    """预检样本资源"""
    from .core.resource_planner import estimate_sample, detect_machine_resources, plan_alignment
    
    r1 = args.r1
    r2 = args.r2
    sample_id = args.sample or Path(r1).stem.replace('_combined_R1.fastq', '').replace('.gz', '')
    output_dir = args.output or "."
    
    # 估算样本
    est = estimate_sample(sample_id, r1, r2)
    print(f"\n样本: {est.sample_id}")
    print(f"  R1: {est.r1_size_gb:.1f} GB")
    print(f"  R2: {est.r2_size_gb:.1f} GB")
    print(f"  合计: {est.input_total_gb:.1f} GB")
    print(f"  预估 BAM: ~{est.est_bam_gb:.0f} GB")
    print(f"  预估临时文件: ~{est.est_temp_gb:.0f} GB")
    print(f"  预估磁盘需求: ~{est.est_disk_need_gb:.0f} GB")
    
    # 检测机器
    machine = detect_machine_resources(output_dir)
    print(f"\n机器资源:")
    print(f"  CPU: {machine.cpu_count} 核")
    print(f"  内存: {machine.avail_memory_gb}/{machine.total_memory_gb} GB (可用/总计)")
    print(f"  磁盘: {machine.disk_avail_gb} GB 可用 ({machine.disk_path})")
    
    # 生成计划
    plan = plan_alignment(est, machine)
    print(f"\n执行计划:")
    if plan.can_run:
        print(f"  ✅ {plan.reason}")
        print(f"  线程: {plan.threads}")
        print(f"  排序内存: {plan.sort_memory}/线程")
        print(f"  总内存: ~{plan.total_memory_gb} GB")
        print(f"  预估耗时: ~{plan.est_hours} 小时")
        print(f"  Docker 限制: --memory={plan.docker_memory_limit}")
        if plan.warnings:
            for w in plan.warnings:
                print(f"  ⚠️ {w}")
    else:
        print(f"  ❌ {plan.reason}")


def cmd_plan_batch(args):
    """批量预检"""
    import glob
    from .core.resource_planner import estimate_sample, detect_machine_resources, plan_batch
    
    fastq_dir = args.fastq_dir
    output_dir = args.output or "."
    
    # 扫描样本
    samples = []
    for r1 in sorted(glob.glob(os.path.join(fastq_dir, "*_combined_R1.fastq.gz"))):
        sample_id = Path(r1).stem.replace('_combined_R1.fastq', '').replace('.gz', '')
        r2 = r1.replace('_R1.fastq.gz', '_R2.fastq.gz')
        if os.path.exists(r2):
            samples.append((sample_id, r1, r2))
    
    if not samples:
        print("未找到 FASTQ 文件对")
        return
    
    print(f"找到 {len(samples)} 个样本")
    
    # 检测机器
    machine = detect_machine_resources(output_dir)
    print(f"机器: {machine.cpu_count}核, {machine.avail_memory_gb}GB 可用内存, {machine.disk_avail_gb}GB 磁盘")
    
    # 批量规划
    result = plan_batch(samples, machine)
    
    print(f"\n{'='*60}")
    print(f"  可运行: {result['runnable_count']} 个样本")
    print(f"  跳过:   {result['skipped_count']} 个样本")
    print(f"  总耗时: ~{result['total_hours']} 小时 ({result['total_days']} 天)")
    print(f"  总磁盘: ~{result['total_disk_gb']} GB (BAM 输出)")
    print(f"{'='*60}")
    
    # 时间线
    tl = result['timeline']
    if tl['checkpoints']:
        print(f"\n⏱️  时间线:")
        print(f"  单样本: {tl['per_sample']['min_hours']}-{tl['per_sample']['max_hours']}h (平均 {tl['per_sample']['avg_hours']}h)")
        for cp in tl['checkpoints']:
            print(f"  {cp['progress_pct']}% ({cp['samples_done']}个) → ~{cp['days_elapsed']}天")
    
    # 建议
    if result['recommendation']:
        print(f"\n📋 建议:")
        for r in result['recommendation']:
            print(f"  {r}")
    
    # 跳过的样本
    if result['skipped']:
        print(f"\n❌ 跳过的样本:")
        for s in result['skipped']:
            print(f"  {s['sample_id']} ({s['input_gb']:.1f}GB): {s['reason']}")
    
    # 前几个样本
    if result['runnable']:
        print(f"\n✅ 前 5 个样本:")
        for s in result['runnable'][:5]:
            print(f"  {s['sample_id']} ({s['input_gb']:.1f}GB): {s['threads']}线程, {s['sort_memory']}/线程, ~{s['est_hours']}h")


def cmd_align(args):
    """比对 FASTQ 文件"""
    from .pipeline.alignment import AlignmentModule
    
    fastq_r1 = args.r1
    fastq_r2 = args.r2
    sample_id = args.sample or Path(fastq_r1).stem.replace('_1', '').replace('.fastq', '')
    output_dir = args.output or f"{sample_id}"
    
    logger.info(f"比对样本: {sample_id}")
    
    aligner = AlignmentModule(
        reference=args.reference or "hg38",
        threads=args.threads or settings.threads,
    )
    
    result = aligner.align(fastq_r1, fastq_r2, output_dir, sample_id)
    
    print(f"\n比对完成:")
    print(f"  BAM 文件: {result.bam_file}")
    print(f"  总读取数: {result.total_reads:,}")
    print(f"  比对率: {result.mapping_rate:.1f}%")


def cmd_extract_chr(args):
    """提取染色体"""
    from .pipeline.alignment import ChromosomeExtractor
    from .core.bam_detector import detect_bam_reference, map_to_system_version
    
    bam_file = args.bam
    chromosome = args.chromosome
    sample_id = args.sample or Path(bam_file).stem.replace('.sorted', '')
    output_dir = args.output or str(Path(bam_file).parent)
    
    # 自动检测参考版本（除非用户指定）
    if args.reference:
        reference = args.reference
    else:
        bam_info = detect_bam_reference(bam_file)
        reference = map_to_system_version(bam_info)
    
    logger.info(f"提取 {chromosome}: {bam_file}")
    
    extractor = ChromosomeExtractor(
        reference=reference,
        threads=args.threads or settings.threads,
    )
    
    result = extractor.extract(bam_file, chromosome, output_dir, sample_id)
    
    print(f"\n提取完成:")
    print(f"  BAM 文件: {result.bam_file}")
    print(f"  覆盖度: {result.coverage:.2f}x")
    if result.vcf_file:
        print(f"  VCF 文件: {result.vcf_file}")
        print(f"  SNP 数量: {result.snp_count}")


def cmd_extract_chip(args):
    """提取芯片格式"""
    from .pipeline.extraction import ChipFormatExtractor
    from .core.bam_detector import detect_bam_reference, map_to_system_version
    
    bam_file = args.bam
    output_dir = args.output or f"{Path(bam_file).stem}_chip_formats"
    sample_id = args.sample or Path(bam_file).stem.replace('.sorted', '')
    
    # 自动检测参考版本
    bam_info = detect_bam_reference(bam_file)
    reference = map_to_system_version(bam_info)
    
    logger.info(f"提取芯片格式: {bam_file}")
    logger.info(f"输出目录: {output_dir}")
    logger.info(f"样本 ID: {sample_id}")
    
    extractor = ChipFormatExtractor(reference=reference)
    results = extractor.extract(bam_file, output_dir, sample_id)
    
    print(f"\n生成 {len(results)} 个文件:")
    for r in results:
        print(f"  {r.format_type}: {r.positions_with_genotype}/{r.total_positions} ({r.genotype_rate*100:.1f}%)")


def cmd_extract_1240k(args):
    """提取 1240K 位点"""
    from .pipeline.extraction import K1240Extractor
    
    bam_file = args.bam
    sample_id = args.sample or Path(bam_file).stem.replace('.sorted', '')
    output_file = args.output or f"{sample_id}_1240K.txt"
    
    logger.info(f"提取 1240K: {bam_file}")
    logger.info(f"输出文件: {output_file}")
    
    extractor = K1240Extractor()
    result = extractor.extract(bam_file, output_file)
    
    print(f"\n结果:")
    print(f"  总位点: {result.total_positions}")
    print(f"  有基因型: {result.positions_with_genotype}")
    print(f"  覆盖率: {result.genotype_rate*100:.1f}%")
    print(f"  输出文件: {result.file_path}")


def _cmd_report(args):
    """生成 HTML 报告"""
    from .pipeline.report import generate_report

    # 收集已有结果
    admixture = None
    if args.admix_json and Path(args.admix_json).exists():
        import json
        with open(args.admix_json) as f:
            admixture = json.load(f)

    generate_report(
        sample_id=args.sample,
        output_file=args.output,
        y_haplogroup=args.y_hg,
        y_qc=float(args.y_qc) if args.y_qc else None,
        mt_haplogroup=args.mt_hg,
        mt_quality=float(args.mt_quality) if args.mt_quality else None,
        admixture=admixture,
        eigenstrat_snps=int(args.eigen_snps) if args.eigen_snps else None,
        chip_formats=int(args.chip_n) if args.chip_n else None,
        reference=args.reference,
    )
    print(f"报告已生成: {args.output}")


def _cmd_g25(args):
    """G25 距离计算"""
    from .pipeline.g25 import G25Calculator

    calc = G25Calculator()

    if args.coords:
        coords = [float(x) for x in args.coords.split(",")]
        result = calc.find_nearest(coords, sample_id=args.sample or "Sample", top_n=args.top)
    elif args.file:
        result = calc.find_nearest_from_file(args.file, sample_id=args.sample, top_n=args.top)
    else:
        print("错误: 请提供 --coords 或 --file")
        return

    print(f"\nG25 距离计算: {result.sample_id}")
    print(f"\n最近现代人群 (前 {args.top}):")
    for name, dist in result.nearest_modern:
        print(f"  {dist:.6f}  {name}")
    if result.nearest_ancient:
        print(f"\n最近古代样本 (前 {args.top}):")
        for name, dist in result.nearest_ancient:
            print(f"  {dist:.6f}  {name}")


def _cmd_pca(args):
    """PCA 分析"""
    from .pipeline.pca import PCAAnalyzer
    analyzer = PCAAnalyzer()
    result = analyzer.run(
        sample_prefix=args.sample_prefix,
        reference_prefix=args.ref,
        output_dir=args.output,
        sample_id=args.sample,
        num_pcs=args.num_pcs,
    )
    print(f"\nPCA 结果 ({result.sample_id}):")
    for pc, val in sorted(result.pc_coordinates.items()):
        print(f"  {pc}: {val:.6f}")
    if result.nearest_pops:
        print(f"\n最近人群 (前 10):")
        for name, dist in result.nearest_pops[:10]:
            print(f"  {name}: {dist:.6f}")


def _cmd_full_pipeline(args):
    """全流程一键分析"""
    from .pipeline.full_pipeline import run_full_pipeline

    bam_files = args.bam or []
    if args.bam_list:
        with open(args.bam_list) as f:
            bam_files = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]

    if not bam_files:
        print("错误: 请通过 --bam 或 --bam-list 提供 BAM 文件")
        return

    results = run_full_pipeline(
        bam_files=bam_files,
        output_dir=args.output,
        population=args.population,
        reference=args.reference,
        seed=args.seed,
    )

    print(f"\n全流程完成! 处理了 {len(results['samples'])} 个样本")
    for s in results["samples"]:
        print(f"\n  {s['sample_id']}:")
        print(f"    Y: {s.get('y_haplogroup', '?')}")
        print(f"    MT: {s.get('mt_haplogroup', '?')}")
        if "admixture" in s:
            for calc, comp in s["admixture"].items():
                top = sorted(comp.items(), key=lambda x: -x[1])[:3]
                top_str = ", ".join(f"{n}:{v:.1f}%" for n, v in top)
                print(f"    {calc}: {top_str}")


def cmd_admixture_calc(args):
    """常染色体祖源计算器"""
    from .pipeline.calculator import AdmixtureCalculator, AVAILABLE_CALCULATORS

    if args.list_models:
        print("可用计算器 (28 个):")
        for c in AVAILABLE_CALCULATORS:
            print(f"  {c}")
        return

    chip_file = args.chip_file
    if not chip_file:
        print("错误: 请提供芯片格式文件。用法: admixture-calc <file> [-c E11,K36]")
        return

    sample_id = args.sample or Path(chip_file).stem
    calculators = args.calculators.split(",") if args.calculators else None

    calc = AdmixtureCalculator()
    result = calc.run(
        chip_file=chip_file,
        sample_id=sample_id,
        calculators=calculators,
        vendor=args.vendor,
    )

    for cr in result.calculators:
        print(f"\n{cr.calculator}:")
        for name, pct in sorted(cr.components.items(), key=lambda x: -x[1]):
            print(f"  {name}: {pct:.2f}%")


def cmd_analyze_mt(args):
    """分析 MT 单倍群"""
    from .pipeline.haplogroup import MTHaplogroupAnalyzer

    vcf_file = args.vcf
    sample_id = args.sample or Path(vcf_file).stem.replace('.chrM', '').replace('.vcf', '').replace('.gz', '')
    output_file = args.output or f"{sample_id}_mt_haplogroup.txt"

    logger.info(f"分析 MT 单倍群: {vcf_file}")

    analyzer = MTHaplogroupAnalyzer()
    result = analyzer.analyze(vcf_file, output_file)

    print(f"\n结果:")
    print(f"  MT 单倍群: {result.haplogroup}")
    print(f"  质量分数: {result.quality_score}")
    print(f"  变异位点: {len(result.variants)}")
    print(f"  输出文件: {output_file}")
    print(f"  输出文件: {output_file}")


def cmd_vcf_to_chip(args):
    """从 VCF 提取芯片格式"""
    from .pipeline.vcf_extraction import VcfChipExtractor
    
    vcf_file = args.vcf
    sample_id = args.sample or Path(vcf_file).stem.replace('.vcf', '')
    output_dir = args.output or f"{sample_id}_chip_formats"
    reference = getattr(args, 'reference', 'hg38') or 'hg38'
    
    logger.info(f"从 VCF 提取芯片格式: {vcf_file} (参考: {reference})")
    logger.info(f"输出目录: {output_dir}")
    logger.info(f"样本 ID: {sample_id}")
    
    extractor = VcfChipExtractor(reference=reference)
    result = extractor.extract(vcf_file, output_dir, sample_id)
    
    print(f"\nVCF SNP 数量: {result['vcf_snps']}")
    print(f"匹配到 rsID: {result['matched']}")
    print(f"\n生成 {len(result['formats'])} 个文件:")
    for r in result['formats']:
        print(f"  {r['format']}: {r['with_genotype']}/{r['total']} ({r['rate']})")


def cmd_snp_to_chip(args):
    """从 .snp 文件提取芯片格式"""
    from .pipeline.snp_extraction import SnpChipExtractor
    
    snp_file = args.snp
    sample_id = args.sample or Path(snp_file).stem.replace('.snp', '')
    output_dir = args.output or f"{sample_id}_chip_formats"
    
    logger.info(f"从 SNP 文件提取芯片格式: {snp_file}")
    logger.info(f"输出目录: {output_dir}")
    logger.info(f"样本 ID: {sample_id}")
    
    extractor = SnpChipExtractor()
    result = extractor.extract(snp_file, output_dir, sample_id)
    
    print(f"\nSNP 总数: {result['total_snps']}")
    print(f"\n生成 {len(result['formats'])} 个文件:")
    for r in result['formats']:
        print(f"  {r['format']}: {r['with_genotype']}/{r['total']} ({r['rate']})")


def cmd_bam_to_eigenstrat(args):
    """批量 hg38 BAM → EIGENSTRAT 数据集 (古 DNA 交付格式)"""
    from .pipeline.eigenstrat import EigenstratExtractor, HgCoordRewriter

    # 解析 BAM 列表
    bam_files = args.bam
    # 如果 --bam-list 给了一个文件，从文件读
    if args.bam_list:
        if not os.path.exists(args.bam_list):
            raise FileNotFoundError(f"--bam-list 文件不存在: {args.bam_list}")
        with open(args.bam_list) as f:
            bam_files = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]

    if not bam_files:
        raise ValueError("请通过 --bam 或 --bam-list 提供 BAM 文件")

    # 样本 ID
    sample_ids = None
    if args.sample_ids:
        sample_ids = args.sample_ids.split(",")

    # 性别 (简化版，格式: sample1:M,sample2:F)
    sex_by_sample = {}
    if args.sex:
        for pair in args.sex.split(","):
            sid, s = pair.split(":")
            sex_by_sample[sid] = s

    logger.info(f"输入 BAM 数: {len(bam_files)}")

    extractor = EigenstratExtractor(
        reference_version=args.reference,
        calling_method=args.method,
        min_mapq=args.min_mapq,
        min_baseq=args.min_baseq,
        min_depth=args.min_depth,
        skip_transitions=args.skip_transitions,
        seed=args.seed,
    )

    result = extractor.extract(
        bam_files=bam_files,
        sample_ids=sample_ids,
        population=args.population,
        output_dir=args.output,
        output_name=args.name,
        position_set=args.position_set,
        sex_by_sample=sex_by_sample,
    )

    print(f"\n✅ hg38 EIGENSTRAT 产出:")
    print(f"  .geno: {result.geno_file}")
    print(f"  .snp:  {result.snp_file}")
    print(f"  .ind:  {result.ind_file}")
    print(f"  SNP 数: {result.total_snps}")
    print(f"  样本数: {len(result.sample_ids)}")

    # 如果要交付 → 转 hg19 坐标
    if args.deliver_hg19:
        if args.reference == "hg19":
            # hg19 BAM 产出的 EIGENSTRAT 本来就是 hg19 坐标，不需要回换
            logger.info("BAM 是 hg19，输出已是 hg19 坐标，跳过坐标回换")
            print(f"\n✅ 输出已是 hg19 坐标 (无需回换):")
            print(f"  .geno: {result.geno_file}")
            print(f"  .snp:  {result.snp_file}")
            print(f"  .ind:  {result.ind_file}")
        else:
            logger.info("开始 hg38 → hg19 坐标回换 (交付用)")
            rewriter = HgCoordRewriter()
            # AADR hg19 .snp 查找顺序:
            #   1. 用户 --aadr-snp 显式指定
            #   2. /reference/aadr_positions/<posset>.snp  (Docker 镜像内路径)
            #   3. <project>/adna_to_dataset/positions/<posset>.snp  (开发机路径)
            aadr_snp = args.aadr_snp
            if not aadr_snp:
                candidates = [
                    Path(f"/reference/aadr_positions/{args.position_set}.snp"),
                    Path(__file__).parent.parent / "adna_to_dataset" / "positions" / f"{args.position_set}.snp",
                ]
                for cand in candidates:
                    if cand.exists():
                        aadr_snp = str(cand)
                        break
                if not aadr_snp:
                    raise FileNotFoundError(
                        f"找不到 AADR hg19 .snp 文件 ({args.position_set}.snp)，"
                        f"请用 --aadr-snp 指定路径。已尝试: {candidates}"
                    )
            logger.info(f"AADR hg19 .snp: {aadr_snp}")
            hg19_prefix = os.path.join(args.output, f"{args.name}.hg19")
            out = rewriter.rewrite_to_hg19(
                eigenstrat_prefix=result.output_prefix,
                aadr_hg19_snp=aadr_snp,
                output_prefix=hg19_prefix,
            )
            print(f"\n✅ 交付版本 (hg19 坐标):")
            print(f"  .geno: {out['geno']}")
            print(f"  .snp:  {out['snp']}")
            print(f"  .ind:  {out['ind']}")
            print(f"  保留位点: {out['kept']} (丢弃 {out['dropped']})")


def cmd_analyze_y(args):
    """分析 Y 单倍群"""
    from .pipeline.haplogroup import YHaplogroupAnalyzer
    
    bam_file = args.bam
    sample_id = args.sample or Path(bam_file).stem.replace('.chrY', '').replace('.sorted', '')
    output_dir = args.output or f"{sample_id}_yleaf_results"
    
    logger.info(f"分析 Y 单倍群: {bam_file}")
    logger.info(f"输出目录: {output_dir}")
    
    analyzer = YHaplogroupAnalyzer(
        quality_thresh=args.quality or 20,
        reads_thresh=args.reads if args.reads is not None else 1,
        base_majority=args.majority or 90,
    )
    
    result = analyzer.analyze(
        bam_file, output_dir, sample_id,
        reference=args.reference,
        tree=args.tree,
        ancient_dna=not args.no_adna,
    )
    
    print(f"\n结果:")
    print(f"  Y 单倍群: {result.haplogroup}")
    print(f"  QC-score: {result.confidence}")
    print(f"  使用标记: {result.markers_used}")
    print(f"  输出目录: {result.output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="WGS Analysis Platform CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # check-references
    p_check = subparsers.add_parser("check-references", help="检查参考文件")
    p_check.add_argument("-v", "--version", help="基因组版本 (hg38/hg19/t2t)，不指定则检查全部")
    p_check.set_defaults(func=cmd_check_references)
    
    # detect-bam
    p_detect = subparsers.add_parser("detect-bam", help="检测 BAM 参考基因组版本")
    p_detect.add_argument("bam", help="BAM 文件路径")
    p_detect.set_defaults(func=cmd_detect_bam)
    
    # plan - 单样本预检
    p_plan = subparsers.add_parser("plan", help="预检单个样本资源需求")
    p_plan.add_argument("r1", help="R1 FASTQ 文件")
    p_plan.add_argument("r2", help="R2 FASTQ 文件")
    p_plan.add_argument("-o", "--output", help="输出目录 (用于检测磁盘)")
    p_plan.add_argument("-s", "--sample", help="样本 ID")
    p_plan.set_defaults(func=cmd_plan)
    
    # plan-batch - 批量预检
    p_batch = subparsers.add_parser("plan-batch", help="批量预检所有样本")
    p_batch.add_argument("fastq_dir", help="FASTQ 文件目录")
    p_batch.add_argument("-o", "--output", help="输出目录 (用于检测磁盘)")
    p_batch.set_defaults(func=cmd_plan_batch)
    
    # align
    p_align = subparsers.add_parser("align", help="比对 FASTQ 文件")
    p_align.add_argument("r1", help="R1 FASTQ 文件")
    p_align.add_argument("r2", help="R2 FASTQ 文件")
    p_align.add_argument("-o", "--output", help="输出目录")
    p_align.add_argument("-s", "--sample", help="样本 ID")
    p_align.add_argument("-r", "--reference", help="参考基因组 (hg38/hg19/t2t)")
    p_align.add_argument("-t", "--threads", type=int, help="线程数")
    p_align.set_defaults(func=cmd_align)
    
    # extract-chr
    p_chr = subparsers.add_parser("extract-chr", help="提取染色体")
    p_chr.add_argument("bam", help="输入 BAM 文件")
    p_chr.add_argument("chromosome", help="染色体 (chrY/chrM)")
    p_chr.add_argument("-o", "--output", help="输出目录")
    p_chr.add_argument("-s", "--sample", help="样本 ID")
    p_chr.add_argument("-r", "--reference", help="参考基因组 (hg38/hg19/t2t)")
    p_chr.add_argument("-t", "--threads", type=int, help="线程数")
    p_chr.set_defaults(func=cmd_extract_chr)
    
    # extract-chip
    p_chip = subparsers.add_parser("extract-chip", help="提取芯片格式")
    p_chip.add_argument("bam", help="输入 BAM 文件")
    p_chip.add_argument("-o", "--output", help="输出目录")
    p_chip.add_argument("-s", "--sample", help="样本 ID")
    p_chip.set_defaults(func=cmd_extract_chip)
    
    # extract-1240k
    p_1240k = subparsers.add_parser("extract-1240k", help="提取 1240K 位点")
    p_1240k.add_argument("bam", help="输入 BAM 文件")
    p_1240k.add_argument("-o", "--output", help="输出文件")
    p_1240k.add_argument("-s", "--sample", help="样本 ID")
    p_1240k.set_defaults(func=cmd_extract_1240k)
    
    # bam-to-eigenstrat
    p_eig = subparsers.add_parser(
        "bam-to-eigenstrat",
        help="BAM → EIGENSTRAT (支持 hg38 和 hg19 BAM，最终交付物一致)",
        description=(
            "从一批 BAM 生成 EIGENSTRAT 三件套 (.geno/.snp/.ind)，\n"
            "用于古 DNA 群体遗传分析 (qpAdm, smartpca, ADMIXTOOLS2)。\n\n"
            "支持两种输入:\n"
            "  • hg38 BAM (默认): 内部自动 liftOver，加 --deliver-hg19 输出 hg19 坐标交付版本\n"
            "  • hg19 BAM (--reference hg19): 直接用 AADR 原版位点，输出即为 hg19 坐标\n\n"
            "两条路线最终交付物完全等价 — 同样的 rsID、同样的 hg19 坐标、同样的 ref/alt，\n"
            "对方拿到后无法区分来源是 hg38 还是 hg19 BAM。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_eig.add_argument("--bam", nargs="+", help="输入 BAM 文件 (可多个)")
    p_eig.add_argument("--bam-list", help="从文件读 BAM 列表 (每行一个路径)")
    p_eig.add_argument("--sample-ids", help="样本 ID 列表，逗号分隔 (默认用 BAM 文件名)")
    p_eig.add_argument("-p", "--population", default="Unknown", help="群体标签 (默认 Unknown)")
    p_eig.add_argument("-o", "--output", default=".", help="输出目录")
    p_eig.add_argument("-n", "--name", default="dataset", help="输出前缀")
    p_eig.add_argument(
        "--reference", default="hg38",
        choices=["hg38", "hg19"],
        help="BAM 参考版本 (默认 hg38)。两种输入最终交付物一致，无需担心差异。",
    )
    p_eig.add_argument(
        "--position-set", default="v42.4.1240K",
        choices=["v42.4.1240K", "v66.2M.aadr"],
        help="位点集 (默认 v42.4.1240K)",
    )
    p_eig.add_argument(
        "--method", default="randomHaploid",
        choices=["randomHaploid", "majorityCall", "randomDiploid"],
        help="pileupCaller 抽取方法 (默认 randomHaploid)",
    )
    p_eig.add_argument("--min-mapq", type=int, default=30, help="最小比对质量 (默认 30)")
    p_eig.add_argument("--min-baseq", type=int, default=30, help="最小碱基质量 (默认 30)")
    p_eig.add_argument("--min-depth", type=int, default=1, help="最小深度 (默认 1)")
    p_eig.add_argument(
        "--skip-transitions", action="store_true",
        help="忽略 C→T/G→A 转换位点 (古 DNA damage 防护)",
    )
    p_eig.add_argument("--seed", type=int, help="随机种子 (randomHaploid 复现用)")
    p_eig.add_argument("--sex", help="样本性别映射: sample1:M,sample2:F (可选)")
    p_eig.add_argument(
        "--deliver-hg19", action="store_true",
        help="[仅 hg38 BAM 需要] 额外输出 hg19 坐标版本用于交付。hg19 BAM 输出本身就是 hg19 坐标。",
    )
    p_eig.add_argument("--aadr-snp", help="AADR hg19 .snp 路径 (用于 --deliver-hg19)")
    p_eig.set_defaults(func=cmd_bam_to_eigenstrat)

    # analyze-y
    p_y = subparsers.add_parser("analyze-y", help="分析 Y 单倍群")
    p_y.add_argument("bam", help="输入 chrY BAM 文件")
    p_y.add_argument("-o", "--output", help="输出目录")
    p_y.add_argument("-s", "--sample", help="样本 ID")
    p_y.add_argument("-q", "--quality", type=int, help="质量阈值 (默认 20)")
    p_y.add_argument("-r", "--reads", type=int, help="最小读取数 (默认 1，古DNA用)")
    p_y.add_argument("-m", "--majority", type=int, help="碱基多数阈值 (默认 90)")
    p_y.add_argument("--reference", default="hg38", choices=["hg38", "hg19", "t2t"], help="参考版本")
    p_y.add_argument("--tree", default="isogg", choices=["isogg", "yfull", "yfull_v10", "ftdna"],
                     help="Y-SNP 树 (默认 isogg)")
    p_y.add_argument("--no-adna", action="store_true", help="关闭古 DNA 模式")
    p_y.set_defaults(func=cmd_analyze_y)
    
    # analyze-mt
    p_mt = subparsers.add_parser("analyze-mt", help="分析 MT 单倍群 (Haplogrep3)")
    p_mt.add_argument("vcf", help="输入 chrM VCF 文件")
    p_mt.add_argument("-o", "--output", help="输出文件")
    p_mt.add_argument("-s", "--sample", help="样本 ID")
    p_mt.set_defaults(func=cmd_analyze_mt)

    # admixture-calc
    p_calc = subparsers.add_parser(
        "admixture-calc",
        help="常染色体祖源计算器 (E11/K13/K36 等 28 个)",
        description="输入芯片格式文件 (extract-chip 产出)，计算祖源成分比例。",
    )
    p_calc.add_argument("chip_file", nargs="?", help="芯片格式文件 (23andMe/Ancestry)")
    p_calc.add_argument("-s", "--sample", help="样本 ID")
    p_calc.add_argument(
        "-c", "--calculators",
        help="计算器列表，逗号分隔 (默认: E11,K12b,K36,globe13)",
    )
    p_calc.add_argument(
        "-v", "--vendor", default="23andme",
        choices=["23andme", "ancestry"],
        help="文件格式 (默认 23andme)",
    )
    p_calc.add_argument("--list-models", action="store_true", help="列出所有可用计算器")
    p_calc.set_defaults(func=cmd_admixture_calc)

    # pca
    p_pca = subparsers.add_parser("pca", help="PCA 主成分分析 (需要参考人群数据)")

    # g25
    p_g25 = subparsers.add_parser("g25", help="G25 坐标距离计算 (找最近人群)")

    # report
    p_report = subparsers.add_parser("report", help="生成 HTML 分析报告")
    p_report.add_argument("-s", "--sample", required=True, help="样本名")
    p_report.add_argument("-o", "--output", default="report.html", help="输出 HTML 文件")
    p_report.add_argument("--y-hg", help="Y 单倍群")
    p_report.add_argument("--y-qc", help="Y QC 分数")
    p_report.add_argument("--mt-hg", help="MT 单倍群")
    p_report.add_argument("--mt-quality", help="MT 质量分数")
    p_report.add_argument("--admix-json", help="祖源计算器结果 JSON 文件")
    p_report.add_argument("--eigen-snps", help="EIGENSTRAT SNP 数")
    p_report.add_argument("--chip-n", help="芯片格式数量")
    p_report.add_argument("--reference", default="hg38", help="参考基因组版本")
    p_report.set_defaults(func=lambda args: _cmd_report(args))
    p_g25.add_argument("--coords", help="25 维坐标，逗号分隔")
    p_g25.add_argument("--file", help="G25 坐标文件 (CSV: name,PC1,...,PC25)")
    p_g25.add_argument("-s", "--sample", help="样本名")
    p_g25.add_argument("--top", type=int, default=20, help="显示前 N 个最近人群 (默认 20)")
    p_g25.set_defaults(func=lambda args: _cmd_g25(args))
    p_pca.add_argument("sample_prefix", help="样本 EIGENSTRAT 前缀")
    p_pca.add_argument("--ref", required=True, help="参考人群 EIGENSTRAT 前缀")
    p_pca.add_argument("-o", "--output", default="pca_out", help="输出目录")
    p_pca.add_argument("-s", "--sample", help="样本 ID")
    p_pca.add_argument("--num-pcs", type=int, default=10, help="主成分数 (默认 10)")
    p_pca.set_defaults(func=lambda args: _cmd_pca(args))

    # full-pipeline
    p_full = subparsers.add_parser(
        "full-pipeline",
        help="一键全流程 (chrY/chrM + 单倍群 + EIGENSTRAT + 芯片 + 计算器)",
    )
    p_full.add_argument("--bam", nargs="+", help="BAM 文件列表")
    p_full.add_argument("--bam-list", help="从文件读 BAM 列表")
    p_full.add_argument("-o", "--output", default="full_output", help="输出目录")
    p_full.add_argument("-p", "--population", default="Unknown", help="群体标签")
    p_full.add_argument("--reference", default="hg38", choices=["hg38", "hg19"])
    p_full.add_argument("--seed", type=int, default=42)
    p_full.set_defaults(func=lambda args: _cmd_full_pipeline(args))

    # vcf-to-chip
    p_vcf = subparsers.add_parser("vcf-to-chip", help="从 VCF 提取芯片格式")
    p_vcf.add_argument("vcf", help="输入 VCF 文件")
    p_vcf.add_argument("-o", "--output", help="输出目录")
    p_vcf.add_argument("-s", "--sample", help="样本 ID")
    p_vcf.add_argument("-r", "--reference", default="hg38", choices=["hg38", "hg19"],
                       help="VCF 坐标系 (默认 hg38，hg19 VCF 请指定 hg19)")
    p_vcf.set_defaults(func=cmd_vcf_to_chip)
    
    # snp-to-chip
    p_snp = subparsers.add_parser("snp-to-chip", help="从 .snp 文件提取芯片格式 (rsID 匹配)")
    p_snp.add_argument("snp", help="输入 .snp 文件")
    p_snp.add_argument("-o", "--output", help="输出目录")
    p_snp.add_argument("-s", "--sample", help="样本 ID")
    p_snp.set_defaults(func=cmd_snp_to_chip)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()
