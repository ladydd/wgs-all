"""
日志模块 - 结构化日志配置
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

from .config import settings


def setup_logging(component: str = "app") -> logging.Logger:
    """
    配置日志
    
    Args:
        component: 组件名称，用于日志文件命名
    
    Returns:
        配置好的 logger 实例
    """
    # 创建日志目录
    log_dir = settings.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 日志文件按日期命名
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"{component}_{today}.log"
    
    # 日志格式
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # 配置 root logger
    logger = logging.getLogger(component)
    logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)
    
    # 清除已有 handlers
    logger.handlers.clear()
    
    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    logger.addHandler(console_handler)
    
    # 文件输出
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))
    logger.addHandler(file_handler)
    
    return logger


# 默认 logger
logger = setup_logging("wgs-platform")
