# -*- coding: utf-8 -*-
"""编码转换服务模块。

提供文件编码检测和转换功能。
"""

import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import chardet


class EncodingService:
    """编码转换服务类。
    
    提供文件编码相关功能，包括：
    - 自动检测文件编码
    - 编码格式转换
    - 批量处理文件
    - 保留文件权限和元数据
    """
    
    # 支持的编码格式列表
    SUPPORTED_ENCODINGS: List[str] = [
        "UTF-8",
        "UTF-8-SIG",  # UTF-8 with BOM
        "UTF-16",
        "UTF-16-LE",
        "UTF-16-BE",
        "UTF-32",
        "GBK",
        "GB2312",
        "GB18030",
        "BIG5",
        "Shift_JIS",
        "EUC-JP",
        "EUC-KR",
        "ISO-8859-1",
        "ASCII",
        "Windows-1252",
    ]
    
    # 常用文本文件扩展名
    TEXT_FILE_EXTENSIONS: List[str] = [
        ".txt", ".py", ".java", ".c", ".cpp", ".h", ".hpp",
        ".js", ".ts", ".jsx", ".tsx", ".vue", ".html", ".css",
        ".scss", ".sass", ".less", ".xml", ".json", ".yaml",
        ".yml", ".md", ".rst", ".csv", ".sql", ".sh", ".bat",
        ".ps1", ".php", ".rb", ".go", ".rs", ".swift", ".kt",
    ]
    
    def __init__(self) -> None:
        """初始化编码转换服务。"""
        pass
    
    def detect_encoding(
        self,
        file_path: Path,
        sample_size: int = 100000
    ) -> Dict[str, any]:
        """检测文件编码。
        
        Args:
            file_path: 文件路径
            sample_size: 采样大小（字节），默认100KB
        
        Returns:
            检测结果字典，包含:
            - encoding: 编码名称
            - confidence: 置信度(0-1)
            - language: 语言（如果检测到）
            - error: 错误信息（如果检测失败）
        """
        try:
            # 读取文件采样
            with open(file_path, 'rb') as f:
                raw_data: bytes = f.read(sample_size)
            
            # 使用chardet检测编码
            result: Dict[str, any] = chardet.detect(raw_data)
            
            if result['encoding']:
                return {
                    'encoding': result['encoding'],
                    'confidence': result.get('confidence', 0.0),
                    'language': result.get('language', 'unknown'),
                }
            else:
                return {
                    'error': '无法检测编码'
                }
        
        except Exception as e:
            return {
                'error': f'检测失败: {str(e)}'
            }
    
    def convert_encoding(
        self,
        input_path: Path,
        output_path: Path,
        source_encoding: Optional[str] = None,
        target_encoding: str = "UTF-8",
        backup: bool = True
    ) -> Tuple[bool, str]:
        """转换文件编码。
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            source_encoding: 源编码（None表示自动检测）
            target_encoding: 目标编码
            backup: 是否备份原文件
        
        Returns:
            (成功标志, 消息)
        """
        try:
            # 自动检测源编码
            if source_encoding is None:
                detect_result: Dict[str, any] = self.detect_encoding(input_path)
                if 'error' in detect_result:
                    return False, detect_result['error']
                source_encoding = detect_result['encoding']
                confidence: float = detect_result.get('confidence', 0)
                
                # 置信度太低时警告
                if confidence < 0.7:
                    return False, f"编码检测置信度较低({confidence:.0%})，建议手动指定源编码"
            
            # 读取文件内容
            with open(input_path, 'r', encoding=source_encoding, errors='replace') as f:
                content: str = f.read()
            
            # 如果是覆盖模式且需要备份
            if backup and input_path == output_path:
                backup_path: Path = input_path.with_suffix(input_path.suffix + '.bak')
                shutil.copy2(input_path, backup_path)
            
            # 写入新编码
            # 处理UTF-8-SIG（带BOM的UTF-8）
            if target_encoding.upper() == "UTF-8-SIG":
                write_encoding = "utf-8-sig"
            else:
                write_encoding = target_encoding
            
            with open(output_path, 'w', encoding=write_encoding, errors='replace') as f:
                f.write(content)
            
            # 保留文件权限和时间戳（如果不是覆盖模式）
            if input_path != output_path:
                try:
                    shutil.copystat(input_path, output_path)
                except Exception:
                    pass  # 忽略权限复制失败
            
            return True, f"转换成功: {source_encoding} → {target_encoding}"
        
        except UnicodeDecodeError as e:
            return False, f"解码失败: 源编码可能不正确 ({source_encoding})"
        except UnicodeEncodeError as e:
            return False, f"编码失败: 目标编码不支持某些字符 ({target_encoding})"
        except Exception as e:
            return False, f"转换失败: {str(e)}"
    
    def batch_convert(
        self,
        file_paths: List[Path],
        target_encoding: str,
        source_encoding: Optional[str] = None,
        output_mode: str = "overwrite",
        output_dir: Optional[Path] = None,
        callback: Optional[callable] = None
    ) -> Dict[str, any]:
        """批量转换文件编码。
        
        Args:
            file_paths: 文件路径列表
            target_encoding: 目标编码
            source_encoding: 源编码（None表示自动检测）
            output_mode: 输出模式 (overwrite, new, custom)
            output_dir: 自定义输出目录（output_mode为custom时使用）
            callback: 进度回调函数 callback(current, total, file_name)
        
        Returns:
            结果字典，包含:
            - success_count: 成功数量
            - failed_count: 失败数量
            - errors: 错误列表
        """
        success_count: int = 0
        failed_count: int = 0
        errors: List[Dict[str, str]] = []
        total: int = len(file_paths)
        
        for i, input_path in enumerate(file_paths):
            if callback:
                callback(i + 1, total, input_path.name)
            
            # 确定输出路径
            if output_mode == "overwrite":
                output_path = input_path
            elif output_mode == "new":
                output_path = input_path.with_suffix(f".converted{input_path.suffix}")
            else:  # custom
                if output_dir:
                    output_path = output_dir / input_path.name
                else:
                    output_path = input_path
            
            # 转换编码
            success, message = self.convert_encoding(
                input_path,
                output_path,
                source_encoding=source_encoding,
                target_encoding=target_encoding,
                backup=(output_mode == "overwrite")
            )
            
            if success:
                success_count += 1
            else:
                failed_count += 1
                errors.append({
                    'file': str(input_path),
                    'error': message
                })
        
        return {
            'success_count': success_count,
            'failed_count': failed_count,
            'errors': errors
        }
    
    def is_text_file(self, file_path: Path) -> bool:
        """判断是否为文本文件。
        
        Args:
            file_path: 文件路径
        
        Returns:
            是否为文本文件
        """
        # 根据扩展名判断
        ext: str = file_path.suffix.lower()
        return ext in self.TEXT_FILE_EXTENSIONS
    
    def scan_directory(
        self,
        directory: Path,
        recursive: bool = False
    ) -> List[Path]:
        """扫描目录中的文本文件。
        
        Args:
            directory: 目录路径
            recursive: 是否递归扫描子目录
        
        Returns:
            文本文件路径列表
        """
        text_files: List[Path] = []
        
        if recursive:
            pattern = "**/*"
        else:
            pattern = "*"
        
        for file_path in directory.glob(pattern):
            if file_path.is_file() and self.is_text_file(file_path):
                text_files.append(file_path)
        
        return sorted(text_files)
    
    def get_file_info(self, file_path: Path) -> Dict[str, any]:
        """获取文件信息（包含编码）。
        
        Args:
            file_path: 文件路径
        
        Returns:
            文件信息字典
        """
        try:
            stat = file_path.stat()
            encoding_info = self.detect_encoding(file_path)
            
            return {
                'name': file_path.name,
                'path': str(file_path),
                'size': stat.st_size,
                'modified': stat.st_mtime,
                'encoding': encoding_info.get('encoding', '未知'),
                'confidence': encoding_info.get('confidence', 0.0),
                'language': encoding_info.get('language', '未知'),
                'error': encoding_info.get('error'),
            }
        except Exception as e:
            return {
                'name': file_path.name,
                'path': str(file_path),
                'error': str(e)
            }

