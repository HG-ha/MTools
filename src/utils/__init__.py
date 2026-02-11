# -*- coding: utf-8 -*-
"""工具函数模块初始化文件。"""

from .file_utils import (
    clean_temp_files,
    copy_file,
    ensure_dir,
    format_file_size,
    get_file_extension,
    get_file_size,
    get_system_fonts,
    get_unique_path,
    list_files_by_extension,
    move_file,
)
from .gif_utils import GifUtils
from .logger import (
    logger,
    debug,
    info,
    warning,
    error,
    critical,
    exception,
    log_print,
    Logger,
)
from .tool_metadata import (
    ToolMetadata,
    get_all_tools,
    get_tool,
    register_tool,
    register_tool_manual,
)
from .network_utils import (
    check_needs_proxy,
    get_proxied_url,
    clear_location_cache,
    get_location_by_ip,
    contains_cjk,
    LocationInfo,
)
from .subtitle_utils import (
    segments_to_srt,
    segments_to_vtt,
    segments_to_txt,
    segments_to_lrc,
)
from .onnx_helper import (
    create_session_options,
    create_provider_options,
    create_onnx_session_config,
    create_onnx_session,
    get_primary_provider,
    get_device_display_name,
    get_session_device_info,
    is_directml_provider,
    parse_onnx_error,
    get_friendly_error_message,
)
from .platform_utils import (
    get_windows_version,
    is_windows,
    is_windows_10_or_later,
    is_windows_11,
    is_macos,
    is_linux,
    supports_file_drop,
    get_gpu_devices,
    get_cuda_devices,
    get_available_compute_devices,
    is_admin,
    request_admin_restart,
)
# 拖放处理器 - 根据平台选择实现
import sys as _sys
if _sys.platform == "win32":
    from .windows_drop import WindowsDropHandler, DropInfo
elif _sys.platform == "darwin":
    from .macos_drop import MacOSDropHandler, DropInfo
# DropInfo 在两个模块中定义一致，始终可用
if _sys.platform not in ("win32", "darwin"):
    from .windows_drop import DropInfo  # 仅导入数据类

__all__ = [
    "ensure_dir",
    "get_file_size",
    "format_file_size",
    "clean_temp_files",
    "copy_file",
    "move_file",
    "get_file_extension",
    "get_system_fonts",
    "get_unique_path",
    "list_files_by_extension",
    "GifUtils",
    "logger",
    "Logger",
    "debug",
    "info",
    "warning",
    "error",
    "critical",
    "exception",
    "log_print",
    "ToolMetadata",
    "register_tool",
    "register_tool_manual",
    "get_all_tools",
    "get_tool",
    "check_needs_proxy",
    "get_proxied_url",
    "clear_location_cache",
    "get_location_by_ip",
    "contains_cjk",
    "LocationInfo",
    "segments_to_srt",
    "segments_to_vtt",
    "segments_to_txt",
    "segments_to_lrc",
    "create_session_options",
    "create_provider_options",
    "create_onnx_session_config",
    "create_onnx_session",
    "get_primary_provider",
    "get_device_display_name",
    "get_session_device_info",
    "is_directml_provider",
    "parse_onnx_error",
    "get_friendly_error_message",
    "get_windows_version",
    "is_windows",
    "is_windows_10_or_later",
    "is_windows_11",
    "is_macos",
    "is_linux",
    "supports_file_drop",
    "get_gpu_devices",
    "get_cuda_devices",
    "get_available_compute_devices",
    "is_admin",
    "request_admin_restart",
    "DropInfo",
]

