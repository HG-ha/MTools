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
        app_name: str = "MyTools"
        
        if system == "Windows":
            # Windows: %APPDATA%\MyTools
            base_dir: Path = Path.home() / "AppData" / "Roaming"
        elif system == "Darwin":
            # macOS: ~/Library/Application Support/MyTools
            base_dir = Path.home() / "Library" / "Application Support"
        else:
            # Linux: ~/.local/share/MyTools
            base_dir = Path.home() / ".local" / "share"
        
        data_dir: Path = base_dir / app_name
        return data_dir
    
    def _get_config_file_path(self) -> Path:
        """获取配置文件路径（遵循平台规范）。
        
        Returns:
            配置文件路径
        """
        system: str = platform.system()
        app_name: str = "MyTools"
        
        if system == "Windows":
            # Windows: %APPDATA%\MyTools\config.json
            config_dir: Path = Path.home() / "AppData" / "Roaming" / app_name
        elif system == "Darwin":
            # macOS: ~/Library/Application Support/MyTools/config.json
            config_dir = Path.home() / "Library" / "Application Support" / app_name
        else:
            # Linux: ~/.config/MyTools/config.json
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
                print(f"加载配置文件失败: {e}")
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
            print(f"保存配置文件失败: {e}")
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
            print(f"设置数据目录失败: {e}")
            return False
    
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

