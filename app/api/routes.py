"""
API 路由
"""

import os
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from ..models.job import (
    Job, JobCreate, JobStatus, JobResult,
    JobState, AnalysisType, InputType,
    BamDetectRequest, BamDetectResponse,
)
from ..core.config import settings
from ..core.logging import logger
from ..core.reference import reference_manager
from ..core.bam_detector import detect_bam_reference, map_to_system_version
from ..core.resource_planner import (
    estimate_sample, detect_machine_resources, plan_alignment, plan_batch,
)

# 简单的内存存储 (生产环境应该用 Redis)
jobs_db: dict[str, Job] = {}

router = APIRouter()


# ============ 作业管理 ============

@router.post("/jobs", response_model=JobStatus, summary="提交分析作业")
async def create_job(request: JobCreate, background_tasks: BackgroundTasks):
    """
    提交新的分析作业

    - **sample_id**: 样本 ID
    - **input_type**: 输入类型 (fastq/bam)
    - **input_files**: 输入文件路径列表
    - **analyses**: 要执行的分析类型列表
    - **reference**: 参考基因组版本 (默认 hg38, 可选 hg19/t2t)
    """
    # 验证输入文件
    for f in request.input_files:
        if not os.path.exists(f):
            raise HTTPException(status_code=400, detail=f"文件不存在: {f}")

    # BAM 输入时自动检测参考基因组
    reference = request.reference
    detected_ref = None
    if request.input_type == InputType.BAM:
        try:
            bam_info = detect_bam_reference(request.input_files[0])
            detected_ref = map_to_system_version(bam_info)
            if reference != detected_ref:
                logger.info(
                    f"BAM 自动检测参考系: {detected_ref} "
                    f"(用户选择: {reference}, 以检测结果为准)"
                )
                reference = detected_ref
        except Exception as e:
            logger.warning(f"BAM 参考系检测失败: {e}, 使用用户选择: {reference}")

    # 验证参考基因组版本
    if reference not in reference_manager.SUPPORTED_VERSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的参考基因组: {reference}, "
                   f"支持: {reference_manager.SUPPORTED_VERSIONS}"
        )

    # 创建作业
    job = Job(
        sample_id=request.sample_id,
        input_type=request.input_type,
        input_files=request.input_files,
        analyses=request.analyses,
        reference=reference,
    )

    # 记录检测信息
    if detected_ref:
        job.statistics["bam_detected_reference"] = detected_ref

    jobs_db[job.id] = job
    logger.info(f"创建作业: {job.id}, 样本: {job.sample_id}, 参考系: {reference}")

    # 后台执行
    background_tasks.add_task(run_job, job.id)

    return job.to_status()


@router.get("/jobs", response_model=List[JobStatus], summary="列出所有作业")
async def list_jobs():
    """列出所有作业"""
    return [job.to_status() for job in jobs_db.values()]


@router.get("/jobs/{job_id}", response_model=JobStatus, summary="获取作业状态")
async def get_job_status(job_id: str):
    """获取指定作业的状态"""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="作业不存在")
    return jobs_db[job_id].to_status()


@router.get("/jobs/{job_id}/result", response_model=JobResult, summary="获取作业结果")
async def get_job_result(job_id: str):
    """获取作业结果"""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="作业不存在")

    job = jobs_db[job_id]
    if job.state not in [JobState.COMPLETED, JobState.FAILED]:
        raise HTTPException(status_code=400, detail="作业尚未完成")

    return job.to_result()


@router.delete("/jobs/{job_id}", summary="取消作业")
async def cancel_job(job_id: str):
    """取消作业"""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="作业不存在")

    job = jobs_db[job_id]
    if job.state == JobState.RUNNING:
        job.state = JobState.CANCELLED
        logger.info(f"取消作业: {job_id}")

    return {"message": "作业已取消", "job_id": job_id}


# ============ BAM 检测 ============

@router.post("/bam/detect", response_model=BamDetectResponse, summary="检测 BAM 参考基因组")
async def detect_bam(request: BamDetectRequest):
    """
    自动检测 BAM 文件的参考基因组版本

    通过读取 BAM header 中的染色体长度信息精确匹配
    """
    if not os.path.exists(request.bam_path):
        raise HTTPException(status_code=400, detail=f"文件不存在: {request.bam_path}")

    try:
        bam_info = detect_bam_reference(request.bam_path)
        system_version = map_to_system_version(bam_info) if bam_info.confidence == "high" else "unknown"
        return BamDetectResponse(
            file_path=bam_info.file_path,
            reference_version=bam_info.reference_version,
            reference_display=bam_info.reference_display,
            system_version=system_version,
            has_chr_prefix=bam_info.has_chr_prefix,
            chr1_length=bam_info.chr1_length,
            mt_name=bam_info.mt_name,
            confidence=bam_info.confidence,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检测失败: {str(e)}")


# ============ 参考数据 ============

@router.get("/references", summary="列出可用参考基因组")
async def list_references():
    """列出可用的参考基因组版本及其文件状态"""
    return reference_manager.get_readiness_summary()


@router.get("/system", summary="系统资源信息")
async def get_system_info():
    """获取系统资源配置"""
    return settings.get_resource_info()


# ============ 文件下载 ============

@router.get("/files/{job_id}/{file_type}", summary="下载结果文件")
async def download_file(job_id: str, file_type: str):
    """下载作业结果文件"""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="作业不存在")

    job = jobs_db[job_id]
    if file_type not in job.files:
        raise HTTPException(status_code=404, detail=f"文件类型不存在: {file_type}")

    file_path = job.files[file_type]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(
        file_path,
        filename=os.path.basename(file_path),
        media_type="application/octet-stream",
    )


