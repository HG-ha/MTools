# -*- coding: utf-8 -*-
"""配置服务模块。

提供应用配置管理，包括数据目录设置、用户偏好设置等。
"""

import json
import platform
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigService:
    """配置服务类。
    
    负责管理应用配置，包括：
    - 数据存储目录管理
    - 用户设置保存和读取
    - 跨平台目录规范支持
    """
    
    def __init__(self) -> None:
        """初始化配置服务。"""
        self.config_file: Path = self._get_config_file_path()
        self.config: Dict[str, Any] = self._load_config()
    
    def _get_default_data_dir(self) -> Path:
        """获取默认数据目录（遵循平台规范）。
        
        Returns:
            默认数据目录路径
        """
        system: str = platform.system()
        app_name: str = "MTools"
        
        if system == "Windows":
            # Windows: %APPDATA%\MTools
            base_dir: Path = Path.home() / "AppData" / "Roaming"
        elif system == "Darwin":
            # macOS: ~/Library/Application Support/MTools
            base_dir = Path.home() / "Library" / "Application Support"
        else:
            # Linux: ~/.local/share/MTools
            base_dir = Path.home() / ".local" / "share"
        
        data_dir: Path = base_dir / app_name
        return data_dir
    
    def _get_config_file_path(self) -> Path:
        """获取配置文件路径（遵循平台规范）。
        
        Returns:
            配置文件路径
        """
        system: str = platform.system()
        app_name: str = "MTools"
        
        if system == "Windows":
            # Windows: %APPDATA%\MTools\config.json
            config_dir: Path = Path.home() / "AppData" / "Roaming" / app_name
        elif system == "Darwin":
            # macOS: ~/Library/Application Support/MTools/config.json
            config_dir = Path.home() / "Library" / "Application Support" / app_name
        else:
            # Linux: ~/.config/MTools/config.json
            config_dir = Path.home() / ".config" / app_name
        
        # 确保目录存在
        config_dir.mkdir(parents=True, exist_ok=True)
        
        return config_dir / "config.json"
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件。
        
        Returns:
            配置字典
        """
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config: Dict[str, Any] = json.load(f)
                    return config
            except Exception as e:
                return self._get_default_config()
        else:
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置。
        
        Returns:
            默认配置字典
        """
        return {
            "data_dir": str(self._get_default_data_dir()),
            "use_custom_dir": False,
            "theme_mode": "system",  # system, light, dark
            "language": "zh_CN",
            "font_family": "System",  # 默认系统字体
            "font_scale": 1.0,  # 字体缩放比例，1.0为默认大小
            "window_left": None,   # 窗口左边距，None表示居中
            "window_top": None,    # 窗口上边距，None表示居中
            "window_width": None,  # 窗口宽度，None表示使用默认值
            "window_height": None, # 窗口高度，None表示使用默认值
            "window_maximized": False,  # 窗口是否最大化
            "window_opacity": 1.0,  # 窗口透明度，1.0为完全不透明，0.0为完全透明
            "background_image": None,  # 背景图片路径，None表示无背景图片
            "background_image_fit": "cover",  # 背景图片适应模式: cover, contain, fill, none
            "gpu_acceleration": True,  # GPU加速开关，默认开启
            "gpu_memory_limit": 2048,  # GPU内存限制（MB），默认2048MB
            "gpu_device_id": 0,  # GPU设备ID，默认使用第一个GPU（0）
            "gpu_enable_memory_arena": True,  # 是否启用GPU内存池优化，默认开启
        }
    
    def save_config(self) -> bool:
        """保存配置到文件。
        
        Returns:
            是否保存成功
        """
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            return False
    
    def get_data_dir(self) -> Path:
        """获取数据目录。
        
        Returns:
            数据目录路径
        """
        data_dir_str: str = self.config.get("data_dir", str(self._get_default_data_dir()))
        data_dir: Path = Path(data_dir_str)
        
        # 确保目录存在
        data_dir.mkdir(parents=True, exist_ok=True)
        
        return data_dir
    
    def set_data_dir(self, path: str, is_custom: bool = True) -> bool:
        """设置数据目录。
        
        Args:
            path: 目录路径
            is_custom: 是否为自定义目录
        
        Returns:
            是否设置成功
        """
        try:
            data_dir: Path = Path(path)
            # 验证路径
            if not data_dir.exists():
                data_dir.mkdir(parents=True, exist_ok=True)
            
            self.config["data_dir"] = str(data_dir)
            self.config["use_custom_dir"] = is_custom
            return self.save_config()
        except Exception as e:
            return False
    
    def check_data_exists(self, directory: Path = None) -> bool:
        """检查数据目录是否包含数据。
        
        Args:
            directory: 要检查的目录，默认为当前数据目录
        
        Returns:
            是否包含数据
        """
        if directory is None:
            directory = self.get_data_dir()
        
        if not directory.exists():
            return False
        
        # 检查是否有子目录或文件（排除临时文件）
        try:
            items = list(directory.iterdir())
            # 过滤掉隐藏文件和临时文件
            significant_items = [
                item for item in items 
                if not item.name.startswith('.') and item.name != 'temp'
            ]
            return len(significant_items) > 0
        except Exception:
            return False
    
    def migrate_data(self, source_dir: Path, dest_dir: Path, progress_callback=None) -> tuple[bool, str]:
        """迁移数据从源目录到目标目录。
        
        Args:
            source_dir: 源数据目录
            dest_dir: 目标数据目录
            progress_callback: 进度回调函数 (current, total, message)
        
        Returns:
            (是否成功, 消息)
        """
        import shutil
        
        try:
            if not source_dir.exists():
                return False, "源目录不存在"
            
            # 确保目标目录存在
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            # 获取所有要迁移的项目（排除 config.json）
            items = []
            for item in source_dir.iterdir():
                # 跳过 config.json，保留在原目录
                if item.name == "config.json":
                    continue
                items.append(item)
            
            total_items = len(items)
            
            if total_items == 0:
                return True, "没有需要迁移的数据"
            
            migrated_count = 0
            
            for i, item in enumerate(items):
                try:
                    dest_item = dest_dir / item.name
                    
                    if progress_callback:
                        progress_callback(i, total_items, f"正在迁移: {item.name}")
                    
                    if item.is_dir():
                        # 复制目录
                        if dest_item.exists():
                            shutil.rmtree(dest_item)
                        shutil.copytree(item, dest_item)
                    else:
                        # 复制文件
                        shutil.copy2(item, dest_item)
                    
                    migrated_count += 1
                except Exception as e:
                    continue
            
            if progress_callback:
                progress_callback(total_items, total_items, "迁移完成")
            
            if migrated_count == 0:
                return False, "没有成功迁移任何数据"
            elif migrated_count < total_items:
                return True, f"部分迁移成功: {migrated_count}/{total_items} 项"
            else:
                return True, f"迁移成功: {migrated_count} 项"
        
        except Exception as e:
            return False, f"迁移失败: {str(e)}"
    
    def reset_to_default_dir(self) -> bool:
        """重置为默认数据目录。
        
        Returns:
            是否重置成功
        """
        default_dir: Path = self._get_default_data_dir()
        return self.set_data_dir(str(default_dir), is_custom=False)
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """获取配置值。
        
        Args:
            key: 配置键
            default: 默认值
        
        Returns:
            配置值
        """
        return self.config.get(key, default)
    
    def set_config_value(self, key: str, value: Any) -> bool:
        """设置配置值。
        
        Args:
            key: 配置键
            value: 配置值
        
        Returns:
            是否设置成功
        """
        self.config[key] = value
        return self.save_config()
    
    def get_temp_dir(self) -> Path:
        """获取临时文件目录。
        
        Returns:
            临时文件目录路径
        """
        temp_dir: Path = self.get_data_dir() / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir
    
    def get_output_dir(self) -> Path:
        """获取输出文件目录。
        
        Returns:
            输出文件目录路径
        """
        output_dir: Path = self.get_data_dir() / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

