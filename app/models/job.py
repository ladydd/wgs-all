"""
作业数据模型
"""

from enum import Enum
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid


class JobState(str, Enum):
    """作业状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InputType(str, Enum):
    """输入类型"""
    FASTQ = "fastq"  # FASTQ 文件，需要比对
    BAM = "bam"  # BAM 文件，直接分析


class AnalysisType(str, Enum):
    """分析类型"""
    CHIP_FORMAT = "chip_format"        # 芯片格式导出
    K1240 = "1240k"                    # 1240K 位点
    Y_HAPLOGROUP = "y_haplogroup"      # Y 单倍群
    MT_HAPLOGROUP = "mt_haplogroup"    # MT 单倍群
    EXTRACT_CHRY = "extract_chrY"      # 提取 chrY
    EXTRACT_CHRM = "extract_chrM"      # 提取 chrM
    EIGENSTRAT = "eigenstrat"          # EIGENSTRAT 数据集 (古 DNA 交付格式)
    PCA = "pca"                        # PCA 主成分分析
    ADMIXTURE = "admixture"            # ADMIXTURE 祖源成分
    G25 = "g25"                        # G25 坐标计算
    QPADM = "qpadm"                   # qpAdm 祖源建模


class JobCreate(BaseModel):
    """创建作业请求"""
    sample_id: str = Field(..., description="样本 ID")
    input_type: InputType = Field(..., description="输入类型")
    input_files: List[str] = Field(..., description="输入文件路径")
    analyses: List[AnalysisType] = Field(..., description="要执行的分析")
    reference: str = Field(default="hg38", description="参考基因组版本")


class JobStatus(BaseModel):
    """作业状态"""
    job_id: str
    sample_id: str
    state: JobState
    progress: int = Field(default=0, ge=0, le=100)
    current_step: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class JobResult(BaseModel):
    """作业结果"""
    job_id: str
    sample_id: str
    state: JobState
    files: Dict[str, str] = Field(default_factory=dict)
    statistics: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    completed_at: Optional[datetime] = None


class BamDetectRequest(BaseModel):
    """BAM 检测请求"""
    bam_path: str = Field(..., description="BAM 文件路径")


class BamDetectResponse(BaseModel):
    """BAM 检测结果"""
    file_path: str
    reference_version: str
    reference_display: str
    system_version: str  # 映射到系统版本 (hg38/hg19/t2t)
    has_chr_prefix: bool
    chr1_length: int
    mt_name: str
    confidence: str


class Job(BaseModel):
    """作业完整信息"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sample_id: str
    input_type: InputType
    input_files: List[str]
    analyses: List[AnalysisType]
    reference: str = "hg38"

    state: JobState = JobState.PENDING
    progress: int = 0
    current_step: Optional[str] = None
    error: Optional[str] = None

    files: Dict[str, str] = Field(default_factory=dict)
    statistics: Dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_status(self) -> JobStatus:
        return JobStatus(
            job_id=self.id,
            sample_id=self.sample_id,
            state=self.state,
            progress=self.progress,
            current_step=self.current_step,
            error=self.error,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
        )

    def to_result(self) -> JobResult:
        return JobResult(
            job_id=self.id,
            sample_id=self.sample_id,
            state=self.state,
            files=self.files,
            statistics=self.statistics,
            created_at=self.created_at,
            completed_at=self.completed_at,
        )
