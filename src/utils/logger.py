# -*- coding: utf-8 -*-
"""
日志工具模块

提供统一的日志记录功能，支持：
- 多级别日志（DEBUG, INFO, WARNING, ERROR, CRITICAL）
- 彩色控制台输出
- 文件日志保存
- 自动调用位置追踪
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
import os


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器（仅在控制台输出时使用）"""
    
    # ANSI 颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
        'RESET': '\033[0m',       # 重置
    }
    
    def format(self, record):
        """格式化日志记录"""
        # 添加颜色
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        
        # 格式化消息
        result = super().format(record)
        
        # 重置 levelname 以避免影响其他 handler
        record.levelname = levelname
        
        return result


class Logger:
    """日志记录器类"""
    
    _instance: Optional['Logger'] = None
    _logger: Optional[logging.Logger] = None
    _file_handler: Optional[logging.FileHandler] = None
    _error_handler: Optional[logging.FileHandler] = None
    _file_logging_enabled: bool = False
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化日志记录器"""
        if self._logger is not None:
            return
        
        # 创建日志记录器
        self._logger = logging.getLogger('mytools')
        self._logger.setLevel(logging.DEBUG)
        
        # 避免重复添加处理器
        if self._logger.handlers:
            return
        
        # 控制台处理器（彩色输出）- 始终启用
        # 打包后的 GUI 应用没有控制台，stdout/stderr 可能为 None
        stream = sys.stdout
        if stream is None:
            stream = sys.stderr
        if stream is None:
            stream = open(os.devnull, 'w', encoding='utf-8')

        console_handler = logging.StreamHandler(stream)
        console_handler.setLevel(logging.DEBUG)
        console_formatter = ColoredFormatter(
            '%(levelname)s | %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        if hasattr(console_handler, 'stream') and hasattr(console_handler.stream, 'reconfigure'):
            try:
                console_handler.stream.reconfigure(encoding='utf-8')
            except Exception:
                pass
        self._logger.addHandler(console_handler)
        
        # 文件处理器默认不创建，需要调用 enable_file_logging() 启用
    
    def enable_file_logging(self):
        """启用文件日志"""
        if self._file_logging_enabled:
            return
        
        # 创建日志目录
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        # 文件格式化器
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 文件处理器（详细日志）
        log_file = log_dir / f"mytools_{datetime.now().strftime('%Y%m%d')}.log"
        self._file_handler = logging.FileHandler(log_file, encoding='utf-8')
        self._file_handler.setLevel(logging.DEBUG)
        self._file_handler.setFormatter(file_formatter)
        self._logger.addHandler(self._file_handler)
        
        # 错误日志文件处理器
        error_log_file = log_dir / f"mytools_error_{datetime.now().strftime('%Y%m%d')}.log"
        self._error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
        self._error_handler.setLevel(logging.ERROR)
        self._error_handler.setFormatter(file_formatter)
        self._logger.addHandler(self._error_handler)
        
        self._file_logging_enabled = True
        self.info("文件日志已启用")
    
    def disable_file_logging(self):
        """禁用文件日志"""
        if not self._file_logging_enabled:
            return
        
        # 移除文件处理器
        if self._file_handler:
            self._file_handler.close()
            self._logger.removeHandler(self._file_handler)
            self._file_handler = None
        
        if self._error_handler:
            self._error_handler.close()
            self._logger.removeHandler(self._error_handler)
            self._error_handler = None
        
        self._file_logging_enabled = False
        self.info("文件日志已禁用")
    
    def is_file_logging_enabled(self) -> bool:
        """检查文件日志是否启用"""
        return self._file_logging_enabled
    
    def debug(self, message: str, *args, **kwargs):
        """调试级别日志"""
        self._logger.debug(message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """信息级别日志"""
        self._logger.info(message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """警告级别日志"""
        self._logger.warning(message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """错误级别日志"""
        self._logger.error(message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """严重错误级别日志"""
        self._logger.critical(message, *args, **kwargs)
    
    def exception(self, message: str, *args, **kwargs):
        """记录异常信息（包含堆栈跟踪）"""
        self._logger.exception(message, *args, **kwargs)
    
    def set_level(self, level: int):
        """设置日志级别
        
        Args:
            level: 日志级别 (logging.DEBUG, logging.INFO, etc.)
        """
        self._logger.setLevel(level)


# 创建全局日志记录器实例
logger = Logger()


# 便捷函数
def debug(message: str, *args, **kwargs):
    """调试日志"""
    logger.debug(message, *args, **kwargs)


def info(message: str, *args, **kwargs):
    """信息日志"""
    logger.info(message, *args, **kwargs)


def warning(message: str, *args, **kwargs):
    """警告日志"""
    logger.warning(message, *args, **kwargs)


def error(message: str, *args, **kwargs):
    """错误日志"""
    logger.error(message, *args, **kwargs)


def critical(message: str, *args, **kwargs):
    """严重错误日志"""
    logger.critical(message, *args, **kwargs)


def exception(message: str, *args, **kwargs):
    """异常日志（包含堆栈）"""
    logger.exception(message, *args, **kwargs)


# 兼容性函数：替代 print
def log_print(*args, sep=' ', end='\n', **kwargs):
    """兼容 print 的日志函数
    
    用于替换项目中的 print 语句
    """
    message = sep.join(str(arg) for arg in args)
    logger.info(message)


if __name__ == '__main__':
    # 测试日志功能
    debug("这是调试信息")
    info("这是普通信息")
    warning("这是警告信息")
    error("这是错误信息")
    critical("这是严重错误")
    
    try:
        1 / 0
    except Exception:
        exception("捕获到异常")

