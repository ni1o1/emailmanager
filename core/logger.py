"""
统一日志系统

使用方法:
    from core.logger import get_logger

    logger = get_logger(__name__)
    logger.info("处理邮件...")
    logger.error("发生错误", exc_info=True)
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime

# 日志目录
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 日志级别（可通过环境变量配置）
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# 日志格式
CONSOLE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
FILE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 全局配置标志
_configured = False


def setup_logging():
    """配置根日志记录器"""
    global _configured
    if _configured:
        return

    root_logger = logging.getLogger("emailmanager")
    root_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # 避免重复添加 handler
    if root_logger.handlers:
        return

    # 控制台 Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT, DATE_FORMAT))
    root_logger.addHandler(console_handler)

    # 文件 Handler（主日志，轮转）
    main_log_file = LOG_DIR / "emailmanager.log"
    file_handler = RotatingFileHandler(
        main_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(FILE_FORMAT, DATE_FORMAT))
    root_logger.addHandler(file_handler)

    # 错误日志（单独文件，便于监控）
    error_log_file = LOG_DIR / "errors.log"
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(FILE_FORMAT, DATE_FORMAT))
    root_logger.addHandler(error_handler)

    _configured = True

    root_logger.info(f"日志系统初始化完成 (级别: {LOG_LEVEL}, 目录: {LOG_DIR})")


def get_logger(name: str) -> logging.Logger:
    """
    获取模块日志记录器

    Args:
        name: 模块名称，通常使用 __name__

    Returns:
        Logger 实例
    """
    setup_logging()

    # 统一使用 emailmanager 作为根命名空间
    if not name.startswith("emailmanager"):
        # 转换模块名: config.settings -> emailmanager.config.settings
        name = f"emailmanager.{name}"

    return logging.getLogger(name)


class LogContext:
    """
    日志上下文管理器，用于记录操作耗时

    使用方法:
        with LogContext(logger, "处理邮件"):
            process_emails()
        # 自动输出: 处理邮件 完成 (耗时 1.23s)
    """

    def __init__(self, logger: logging.Logger, operation: str, level: int = logging.INFO):
        self.logger = logger
        self.operation = operation
        self.level = level
        self.start_time = None

    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.log(self.level, f"{self.operation} 开始...")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()
        if exc_type is not None:
            self.logger.error(f"{self.operation} 失败 (耗时 {duration:.2f}s): {exc_val}")
        else:
            self.logger.log(self.level, f"{self.operation} 完成 (耗时 {duration:.2f}s)")
        return False


def mask_sensitive(text: str) -> str:
    """
    脱敏敏感信息，用于日志输出

    Args:
        text: 可能包含敏感信息的文本

    Returns:
        脱敏后的文本
    """
    import re

    if not text:
        return text

    # 脱敏邮箱地址
    text = re.sub(r"([\w.+-]+)@([\w.-]+)", r"\1[at]\2", text)

    # 脱敏 API Key (sk-xxx, key-xxx 等)
    text = re.sub(r"(sk-|key-|token-)[a-zA-Z0-9]{8,}", r"\1***", text)

    # 脱敏手机号
    text = re.sub(r"(\+?86)?1[3-9]\d{9}", "***手机号***", text)

    return text
