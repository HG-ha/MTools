# -*- coding: utf-8 -*-
"""平台相关工具函数。"""

import sys
import subprocess
from typing import Tuple, List, Dict, Optional


def get_windows_version() -> Tuple[int, int, int]:
    """获取 Windows 版本号。
    
    Returns:
        (major, minor, build) 版本号元组，非 Windows 返回 (0, 0, 0)
    """
    if sys.platform != "win32":
        return (0, 0, 0)
    
    try:
        version = sys.getwindowsversion()
        return (version.major, version.minor, version.build)
    except Exception:
        return (0, 0, 0)


def is_windows() -> bool:
    """检查是否为 Windows 系统。"""
    return sys.platform == "win32"


def is_windows_10_or_later() -> bool:
    """检查是否为 Windows 10 或更高版本。
    
    Windows 10 和 Windows 11 的 major 版本号都是 10。
    """
    if not is_windows():
        return False
    
    major, _, _ = get_windows_version()
    return major >= 10


def is_windows_11() -> bool:
    """检查是否为 Windows 11。
    
    Windows 11 的版本号为 10.0.22000 及以上。
    """
    if not is_windows():
        return False
    
    major, _, build = get_windows_version()
    return major >= 10 and build >= 22000


def is_macos() -> bool:
    """检查是否为 macOS 系统。"""
    return sys.platform == "darwin"


def is_linux() -> bool:
    """检查是否为 Linux 系统。"""
    return sys.platform.startswith("linux")


def supports_file_drop() -> bool:
    """检查当前系统是否支持文件拖放功能。
    
    目前只支持 Windows 10/11。
    """
    return is_windows_10_or_later()


def get_gpu_devices() -> List[Dict[str, str]]:
    """获取系统中所有 GPU 设备信息。
    
    跨平台支持 Windows、macOS、Linux。
    
    Returns:
        GPU 设备列表，每个设备包含:
        - index: 设备索引
        - name: 设备名称
        - vendor: 厂商（NVIDIA/AMD/Intel/Apple 等）
    """
    gpus = []
    
    if is_windows():
        gpus = _get_gpu_devices_windows()
    elif is_macos():
        gpus = _get_gpu_devices_macos()
    elif is_linux():
        gpus = _get_gpu_devices_linux()
    
    return gpus if gpus else [{"index": 0, "name": "Unknown GPU", "vendor": "Unknown"}]