# ============ 后台任务 ============

async def run_job(job_id: str):
    """执行作业 (后台任务)"""
    job = jobs_db.get(job_id)
    if not job:
        return

    try:
        job.state = JobState.RUNNING
        job.started_at = datetime.now()
        logger.info(f"开始执行作业: {job_id}")

        # 确定输出目录
        output_dir = settings.data_dir / job.sample_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # 获取 BAM 文件
        if job.input_type == InputType.FASTQ:
            job.current_step = "比对"
            job.progress = 10
            bam_file = await run_alignment(job, output_dir)
        else:
            bam_file = job.input_files[0]

        job.files["bam"] = bam_file

        # 执行各项分析
        total_analyses = len(job.analyses)
        for i, analysis in enumerate(job.analyses):
            if job.state == JobState.CANCELLED:
                break

            job.current_step = analysis.value
            job.progress = 20 + int(70 * i / total_analyses)

            await run_analysis(job, analysis, bam_file, output_dir)

        job.state = JobState.COMPLETED
        job.progress = 100
        job.completed_at = datetime.now()
        logger.info(f"作业完成: {job_id}")

    except Exception as e:
        job.state = JobState.FAILED
        job.error = str(e)
        job.completed_at = datetime.now()
        logger.error(f"作业失败: {job_id}, 错误: {e}")


async def run_alignment(job: Job, output_dir: Path) -> str:
    """执行比对"""
    from ..pipeline.alignment import AlignmentModule

    aligner = AlignmentModule(reference=job.reference)
    result = aligner.align(
        job.input_files[0],
        job.input_files[1],
        str(output_dir),
        job.sample_id,
    )

    job.statistics["alignment"] = {
        "total_reads": result.total_reads,
        "mapped_reads": result.mapped_reads,
        "mapping_rate": result.mapping_rate,
    }

    return result.bam_file


