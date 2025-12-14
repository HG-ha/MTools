# -*- coding: utf-8 -*-
"""更新检测服务模块。

提供应用版本检测和更新功能。
"""

import platform
import re
from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum

import httpx

from constants import APP_VERSION, GITHUB_API_URL, GITHUB_RELEASES_URL, DOWNLOAD_URL_CHINA
from utils import get_proxied_url


class UpdateStatus(Enum):
    """更新状态枚举。"""
    CHECKING = "checking"           # 正在检查
    UP_TO_DATE = "up_to_date"       # 已是最新版本
    UPDATE_AVAILABLE = "update_available"  # 有新版本
    ERROR = "error"                 # 检查失败


@dataclass
class UpdateInfo:
    """更新信息数据类。"""
    status: UpdateStatus
    current_version: str
    latest_version: Optional[str] = None
    release_notes: Optional[str] = None
    download_url: Optional[str] = None
    release_url: Optional[str] = None
    error_message: Optional[str] = None


class UpdateService:
    """更新检测服务类。
    
    负责检查应用更新，包括：
    - 从 GitHub Releases 获取最新版本信息
    - 比较版本号
    - 提供更新下载链接
    - 自动为中国用户提供代理加速链接
    - 智能检测网络环境，自动选择最佳下载源
    """
    
    # 请求超时时间（秒）
    REQUEST_TIMEOUT: int = 10
    
    # 网络检测超时时间（秒）
    NETWORK_TEST_TIMEOUT: int = 3
    
    def __init__(self) -> None:
        """初始化更新检测服务。"""
        self.current_version: str = APP_VERSION
        self._is_china_network: Optional[bool] = None  # 缓存网络检测结果
    
    @staticmethod
    def detect_china_network() -> bool:
        """检测是否在中国大陆网络环境。
        
        通过测试访问国内镜像和 GitHub 的速度来判断。
        优先级：国内镜像 > GitHub 代理 > GitHub 直连
        
        Returns:
            True 表示应使用国内镜像或代理
            False 表示可以直接访问 GitHub
        """
        try:
            import time
            
            # 首先测试国内镜像（优先级最高）
            china_reachable = False
            china_time = float('inf')
            
            try:
                start = time.time()
                with httpx.Client(timeout=UpdateService.NETWORK_TEST_TIMEOUT, follow_redirects=True) as client:
                    # 测试国内镜像网站的可达性
                    response = client.head("https://openlist.wer.plus")
                    if response.status_code < 500:
                        china_time = time.time() - start
                        china_reachable = True
            except Exception:
                pass  # 国内镜像不可访问
            
            # 测试 GitHub 访问速度
            github_reachable = False
            github_time = float('inf')
            
            try:
                start = time.time()
                with httpx.Client(timeout=UpdateService.NETWORK_TEST_TIMEOUT, follow_redirects=True) as client:
                    response = client.head("https://github.com")
                    if response.status_code < 500:
                        github_time = time.time() - start
                        github_reachable = True
            except Exception:
                pass  # GitHub 不可访问
            
            # 判断逻辑（优先使用国内镜像）：
            # 1. 如果国内镜像可访问，优先使用（无论 GitHub 是否可访问）
            # 2. 如果国内镜像不可访问但 GitHub 也不可访问，尝试使用代理
            # 3. 如果国内镜像不可访问但 GitHub 可访问，直接使用 GitHub
            
            if china_reachable:
                return True  # 国内镜像可用，优先使用
            
            if not github_reachable:
                return True  # GitHub 不可访问，尝试使用代理（fallback）
            
            return False  # GitHub 直连正常，使用 GitHub
            
        except Exception:
            # 检测失败，默认返回 True（优先尝试国内镜像）
            return True
    
    def is_china_network(self) -> bool:
        """获取网络环境检测结果（带缓存）。
        
        Returns:
            True 表示在中国大陆网络环境
        """
        if self._is_china_network is None:
            self._is_china_network = self.detect_china_network()
        return self._is_china_network
    
    @staticmethod
    def detect_cuda_variant() -> str:
        """检测当前运行的 CUDA 变体版本。
        
        优先使用构建时写入的 BUILD_CUDA_VARIANT 常量。
        只有在开发环境（未编译）时才使用运行时检测。
        
        Returns:
            CUDA 变体标识：'none', 'cuda', 或 'cuda_full'
        """
        # 检查是否是编译后的程序
        import sys
        is_frozen = getattr(sys, 'frozen', False)
        
        # 优先使用构建时写入的信息
        try:
            from constants import BUILD_CUDA_VARIANT
            
            # 如果是编译后的程序，BUILD_CUDA_VARIANT 必定是准确的
            if is_frozen:
                if BUILD_CUDA_VARIANT in ('none', 'cuda', 'cuda_full'):
                    return BUILD_CUDA_VARIANT
                else:
                    # 编译后的程序应该有明确的值，如果没有则说明编译配置有问题
                    print(f"⚠️ 警告：编译后的程序 BUILD_CUDA_VARIANT 值异常: {BUILD_CUDA_VARIANT}")
                    # 继续尝试运行时检测
            else:
                # 开发环境：如果有明确的非默认值，使用它
                if BUILD_CUDA_VARIANT in ('cuda', 'cuda_full'):
                    return BUILD_CUDA_VARIANT
                # 如果是 'none' 或其他值，继续运行时检测
        except ImportError:
            pass  # 如果导入失败，继续使用运行时检测
        
        # 运行时检测（主要用于开发环境）
        try:
            import onnxruntime as ort
            
            # 获取可用的执行提供程序
            providers = ort.get_available_providers()
            
            # 检查是否有 CUDA 支持
            has_cuda = 'CUDAExecutionProvider' in providers
            
            if not has_cuda:
                # 没有 CUDA 支持，检查是否有 DirectML (Windows 标准版)
                if 'DmlExecutionProvider' in providers:
                    return 'none'  # DirectML 版本
                return 'none'  # CPU 版本
            
            # 有 CUDA 支持，检测是否内置了 CUDA 库
            try:
                # 尝试导入 onnxruntime-gpu 的 CUDA 相关模块
                # 如果是 cuda_full 版本，会包含 cuda 和 cudnn 子包
                import importlib.util
                
                # 检查是否存在 onnxruntime.capi.onnxruntime_providers_cuda
                cuda_spec = importlib.util.find_spec('onnxruntime.capi.onnxruntime_providers_cuda')
                
                if cuda_spec and cuda_spec.origin:
                    # 检查是否在 onnxruntime 目录内部（cuda_full）还是系统路径（cuda）
                    ort_path = ort.__file__
                    if ort_path:
                        from pathlib import Path as PathLib
                        ort_dir = str(PathLib(ort_path).parent)
                        cuda_provider_path = str(cuda_spec.origin)
                        
                        # 如果 CUDA provider 在 onnxruntime 目录内，说明是 cuda_full
                        if cuda_provider_path.startswith(ort_dir):
                            return 'cuda_full'
                
                # 否则是需要外部 CUDA 的版本
                return 'cuda'
                
            except Exception:
                # 无法确定具体版本，默认为 cuda
                return 'cuda'
                
        except ImportError:
            # onnxruntime 未安装或导入失败
            return 'none'
        except Exception:
            # 其他错误，默认返回 none
            return 'none'
    
    @staticmethod
    def get_platform_name() -> str:
        """获取平台相关的名称，与 build.py 保持一致。
        
        包含 CUDA 变体检测，返回完整的平台标识。
        
        Returns:
            平台名称，例如：
            - "Windows_amd64" (DirectML 标准版)
            - "Windows_amd64_CUDA" (需要外部 CUDA)
            - "Windows_amd64_CUDA_FULL" (内置 CUDA)
            - "Darwin_arm64" (macOS)
            - "Linux_amd64" (CPU 版)
            - "Linux_amd64_CUDA" (需要外部 CUDA)
            - "Linux_amd64_CUDA_FULL" (内置 CUDA)
        """
        system = platform.system()
        machine = platform.machine().upper()
        
        # 统一机器架构名称（与 build.py 保持一致）
        arch_map = {
            'X86_64': 'amd64',   # Linux/macOS 常用
            'AMD64': 'amd64',    # Windows 常用
            'ARM64': 'arm64',    # Apple Silicon
            'AARCH64': 'arm64',  # Linux ARM64
            'I386': 'x86',
            'I686': 'x86',
        }
        
        arch = arch_map.get(machine, machine.lower())
        base_name = f"{system}_{arch}"
        
        # 检测 CUDA 变体
        cuda_variant = UpdateService.detect_cuda_variant()
        
        if cuda_variant == 'cuda':
            return f"{base_name}_CUDA"
        elif cuda_variant == 'cuda_full':
            return f"{base_name}_CUDA_FULL"
        else:
            return base_name
    
    @staticmethod
    def parse_version(version_str: str) -> Tuple[int, ...]:
        """解析版本号字符串为可比较的元组。
        
        支持格式：v1.0.0, 1.0.0, 1.0, 1.0.0-beta 等
        
        Args:
            version_str: 版本号字符串
        
        Returns:
            版本号元组，例如 (1, 0, 0)
        """
        # 移除开头的 'v' 或 'V'
        version_str = version_str.lstrip('vV')
        
        # 移除预发布标签（如 -beta, -alpha, -rc1 等）
        version_str = re.split(r'[-+]', version_str)[0]
        
        # 分割版本号并转换为整数
        parts = version_str.split('.')
        return tuple(int(part) for part in parts if part.isdigit())
    
    @staticmethod
    def compare_versions(version1: str, version2: str) -> int:
        """比较两个版本号。
        
        Args:
            version1: 第一个版本号
            version2: 第二个版本号
        
        Returns:
            -1: version1 < version2
             0: version1 == version2
             1: version1 > version2
        """
        v1 = UpdateService.parse_version(version1)
        v2 = UpdateService.parse_version(version2)
        
        # 补齐版本号长度
        max_len = max(len(v1), len(v2))
        v1 = v1 + (0,) * (max_len - len(v1))
        v2 = v2 + (0,) * (max_len - len(v2))
        
        if v1 < v2:
            return -1
        elif v1 > v2:
            return 1
        else:
            return 0
    
    def check_update(self) -> UpdateInfo:
        """检查更新。
        
        Returns:
            UpdateInfo: 更新信息对象
        """
        try:
            # 发送请求获取最新 Release 信息
            with httpx.Client(timeout=self.REQUEST_TIMEOUT, follow_redirects=True) as client:
                response = client.get(
                    GITHUB_API_URL,
                    headers={
                        "Accept": "application/vnd.github.v3+json",
                        "User-Agent": f"MTools/{self.current_version}"
                    }
                )
                
                if response.status_code == 404:
                    # 没有发布任何 Release
                    return UpdateInfo(
                        status=UpdateStatus.UP_TO_DATE,
                        current_version=self.current_version,
                        latest_version=self.current_version,
                        release_url=GITHUB_RELEASES_URL,
                    )
                
                response.raise_for_status()
                data = response.json()
            
            # 解析版本信息
            latest_version = data.get("tag_name", "").lstrip('vV')
            release_notes = data.get("body", "")
            release_url = data.get("html_url", GITHUB_RELEASES_URL)
            
            # 查找当前平台的下载链接
            download_url = None
            assets = data.get("assets", [])
            platform_name = self.get_platform_name()  # 例如 "Windows_amd64_CUDA_FULL"
            
            # 调试信息：输出检测到的平台名称
            import sys
            is_frozen = getattr(sys, 'frozen', False)
            if not is_frozen:  # 只在开发环境显示
                print(f"[调试] 当前平台名称: {platform_name}")
                print(f"[调试] 可用的资源文件:")
                for asset in assets:
                    print(f"  - {asset.get('name', '')}")
            
            # 首先尝试精确匹配（包含 CUDA 变体）
            for asset in assets:
                asset_name = asset.get("name", "")
                # 精确匹配当前平台的文件
                # 例如：MTools_Windows_amd64_CUDA_FULL.zip
                if platform_name in asset_name and (asset_name.endswith('.zip') or asset_name.endswith('.tar.gz')):
                    download_url = asset.get("browser_download_url")
                    if not is_frozen:
                        print(f"[调试] 精确匹配成功: {asset_name}")
                    break
            
            # 备选：如果没找到精确匹配，尝试降级匹配
            # CUDA_FULL -> CUDA -> 标准版
            if not download_url:
                fallback_variants = []
                
                if '_CUDA_FULL' in platform_name:
                    # CUDA_FULL 版本可以降级到 CUDA 或标准版
                    base = platform_name.replace('_CUDA_FULL', '')
                    fallback_variants = [
                        f"{base}_CUDA",  # 降级到 CUDA 版
                        base,            # 降级到标准版
                    ]
                elif '_CUDA' in platform_name:
                    # CUDA 版本可以降级到标准版（但不能升级到 CUDA_FULL）
                    base = platform_name.replace('_CUDA', '')
                    fallback_variants = [base]
                
                if not is_frozen and fallback_variants:
                    print(f"[调试] 精确匹配失败，尝试降级匹配: {fallback_variants}")
                
                # 尝试降级版本
                for variant in fallback_variants:
                    for asset in assets:
                        asset_name = asset.get("name", "")
                        if variant in asset_name and (asset_name.endswith('.zip') or asset_name.endswith('.tar.gz')):
                            download_url = asset.get("browser_download_url")
                            if not is_frozen:
                                print(f"[调试] 降级匹配成功: {asset_name} (匹配变体: {variant})")
                            break
                    if download_url:
                        break
            
            # 最后的备选：模糊匹配系统类型
            if not download_url:
                system = platform.system().lower()
                for asset in assets:
                    asset_name = asset.get("name", "").lower()
                    if system in asset_name and (asset_name.endswith('.zip') or asset_name.endswith('.tar.gz')):
                        download_url = asset.get("browser_download_url")
                        break
            
            # 比较版本
            comparison = self.compare_versions(self.current_version, latest_version)
            
            # 根据网络环境选择下载源
            # 优先级：国内镜像 > GitHub 代理 > GitHub 直连
            if download_url:
                if self.is_china_network():
                    # 优先使用国内镜像，将 release_url 指向国内镜像页面
                    # 用户可以从那里手动下载或使用自动更新
                    release_url = DOWNLOAD_URL_CHINA
                    # 同时提供 GitHub 代理链接作为备选
                    download_url = get_proxied_url(download_url)
                else:
                    # 国际网络环境，仍然通过 get_proxied_url 以支持 IP 地理位置检测
                    download_url = get_proxied_url(download_url)
            
            if comparison < 0:
                # 有新版本
                return UpdateInfo(
                    status=UpdateStatus.UPDATE_AVAILABLE,
                    current_version=self.current_version,
                    latest_version=latest_version,
                    release_notes=release_notes,
                    download_url=download_url,
                    release_url=release_url,
                )
            else:
                # 已是最新版本
                return UpdateInfo(
                    status=UpdateStatus.UP_TO_DATE,
                    current_version=self.current_version,
                    latest_version=latest_version,
                    release_url=release_url,
                )
        
        except httpx.TimeoutException:
            return UpdateInfo(
                status=UpdateStatus.ERROR,
                current_version=self.current_version,
                error_message="检查更新超时，请检查网络连接",
            )
        except httpx.HTTPStatusError as e:
            return UpdateInfo(
                status=UpdateStatus.ERROR,
                current_version=self.current_version,
                error_message=f"服务器返回错误: {e.response.status_code}",
            )
        except Exception as e:
            return UpdateInfo(
                status=UpdateStatus.ERROR,
                current_version=self.current_version,
                error_message=f"检查更新失败: {str(e)}",
            )
    
    async def check_update_async(self) -> UpdateInfo:
        """异步检查更新。
        
        Returns:
            UpdateInfo: 更新信息对象
        """
        try:
            async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT, follow_redirects=True) as client:
                response = await client.get(
                    GITHUB_API_URL,
                    headers={
                        "Accept": "application/vnd.github.v3+json",
                        "User-Agent": f"MTools/{self.current_version}"
                    }
                )
                
                if response.status_code == 404:
                    return UpdateInfo(
                        status=UpdateStatus.UP_TO_DATE,
                        current_version=self.current_version,
                        latest_version=self.current_version,
                        release_url=GITHUB_RELEASES_URL,
                    )
                
                response.raise_for_status()
                data = response.json()
            
            latest_version = data.get("tag_name", "").lstrip('vV')
            release_notes = data.get("body", "")
            release_url = data.get("html_url", GITHUB_RELEASES_URL)
            
            # 查找当前平台的下载链接
            download_url = None
            assets = data.get("assets", [])
            platform_name = self.get_platform_name()
            
            # 首先尝试精确匹配（包含 CUDA 变体）
            for asset in assets:
                asset_name = asset.get("name", "")
                if platform_name in asset_name and (asset_name.endswith('.zip') or asset_name.endswith('.tar.gz')):
                    download_url = asset.get("browser_download_url")
                    break
            
            # 备选：如果没找到精确匹配，尝试降级匹配
            if not download_url:
                fallback_variants = []
                
                if '_CUDA_FULL' in platform_name:
                    base = platform_name.replace('_CUDA_FULL', '')
                    fallback_variants = [f"{base}_CUDA", base]
                elif '_CUDA' in platform_name:
                    base = platform_name.replace('_CUDA', '')
                    fallback_variants = [base]
                
                for variant in fallback_variants:
                    for asset in assets:
                        asset_name = asset.get("name", "")
                        if variant in asset_name and (asset_name.endswith('.zip') or asset_name.endswith('.tar.gz')):
                            download_url = asset.get("browser_download_url")
                            break
                    if download_url:
                        break
            
            # 最后的备选：模糊匹配系统类型
            if not download_url:
                system = platform.system().lower()
                for asset in assets:
                    asset_name = asset.get("name", "").lower()
                    if system in asset_name and (asset_name.endswith('.zip') or asset_name.endswith('.tar.gz')):
                        download_url = asset.get("browser_download_url")
                        break
            
            comparison = self.compare_versions(self.current_version, latest_version)
            
            # 根据网络环境选择下载源
            # 优先级：国内镜像 > GitHub 代理 > GitHub 直连
            if download_url:
                if self.is_china_network():
                    # 优先使用国内镜像，将 release_url 指向国内镜像页面
                    # 用户可以从那里手动下载或使用自动更新
                    release_url = DOWNLOAD_URL_CHINA
                    # 同时提供 GitHub 代理链接作为备选
                    download_url = get_proxied_url(download_url)
                else:
                    # 国际网络环境，仍然通过 get_proxied_url 以支持 IP 地理位置检测
                    download_url = get_proxied_url(download_url)
            
            if comparison < 0:
                return UpdateInfo(
                    status=UpdateStatus.UPDATE_AVAILABLE,
                    current_version=self.current_version,
                    latest_version=latest_version,
                    release_notes=release_notes,
                    download_url=download_url,
                    release_url=release_url,
                )
            else:
                return UpdateInfo(
                    status=UpdateStatus.UP_TO_DATE,
                    current_version=self.current_version,
                    latest_version=latest_version,
                    release_url=release_url,
                )
        
        except httpx.TimeoutException:
            return UpdateInfo(
                status=UpdateStatus.ERROR,
                current_version=self.current_version,
                error_message="检查更新超时，请检查网络连接",
            )
        except httpx.HTTPStatusError as e:
            return UpdateInfo(
                status=UpdateStatus.ERROR,
                current_version=self.current_version,
                error_message=f"服务器返回错误: {e.response.status_code}",
            )
        except Exception as e:
            return UpdateInfo(
                status=UpdateStatus.ERROR,
                current_version=self.current_version,
                error_message=f"检查更新失败: {str(e)}",
            )