def _get_gpu_devices_windows() -> List[Dict[str, str]]:
    """Windows 平台获取 GPU 设备信息。"""
    gpus = []
    
    # 方法1: 使用 WMI (需要 wmi 库)
    try:
        import wmi
        c = wmi.WMI()
        for i, gpu in enumerate(c.Win32_VideoController()):
            gpus.append({
                "index": i,
                "name": gpu.Name or "Unknown GPU",
                "vendor": _detect_vendor(gpu.Name or "", gpu.AdapterCompatibility or ""),
            })
        if gpus:
            return gpus
    except ImportError:
        pass
    except Exception:
        pass
    
    # 方法2: 使用 PowerShell 作为备用方案
    try:
        result = subprocess.run(
            [
                "powershell", "-Command",
                "Get-WmiObject Win32_VideoController | Select-Object Name, AdapterCompatibility | ConvertTo-Json"
            ],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        if result.returncode == 0 and result.stdout.strip():
            import json
            data = json.loads(result.stdout)
            # 单个设备时返回的是 dict，多个设备时是 list
            if isinstance(data, dict):
                data = [data]
            for i, gpu in enumerate(data):
                name = gpu.get("Name", "Unknown GPU")
                vendor = _detect_vendor(name, gpu.get("AdapterCompatibility", ""))
                gpus.append({
                    "index": i,
                    "name": name,
                    "vendor": vendor,
                })
    except Exception:
        pass
    
    return gpus


def _get_gpu_devices_macos() -> List[Dict[str, str]]:
    """macOS 平台获取 GPU 设备信息。"""
    gpus = []
    
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            import json
            data = json.loads(result.stdout)
            for i, display in enumerate(data.get("SPDisplaysDataType", [])):
                name = display.get("sppci_model", "Unknown GPU")
                vendor = display.get("spdisplays_vendor", "")
                if not vendor:
                    vendor = "Apple" if "Apple" in name or "M1" in name or "M2" in name or "M3" in name else "Unknown"
                gpus.append({
                    "index": i,
                    "name": name,
                    "vendor": vendor,
                })
    except Exception:
        pass
    
    return gpus


def _get_gpu_devices_linux() -> List[Dict[str, str]]:
    """Linux 平台获取 GPU 设备信息。"""
    gpus = []
    
    try:
        result = subprocess.run(
            ["lspci", "-mm"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                # 过滤 VGA/Display/3D 控制器
                if "VGA" in line or "Display" in line or "3D" in line:
                    # lspci -mm 格式: slot "class" "vendor" "device" ...
                    parts = line.split('"')
                    if len(parts) >= 6:
                        vendor_str = parts[3] if len(parts) > 3 else ""
                        name = parts[5] if len(parts) > 5 else "Unknown GPU"
                        vendor = _detect_vendor(name, vendor_str)
                        gpus.append({
                            "index": len(gpus),
                            "name": name,
                            "vendor": vendor,
                        })
    except Exception:
        pass
    
    return gpus


def _detect_vendor(name: str, adapter_compatibility: str = "") -> str:
    """检测 GPU 厂商。"""
    name_upper = name.upper()
    compat_upper = adapter_compatibility.upper()
    
    if "NVIDIA" in name_upper or "NVIDIA" in compat_upper or "GEFORCE" in name_upper or "RTX" in name_upper or "GTX" in name_upper:
        return "NVIDIA"
    elif "AMD" in name_upper or "AMD" in compat_upper or "RADEON" in name_upper or "RX " in name_upper:
        return "AMD"
    elif "INTEL" in name_upper or "INTEL" in compat_upper or "UHD" in name_upper or "IRIS" in name_upper or "ARC" in name_upper:
        return "Intel"
    elif "APPLE" in name_upper or "M1" in name_upper or "M2" in name_upper or "M3" in name_upper:
        return "Apple"
    else:
        return adapter_compatibility if adapter_compatibility else "Unknown"


def get_available_compute_devices() -> Dict[str, List[Dict]]:
    """获取可用的计算设备信息（结合 ONNX Runtime Provider 和实际硬件）。
    
    Returns:
        包含以下键的字典:
        - cpu: CPU 信息
        - gpus: GPU 设备列表（带有可用的加速方式）
        - available_providers: ONNX Runtime 可用的 Provider 列表
        - recommended_provider: 推荐使用的 Provider
    """
    result = {
        "cpu": {"name": "CPU", "available": True},
        "gpus": [],
        "available_providers": [],
        "recommended_provider": "CPUExecutionProvider",
    }
    
    # 获取 ONNX Runtime 可用的 Providers
    try:
        import onnxruntime as ort
        result["available_providers"] = ort.get_available_providers()
    except ImportError:
        result["available_providers"] = ["CPUExecutionProvider"]
    
    # 获取实际的 GPU 设备
    gpus = get_gpu_devices()
    
    # 确定每个 GPU 可用的加速方式
    providers = result["available_providers"]
    
    for gpu in gpus:
        vendor = gpu["vendor"]
        gpu_info = {
            "index": gpu["index"],
            "name": gpu["name"],
            "vendor": vendor,
            "acceleration": [],
        }
        
        # 根据厂商和可用的 Provider 确定加速方式
        if vendor == "NVIDIA":
            if "CUDAExecutionProvider" in providers:
                gpu_info["acceleration"].append("CUDA")
            if "TensorrtExecutionProvider" in providers:
                gpu_info["acceleration"].append("TensorRT")
            if "DmlExecutionProvider" in providers:
                gpu_info["acceleration"].append("DirectML")
        elif vendor == "AMD":
            if "ROCMExecutionProvider" in providers:
                gpu_info["acceleration"].append("ROCm")
            if "DmlExecutionProvider" in providers:
                gpu_info["acceleration"].append("DirectML")
            if "MIGraphXExecutionProvider" in providers:
                gpu_info["acceleration"].append("MIGraphX")
        elif vendor == "Intel":
            if "OpenVINOExecutionProvider" in providers:
                gpu_info["acceleration"].append("OpenVINO")
            if "DmlExecutionProvider" in providers:
                gpu_info["acceleration"].append("DirectML")
        elif vendor == "Apple":
            if "CoreMLExecutionProvider" in providers:
                gpu_info["acceleration"].append("CoreML")
        else:
            # 未知厂商，尝试通用加速
            if "DmlExecutionProvider" in providers:
                gpu_info["acceleration"].append("DirectML")
        
        result["gpus"].append(gpu_info)
    
    # 确定推荐的 Provider
    if "CUDAExecutionProvider" in providers:
        result["recommended_provider"] = "CUDAExecutionProvider"
    elif "CoreMLExecutionProvider" in providers:
        result["recommended_provider"] = "CoreMLExecutionProvider"
    elif "DmlExecutionProvider" in providers:
        result["recommended_provider"] = "DmlExecutionProvider"
    elif "ROCMExecutionProvider" in providers:
        result["recommended_provider"] = "ROCMExecutionProvider"
    elif "OpenVINOExecutionProvider" in providers:
        result["recommended_provider"] = "OpenVINOExecutionProvider"
    
    return result

