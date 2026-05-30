"""
配置模块 - 使用 pydantic-settings 管理配置
支持环境变量覆盖，自动检测系统资源
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_system_memory_gb() -> int:
    """获取系统总内存 (GB)"""
    try:
        # Linux
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if line.startswith('MemTotal:'):
                    kb = int(line.split()[1])
                    return kb // (1024 * 1024)
    except FileNotFoundError:
        pass
    try:
        # macOS / 通用
        import shutil
        total, _, _ = shutil.disk_usage("/")
        import psutil
        return int(psutil.virtual_memory().total / (1024**3))
    except ImportError:
        pass
    try:
        # macOS fallback
        import subprocess
        result = subprocess.run(['sysctl', '-n', 'hw.memsize'], capture_output=True, text=True)
        if result.returncode == 0:
            return int(result.stdout.strip()) // (1024**3)
    except:
        pass
    return 16  # 默认 16GB


def get_cpu_count() -> int:
    """获取 CPU 核心数"""
    try:
        return os.cpu_count() or 4
    except:
        return 4


class Settings(BaseSettings):
    """应用配置"""
    
    model_config = SettingsConfigDict(
        env_prefix="WGS_",  # 环境变量前缀: WGS_THREADS, WGS_MEMORY_GB 等
        env_file=".env",
        env_file_encoding="utf-8",
    )
    
    # 基础配置
    app_name: str = "WGS Analysis Platform"
    debug: bool = False
    
    # 资源限制 (0 表示自动检测)
    threads: int = 0  # BWA/samtools 线程数，0=自动
    memory_gb: int = 0  # 内存限制 (GB)，0=自动
    
    # 路径配置 (Docker 内默认路径，可通过环境变量覆盖)
    reference_dir: Path = Path("/reference")  # 参考文件目录
    data_dir: Path = Path("/data")  # 数据目录
    log_dir: Path = Path("logs")  # 日志目录
    
    # API 配置
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    
    @property
    def effective_threads(self) -> int:
        """实际使用的线程数"""
        if self.threads > 0:
            return self.threads
        # 自动: CPU 核心数 - 2，最少 2
        return max(2, get_cpu_count() - 2)
    
    @property
    def effective_memory_gb(self) -> int:
        """实际使用的内存 (GB)"""
        if self.memory_gb > 0:
            return self.memory_gb
        # 自动: 系统内存的 70%
        return max(8, int(get_system_memory_gb() * 0.7))
    
    @property
    def sort_memory_per_thread(self) -> str:
        """samtools sort 每线程内存"""
        # 预留 10GB 给 BWA，剩余分给 sort
        available = self.effective_memory_gb - 10
        per_thread = max(1, available // self.effective_threads)
        return f"{per_thread}G"
    
    @property
    def genomes_dir(self) -> Path:
        """参考基因组目录"""
        return self.reference_dir / "genomes"
    
    @property
    def microarray_dir(self) -> Path:
        """芯片模板目录"""
        return self.reference_dir / "microarray"
    
    # yleaf 路径 (Docker 内置 /app/yleaf，本地可覆盖)
    yleaf_path: Path = Path("")
    
    @property
    def yleaf_dir(self) -> Path:
        """yleaf 工具目录"""
        if self.yleaf_path and self.yleaf_path != Path(""):
            return self.yleaf_path
        # Docker 内置路径
        docker_path = Path("/app/yleaf")
        if docker_path.exists():
            return docker_path
        # 本地 reference 目录
        return self.reference_dir / "yleaf"
    
    def get_resource_info(self) -> dict:
        """获取资源配置信息"""
        return {
            "system_memory_gb": get_system_memory_gb(),
            "system_cpus": get_cpu_count(),
            "effective_threads": self.effective_threads,
            "effective_memory_gb": self.effective_memory_gb,
            "sort_memory_per_thread": self.sort_memory_per_thread,
        }


# 全局配置实例
settings = Settings()
