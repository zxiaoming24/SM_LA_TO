"""
日志工具模块
提供统一的日志配置和管理
"""

import logging
import sys
from typing import Optional
import os
from datetime import datetime

# 全局日志管理器
_loggers = {}

# 获取当前脚本所在目录
script_dir = os.path.dirname(os.path.abspath(__file__))

# 默认日志配置
DEFAULT_LOG_CONFIG = {
    "level": logging.INFO,  # 默认日志级别
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "handlers": [
        {"type": "stream"},
        {
            "type": "file",
            "filename": f'{script_dir}/log/run_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',  # 每次运行生成新的日志文件
            "level": logging.DEBUG,  # 文件记录更详细的日志
        },
    ],
}


def get_logger(
    name: Optional[str] = None, config: Optional[dict] = None
) -> logging.Logger:
    """
    获取配置好的日志记录器

    Args:
        name: 日志记录器名称，为None时返回根记录器
        config: 日志配置，为None时使用配置文件的配置

    Returns:
        配置好的日志记录器
    """
    # 获取日志配置
    log_config = config or DEFAULT_LOG_CONFIG

    # 处理None情况或是否已经配置过
    if name is None:
        # 根记录器 - 不要返回，继续配置
        logger = logging.getLogger()
        # 根记录器需要特殊标识
        key = "<root>"
    else:
        key = name
        # 如果已经创建过该logger，直接返回
        if key in _loggers:
            return _loggers[key]
        logger = logging.getLogger(name)

    logger.setLevel(log_config["level"])

    # 清除已有的handler，避免重复
    logger.handlers.clear()

    # 根记录器特殊处理 - 不要禁用它，确保forward compatibility
    if name is None:
        # 根记录器 - 也不要禁用它
        logger.propagate = True  # 根记录器应该传播
    else:
        # 子记录器 - 防止重复传播
        logger.propagate = False

    # 创建formatter
    formatter = logging.Formatter(log_config["format"])

    # 添加handler
    for handler_config in log_config.get("handlers", []):
        if handler_config["type"] == "stream":
            # 控制台输出
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        elif handler_config["type"] == "file":
            # 文件输出
            from logging.handlers import RotatingFileHandler

            handler = RotatingFileHandler(
                handler_config["filename"],
                maxBytes=handler_config.get("max_bytes", 10 * 1024 * 1024),  # 10MB 默认
                backupCount=handler_config.get("backup_count", 5),
                encoding="utf-8",
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

    # 保存logger实例
    _loggers[key] = logger

    return logger


def setup_module_logger(module_name: str) -> logging.Logger:
    """
    为指定模块设置日志记录器

    Args:
        module_name: 模块名称

    Returns:
        配置好的日志记录器
    """
    return get_logger(module_name)


# 便捷的日志级别函数
def debug(message: str, module: Optional[str] = None):
    """输出debug级别日志"""
    get_logger(module).debug(message)


def info(message: str, module: Optional[str] = None):
    """输出info级别日志"""
    get_logger(module).info(message)


def warning(message: str, module: Optional[str] = None):
    """输出warning级别日志"""
    get_logger(module).warning(message)


def error(message: str, module: Optional[str] = None):
    """输出error级别日志"""
    get_logger(module).error(message)


def critical(message: str, module: Optional[str] = None):
    """输出critical级别日志"""
    get_logger(module).critical(message)