async def run_analysis(job: Job, analysis: AnalysisType, bam_file: str, output_dir: Path):
    """执行单项分析"""

    if analysis == AnalysisType.EXTRACT_CHRY:
        from ..pipeline.alignment import ChromosomeExtractor
        extractor = ChromosomeExtractor(reference=job.reference)
        result = extractor.extract(bam_file, "chrY", str(output_dir), job.sample_id)
        job.files["chrY_bam"] = result.bam_file
        job.files["chrY_vcf"] = result.vcf_file
        job.statistics["chrY"] = {"coverage": result.coverage, "snp_count": result.snp_count}

    elif analysis == AnalysisType.EXTRACT_CHRM:
        from ..pipeline.alignment import ChromosomeExtractor
        extractor = ChromosomeExtractor(reference=job.reference)
        result = extractor.extract(bam_file, "chrM", str(output_dir), job.sample_id)
        job.files["chrM_bam"] = result.bam_file
        job.files["chrM_vcf"] = result.vcf_file
        job.statistics["chrM"] = {"coverage": result.coverage, "snp_count": result.snp_count}

    elif analysis == AnalysisType.CHIP_FORMAT:
        from ..pipeline.extraction import ChipFormatExtractor
        extractor = ChipFormatExtractor()
        chip_dir = output_dir / f"{job.sample_id}_chip_formats"
        results = extractor.extract(bam_file, str(chip_dir), job.sample_id)
        job.files["chip_formats"] = str(chip_dir)
        job.statistics["chip_formats"] = [
            {"format": r.format_type, "genotype_rate": r.genotype_rate}
            for r in results
        ]

    elif analysis == AnalysisType.K1240:
        from ..pipeline.extraction import K1240Extractor
        extractor = K1240Extractor()
        output_file = str(output_dir / f"{job.sample_id}_1240K.txt")
        result = extractor.extract(bam_file, output_file)
        job.files["1240k"] = result.file_path
        job.statistics["1240k"] = {
            "total_positions": result.total_positions,
            "genotype_rate": result.genotype_rate,
        }

    elif analysis == AnalysisType.Y_HAPLOGROUP:
        from ..pipeline.haplogroup import YHaplogroupAnalyzer
        analyzer = YHaplogroupAnalyzer()
        yleaf_dir = output_dir / f"{job.sample_id}_yleaf"
        result = analyzer.analyze(bam_file, str(yleaf_dir), job.sample_id)
        job.files["y_haplogroup"] = result.output_dir
        job.statistics["y_haplogroup"] = {
            "haplogroup": result.haplogroup,
            "confidence": result.confidence,
            "markers_used": result.markers_used,
        }

    elif analysis == AnalysisType.EIGENSTRAT:
        # EIGENSTRAT 批量提取。
        # 约定: job.input_files 是 BAM 列表 (可以多个，都需是 hg38)
        #       job.sample_id 用作输出前缀 (数据集名)
        #       job.statistics["eigenstrat"]["population"] 可选指定群体标签
        from ..pipeline.eigenstrat import EigenstratExtractor

        if job.reference != "hg38":
            logger.warning(f"EIGENSTRAT 当前只支持 hg38 BAM，跳过 (当前: {job.reference})")
            job.statistics["eigenstrat"] = {"status": "skipped", "reason": "not hg38"}
            return

        eigen_cfg = job.statistics.get("eigenstrat_config", {})
        population = eigen_cfg.get("population", "Unknown")
        position_set = eigen_cfg.get("position_set", "v42.4.1240K")
        deliver_hg19 = eigen_cfg.get("deliver_hg19", False)

        extractor = EigenstratExtractor()
        eigen_dir = output_dir / f"{job.sample_id}_eigenstrat"
        result = extractor.extract(
            bam_files=job.input_files,
            sample_ids=[Path(b).stem for b in job.input_files],
            population=population,
            output_dir=str(eigen_dir),
            output_name=job.sample_id,
            position_set=position_set,
        )
        job.files["eigenstrat_geno"] = result.geno_file
        job.files["eigenstrat_snp"] = result.snp_file
        job.files["eigenstrat_ind"] = result.ind_file
        job.statistics["eigenstrat"] = {
            "total_snps": result.total_snps,
            "sample_count": len(result.sample_ids),
            "population": result.population,
            "position_set": result.position_set,
            "coord_system": result.coord_system,
        }

        if deliver_hg19:
            from ..pipeline.eigenstrat import HgCoordRewriter
            aadr_snp = (
                Path(__file__).parent.parent.parent
                / "adna_to_dataset" / "positions" / f"{position_set}.snp"
            )
            rewriter = HgCoordRewriter()
            out = rewriter.rewrite_to_hg19(
                eigenstrat_prefix=result.output_prefix,
                aadr_hg19_snp=str(aadr_snp),
                output_prefix=str(eigen_dir / f"{job.sample_id}.hg19"),
            )
            job.files["eigenstrat_hg19_geno"] = out["geno"]
            job.files["eigenstrat_hg19_snp"] = out["snp"]
            job.files["eigenstrat_hg19_ind"] = out["ind"]
            job.statistics["eigenstrat"]["hg19_delivered"] = {
                "kept": out["kept"],
                "dropped": out["dropped"],
            }

    elif analysis in (
        AnalysisType.PCA, AnalysisType.ADMIXTURE,
        AnalysisType.G25, AnalysisType.QPADM,
    ):
        # 群体分析需要先有 1240K 数据
        k1240_file = job.files.get("1240k")
        if not k1240_file:
            logger.warning(f"群体分析需要先提取 1240K 数据，跳过 {analysis.value}")
            return

        from ..pipeline.population import PopulationAnalyzer
        pop_analyzer = PopulationAnalyzer(reference_version=job.reference)
        pop_dir = output_dir / f"{job.sample_id}_population"

        try:
            results = pop_analyzer.full_analysis(
                input_file=k1240_file,
                input_type="1240k",
                output_dir=str(pop_dir),
                sample_id=job.sample_id,
                analyses=[analysis.value],
            )
            job.files[f"population_{analysis.value}"] = str(pop_dir)
            job.statistics[analysis.value] = _serialize_population_result(analysis.value, results)
        except NotImplementedError:
            logger.warning(f"{analysis.value} 尚未实现")
            job.statistics[analysis.value] = {"status": "not_implemented"}


def _serialize_population_result(analysis_type: str, results: dict) -> dict:
    """将群体分析结果序列化为可 JSON 的格式"""
    if analysis_type == "pca" and "pca" in results:
        r = results["pca"]
        return {
            "pc1": r.pc1,
            "pc2": r.pc2,
            "nearest_populations": r.nearest_populations[:5],
        }
    elif analysis_type == "admixture" and "admixture" in results:
        return {
            calc: {"components": r.components, "cv_error": r.cv_error}
            for calc, r in results["admixture"].items()
        }
    elif analysis_type == "g25" and "g25" in results:
        r = results["g25"]
        return {
            "coordinates": r.coordinates,
            "nearest_ancient": r.nearest_ancient[:5],
            "nearest_modern": r.nearest_modern[:5],
        }
    elif analysis_type == "qpadm" and "qpadm" in results:
        r = results["qpadm"]
        return {
            "sources": r.sources,
            "proportions": r.proportions,
            "p_value": r.p_value,
            "feasible": r.feasible,
        }
    return results
