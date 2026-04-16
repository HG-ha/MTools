# -*- coding: utf-8 -*-
"""配置服务模块。

提供应用配置管理，包括数据目录设置、用户偏好设置等。
配置以加密形式存储（Fernet / AES-128），密钥基于机器特征自动派生。
"""

import getpass
import hashlib
import json
import platform
import re
from pathlib import Path
from typing import Any, Dict, Optional

from flet.security import encrypt, decrypt


class ConfigService:
    """配置服务类。
    
    负责管理应用配置，包括：
    - 数据存储目录管理
    - 用户设置保存和读取
    - 跨平台目录规范支持
    - 配置加密存储（对外接口透明）
    """

    _CONFIG_FILENAME = "config.dat"
    _LEGACY_FILENAME = "config.json"
    
    def __init__(self) -> None:
        """初始化配置服务。"""
        self._secret_key: str = self._derive_secret_key()
        self._config_dir: Path = self._get_config_dir()
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file: Path = self._config_dir / self._CONFIG_FILENAME
        self.config: Dict[str, Any] = self._load_config()
    
    @staticmethod
    def _derive_secret_key() -> str:
        """基于机器特征派生加密密钥。

        同一台机器、同一用户始终得到相同密钥，无需用户手动配置。
        """
        raw = f"MTools:{getpass.getuser()}@{platform.node()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _get_default_data_dir(self) -> Path:
        """获取默认数据目录（遵循平台规范）。
        
        Returns:
            默认数据目录路径
        """
        system: str = platform.system()
        app_name: str = "MTools"
        
        if system == "Windows":
            base_dir: Path = Path.home() / "AppData" / "Roaming"
        elif system == "Darwin":
            base_dir = Path.home() / "Library" / "Application Support"
        else:
            base_dir = Path.home() / ".local" / "share"
        
        data_dir: Path = base_dir / app_name
        return data_dir
    
    @staticmethod
    def _get_config_dir() -> Path:
        """获取配置文件所在目录（遵循平台规范）。"""
        system: str = platform.system()
        app_name: str = "MTools"
        
        if system == "Windows":
            return Path.home() / "AppData" / "Roaming" / app_name
        elif system == "Darwin":
            return Path.home() / "Library" / "Application Support" / app_name
        else:
            return Path.home() / ".config" / app_name

    # ------------------------------------------------------------------
    # 加密读写
    # ------------------------------------------------------------------

    def _encrypt_and_write(self, data: Dict[str, Any], path: Path) -> None:
        """将配置字典加密后写入文件。"""
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        encrypted = encrypt(json_str, self._secret_key)
        path.write_text(encrypted, encoding="utf-8")

    def _read_and_decrypt(self, path: Path) -> Dict[str, Any]:
        """从加密文件读取并解密为配置字典。

        Raises:
            Exception: 解密或 JSON 解析失败
        """
        encrypted = path.read_text(encoding="utf-8").strip()
        json_str = decrypt(encrypted, self._secret_key)
        return json.loads(json_str)

    # ------------------------------------------------------------------
    # 配置加载（含旧版明文迁移）
    # ------------------------------------------------------------------

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件。

        优先读取加密的 config.dat；若不存在则尝试迁移旧版明文 config.json。
        解密失败时会尝试从明文备份恢复。
        加载后始终与默认值合并并校验关键字段，防止老配置导致白屏。
        """
        legacy_file = self._config_dir / self._LEGACY_FILENAME
        backup_file = self._config_dir / "config.json.bak"

        config: Optional[Dict[str, Any]] = None

        # 1) 优先读取加密配置
        if self.config_file.exists():
            try:
                config = self._read_and_decrypt(self.config_file)
            except Exception:
                # 解密失败（密钥变化等），尝试从明文备份恢复
                config = self._try_load_legacy(legacy_file, backup_file)

        # 2) 尝试迁移旧版明文 config.json
        if config is None and legacy_file.exists():
            try:
                with open(legacy_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                self._encrypt_and_write(config, self.config_file)
                try:
                    legacy_file.rename(backup_file)
                except Exception:
                    pass
            except Exception:
                config = None

        # 3) 全新安装
        if config is None:
            return self._get_default_config()

        # 用默认值补全缺失的 key（老配置可能缺少新版本新增的字段）
        defaults = self._get_default_config()
        for key, value in defaults.items():
            config.setdefault(key, value)

        # 校验关键字段，防止无效值导致 UI 白屏
        config = self._sanitize_config(config, defaults)
        return config

    def _try_load_legacy(self, *paths: Path) -> Dict[str, Any] | None:
        """尝试从明文 JSON 文件恢复配置，成功后重新加密保存。"""
        for path in paths:
            if not path.exists():
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    config: Dict[str, Any] = json.load(f)
                self._encrypt_and_write(config, self.config_file)
                return config
            except Exception:
                continue
        return None
    
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
            "font_family": "System",
            "font_scale": 1.0,
            "window_left": None,
            "window_top": None,
            "window_width": None,
            "window_height": None,
            "window_maximized": False,
            "window_opacity": 1.0,
            "background_image": None,
            "background_image_fit": "cover",
            "gpu_acceleration": platform.system() != "Darwin",
            "gpu_memory_limit": 8192,
            "gpu_device_id": 0,
            "gpu_enable_memory_arena": False,
            "onnx_cpu_threads": 0,
            "onnx_execution_mode": "sequential",
            "onnx_enable_model_cache": False,
        }

    @staticmethod
    def _sanitize_config(config: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
        """校验并修正配置中可能导致 UI 异常的值。

        老版本配置可能包含新版本不兼容的值（格式变更、类型不匹配等），
        此方法将无效值替换为默认值，防止启动白屏。
        """
        # theme_color: 必须是 #RRGGBB 格式
        tc = config.get("theme_color")
        if tc is not None and not (isinstance(tc, str) and re.match(r'^#[0-9A-Fa-f]{6}$', tc)):
            config["theme_color"] = defaults.get("theme_color", "#667EEA")

        # theme_mode: 必须是已知值
        if config.get("theme_mode") not in ("system", "light", "dark"):
            config["theme_mode"] = "system"

        # window_opacity: 必须是 0~1 之间的数值
        try:
            op = float(config.get("window_opacity", 1.0))
            if not (0.1 <= op <= 1.0):
                op = 1.0
            config["window_opacity"] = op
        except (TypeError, ValueError):
            config["window_opacity"] = 1.0

        # font_family: 必须是字符串
        if not isinstance(config.get("font_family"), str) or not config["font_family"]:
            config["font_family"] = "System"

        # window 尺寸: 必须是正数或 None
        for key in ("window_width", "window_height"):
            val = config.get(key)
            if val is not None:
                try:
                    val = float(val)
                    if val <= 0:
                        config[key] = None
                except (TypeError, ValueError):
                    config[key] = None

        return config

    def save_config(self) -> bool:
        """保存配置到加密文件。
        
        Returns:
            是否保存成功
        """
        try:
            self._encrypt_and_write(self.config, self.config_file)
            return True
        except Exception:
            return False
    
    # ------------------------------------------------------------------
    # 导入 / 导出（明文 JSON，供设置界面使用）
    # ------------------------------------------------------------------

    def export_config(self, path: Path) -> bool:
        """将当前配置导出为明文 JSON 文件。"""
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    _LOCAL_ONLY_KEYS = {"data_dir", "use_custom_dir"}

    def import_config(self, path: Path) -> bool:
        """从明文 JSON 文件导入配置并加密保存。

        数据存储路径等本机相关设置不会被覆盖。
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                imported: Dict[str, Any] = json.load(f)
            for key in self._LOCAL_ONLY_KEYS:
                if key in self.config:
                    imported[key] = self.config[key]
            self.config = imported
            return self.save_config()
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 公共接口（与旧版完全兼容）
    # ------------------------------------------------------------------

    def get_data_dir(self) -> Path:
        """获取数据目录。
        
        Returns:
            数据目录路径
        """
        data_dir_str: str = self.config.get("data_dir", str(self._get_default_data_dir()))
        data_dir: Path = Path(data_dir_str)
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
            if not data_dir.exists():
                data_dir.mkdir(parents=True, exist_ok=True)
            
            self.config["data_dir"] = str(data_dir)
            self.config["use_custom_dir"] = is_custom
            return self.save_config()
        except Exception:
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
        
        try:
            items = list(directory.iterdir())
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
            
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            skip_names = {self._CONFIG_FILENAME, self._LEGACY_FILENAME}
            items = [
                item for item in source_dir.iterdir()
                if item.name not in skip_names
            ]
            
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
                        if dest_item.exists():
                            shutil.rmtree(dest_item)
                        shutil.copytree(item, dest_item)
                    else:
                        shutil.copy2(item, dest_item)
                    
                    migrated_count += 1
                except Exception:
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
    
    def record_tool_usage(self, tool_name: str) -> None:
        """记录工具使用次数。
        
        Args:
            tool_name: 工具名称
        """
        tool_usage_count = self.get_config_value("tool_usage_count", {})
        
        if tool_name not in tool_usage_count:
            tool_usage_count[tool_name] = 0
        
        tool_usage_count[tool_name] += 1
        
        self.set_config_value("tool_usage_count", tool_usage_count)
    
    def get_pinned_tools(self) -> list:
        """获取置顶工具列表。
        
        Returns:
            置顶工具ID列表
        """
        return self.get_config_value("pinned_tools", [])
    
    def pin_tool(self, tool_id: str) -> None:
        """置顶工具。
        
        Args:
            tool_id: 工具ID
        """
        pinned = self.get_pinned_tools()
        if tool_id not in pinned:
            pinned.insert(0, tool_id)
            self.set_config_value("pinned_tools", pinned)
    
    def unpin_tool(self, tool_id: str) -> None:
        """取消置顶工具。
        
        Args:
            tool_id: 工具ID
        """
        pinned = self.get_pinned_tools()
        if tool_id in pinned:
            pinned.remove(tool_id)
            self.set_config_value("pinned_tools", pinned)
    
    def is_tool_pinned(self, tool_id: str) -> bool:
        """检查工具是否已置顶。
        
        Args:
            tool_id: 工具ID
            
        Returns:
            是否已置顶
        """
        return tool_id in self.get_pinned_tools()
    
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
