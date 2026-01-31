# -*- coding: utf-8 -*-
"""语音识别服务模块。

使用 sherpa-onnx 和 Whisper 模型进行语音转文字。
支持 VAD（语音活动检测）智能分片，提高识别准确率。
"""

import os
from pathlib import Path
from typing import Optional, Callable, TYPE_CHECKING, List, Dict, Any, Tuple
from utils import logger
import numpy as np

if TYPE_CHECKING:
    from services import FFmpegService
    from services.vad_service import VADService
    from constants import WhisperModelInfo, SenseVoiceModelInfo


class SpeechRecognitionService:
    """语音识别服务类。
    
    支持 sherpa-onnx Whisper 和 SenseVoice/Paraformer 模型进行音视频转文字。
    支持 VAD（语音活动检测）智能分片。
    """
    
    def __init__(
        self,
        model_dir: Optional[Path] = None,
        ffmpeg_service: Optional['FFmpegService'] = None,
        vad_service: Optional['VADService'] = None,
        debug_mode: bool = False
    ):
        """初始化语音识别服务。
        
        Args:
            model_dir: 模型存储目录，默认为用户数据目录下的 models/whisper
            ffmpeg_service: FFmpeg 服务实例
            vad_service: VAD 服务实例（可选，用于智能分片）
            debug_mode: 是否启用调试模式（输出详细信息）
        """
        self.ffmpeg_service = ffmpeg_service
        self.vad_service = vad_service
        self.model_dir = model_dir
        self.debug_mode = debug_mode
        # 确保目录存在
        if self.model_dir:
            self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.recognizer = None
        self.current_model: Optional[str] = None
        self.model_type: str = "whisper"  # whisper 或 sensevoice 或 paraformer
        self.sample_rate: int = 16000  # 固定使用 16kHz
        self.current_provider: str = "未加载"
        
        # VAD 相关设置
        self.use_vad: bool = True  # 是否使用 VAD 智能分片
        
        # 标点恢复相关
        self.punctuator = None  # 标点恢复模型
        self.punctuation_model_path: Optional[Path] = None
        self.use_punctuation: bool = True  # 是否启用标点恢复（仅对无标点模型生效）
        
        # 字幕分段设置
        self.subtitle_max_length: int = 30  # 每段字幕最大字符数（默认30，适合阅读）
        self.subtitle_split_by_punctuation: bool = True  # 是否在标点处分段
        self.subtitle_keep_ending_punctuation: bool = True  # 是否保留结尾标点
        
        # 设置 FFmpeg 环境
        self._setup_ffmpeg_env()
    
    def _setup_ffmpeg_env(self) -> None:
        """设置 FFmpeg 环境变量（如果使用本地 FFmpeg）。"""
        if self.ffmpeg_service:
            ffmpeg_path = self.ffmpeg_service.get_ffmpeg_path()
            if ffmpeg_path and ffmpeg_path != "ffmpeg":
                # 如果是完整路径，将其目录添加到 PATH
                ffmpeg_dir = str(Path(ffmpeg_path).parent)
                if 'PATH' in os.environ:
                    # 将 ffmpeg 目录添加到 PATH 开头，优先使用
                    if ffmpeg_dir not in os.environ['PATH']:
                        os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ['PATH']
                else:
                    os.environ['PATH'] = ffmpeg_dir
    
    def _get_ffmpeg_cmd(self) -> str:
        """获取 FFmpeg 命令。
        
        Returns:
            ffmpeg 命令（可执行文件路径或 'ffmpeg'）
        """
        if self.ffmpeg_service:
            ffmpeg_path = self.ffmpeg_service.get_ffmpeg_path()
            if ffmpeg_path:
                return ffmpeg_path
        return 'ffmpeg'
    
    def get_available_models(self) -> list[str]:
        """获取可用的模型列表。
        
        Returns:
            模型键名列表
        """
        from constants import WHISPER_MODELS
        return list(WHISPER_MODELS.keys())
    
    def get_model_dir(self, model_key: str) -> Path:
        """获取指定模型的存储目录。
        
        Args:
            model_key: 模型键名
            
        Returns:
            模型存储目录路径
        """
        # 每个模型使用独立的子目录，避免文件冲突
        model_subdir = self.model_dir / model_key
        model_subdir.mkdir(parents=True, exist_ok=True)
        return model_subdir
    
    def download_model(
        self,
        model_key: str,
        model_info: 'WhisperModelInfo',
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> tuple[Path, Path, Path]:
        """下载模型文件（encoder + decoder + tokens + weights）。
        
        Args:
            model_key: 模型键名
            model_info: 模型信息
            progress_callback: 进度回调函数 (进度0-1, 状态消息)
            
        Returns:
            (encoder路径, decoder路径, tokens路径)
        """
        import httpx
        
        # 获取模型专属目录
        model_dir = self.get_model_dir(model_key)
        
        encoder_path = model_dir / model_info.encoder_filename
        decoder_path = model_dir / model_info.decoder_filename
        config_path = model_dir / model_info.config_filename
        
        # 检查外部权重文件
        encoder_weights_path = None
        decoder_weights_path = None
        if model_info.encoder_weights_filename:
            encoder_weights_path = model_dir / model_info.encoder_weights_filename
        if model_info.decoder_weights_filename:
            decoder_weights_path = model_dir / model_info.decoder_weights_filename
        
        # 检查所有必需文件是否存在
        required_files = [encoder_path, decoder_path, config_path]
        if encoder_weights_path:
            required_files.append(encoder_weights_path)
        if decoder_weights_path:
            required_files.append(decoder_weights_path)
        
        if all(f.exists() for f in required_files):
            return encoder_path, decoder_path, config_path
        
        files_to_download = []
        
        if not encoder_path.exists():
            files_to_download.append(('encoder', model_info.encoder_url, encoder_path))
        if not decoder_path.exists():
            files_to_download.append(('decoder', model_info.decoder_url, decoder_path))
        if not config_path.exists():
            files_to_download.append(('tokens', model_info.config_url, config_path))
        
        # 添加外部权重文件
        if encoder_weights_path and not encoder_weights_path.exists() and model_info.encoder_weights_url:
            files_to_download.append(('encoder权重', model_info.encoder_weights_url, encoder_weights_path))
        if decoder_weights_path and not decoder_weights_path.exists() and model_info.decoder_weights_url:
            files_to_download.append(('decoder权重', model_info.decoder_weights_url, decoder_weights_path))
        
        if not files_to_download:
            return encoder_path, decoder_path, config_path
        
        total_files = len(files_to_download)
        downloaded_files = []  # 记录成功下载的文件
        
        try:
            for i, (file_type, url, file_path) in enumerate(files_to_download):
                if progress_callback:
                    progress_callback(i / total_files, f"下载{file_type}模型...")
                
                # 使用临时文件下载，避免损坏原文件
                temp_path = file_path.with_suffix(file_path.suffix + '.tmp')
                
                try:
                    with httpx.stream("GET", url, follow_redirects=True, timeout=300.0) as response:
                        response.raise_for_status()
                        
                        total_size = int(response.headers.get('content-length', 0))
                        downloaded = 0
                        
                        with open(temp_path, 'wb') as f:
                            for chunk in response.iter_bytes(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    
                                    if progress_callback and total_size > 0:
                                        file_progress = (i + downloaded / total_size) / total_files
                                        size_mb = downloaded / (1024 * 1024)
                                        total_mb = total_size / (1024 * 1024)
                                        progress_callback(
                                            file_progress,
                                            f"下载{file_type}: {size_mb:.1f}/{total_mb:.1f} MB"
                                        )
                        
                        # 验证文件大小
                        if total_size > 0:
                            actual_size = temp_path.stat().st_size
                            if actual_size != total_size:
                                raise RuntimeError(
                                    f"{file_type}文件大小不匹配: "
                                    f"期望 {total_size} 字节, 实际 {actual_size} 字节"
                                )
                        
                        # 下载成功，重命名临时文件
                        if file_path.exists():
                            file_path.unlink()  # 删除旧文件
                        temp_path.rename(file_path)
                        downloaded_files.append(file_path)
                        
                        logger.info(f"{file_type}模型下载完成: {file_path.name}")
                        
                except Exception as e:
                    # 清理临时文件
                    if temp_path.exists():
                        try:
                            temp_path.unlink()
                        except:
                            pass
                    raise RuntimeError(f"下载{file_type}失败: {e}")
            
            if progress_callback:
                progress_callback(1.0, "下载完成!")
            
            return encoder_path, decoder_path, config_path
            
        except Exception as e:
            # 删除本次下载的所有文件（保留之前已存在的文件）
            for file_path in downloaded_files:
                if file_path.exists():
                    try:
                        file_path.unlink()
                        logger.warning(f"已删除不完整的文件: {file_path.name}")
                    except:
                        pass
            raise RuntimeError(f"下载模型失败: {e}")
    
    def download_sensevoice_model(
        self,
        model_key: str,
        model_info: 'SenseVoiceModelInfo',
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> tuple[Path, Path]:
        """下载 SenseVoice 模型文件（model.onnx + tokens.txt）。
        
        Args:
            model_key: 模型键名
            model_info: SenseVoice 模型信息
            progress_callback: 进度回调函数 (进度0-1, 状态消息)
            
        Returns:
            (model路径, tokens路径)
        """
        import httpx
        
        # 获取模型专属目录
        model_dir = self.get_model_dir(model_key)
        
        model_path = model_dir / model_info.model_filename
        tokens_path = model_dir / model_info.tokens_filename
        
        # 检查文件是否已存在
        if model_path.exists() and tokens_path.exists():
            return model_path, tokens_path
        
        files_to_download = []
        
        if not model_path.exists():
            files_to_download.append(('模型文件', model_info.model_url, model_path))
        if not tokens_path.exists():
            files_to_download.append(('词表文件', model_info.tokens_url, tokens_path))
        
        if not files_to_download:
            return model_path, tokens_path
        
        total_files = len(files_to_download)
        downloaded_files = []  # 记录成功下载的文件
        
        try:
            for i, (file_type, url, file_path) in enumerate(files_to_download):
                if progress_callback:
                    progress_callback(i / total_files, f"下载{file_type}...")
                
                # 使用临时文件下载，避免损坏原文件
                temp_path = file_path.with_suffix(file_path.suffix + '.tmp')
                
                try:
                    with httpx.stream("GET", url, follow_redirects=True, timeout=300.0) as response:
                        response.raise_for_status()
                        
                        total_size = int(response.headers.get('content-length', 0))
                        downloaded = 0
                        
                        with open(temp_path, 'wb') as f:
                            for chunk in response.iter_bytes(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    
                                    if progress_callback and total_size > 0:
                                        file_progress = (i + downloaded / total_size) / total_files
                                        size_mb = downloaded / (1024 * 1024)
                                        total_mb = total_size / (1024 * 1024)
                                        progress_callback(
                                            file_progress,
                                            f"下载{file_type}: {size_mb:.1f}/{total_mb:.1f} MB"
                                        )
                        
                        # 验证文件大小
                        if total_size > 0:
                            actual_size = temp_path.stat().st_size
                            if actual_size != total_size:
                                raise RuntimeError(
                                    f"{file_type}大小不匹配: "
                                    f"预期 {total_size / (1024*1024):.1f}MB, "
                                    f"实际 {actual_size / (1024*1024):.1f}MB"
                                )
                        
                        # 重命名为正式文件
                        temp_path.replace(file_path)
                        downloaded_files.append(file_path)
                        
                        logger.info(f"✓ {file_type}下载完成: {file_path.name}")
                    
                except Exception as e:
                    if temp_path.exists():
                        temp_path.unlink()
                    raise RuntimeError(f"下载{file_type}失败: {e}")
            
            if progress_callback:
                progress_callback(1.0, "下载完成!")
            
            return model_path, tokens_path
            
        except Exception as e:
            # 删除本次下载的所有文件（保留之前已存在的文件）
            for file_path in downloaded_files:
                if file_path.exists():
                    try:
                        file_path.unlink()
                        logger.warning(f"已删除不完整的文件: {file_path.name}")
                    except:
                        pass
            raise RuntimeError(f"下载 SenseVoice 模型失败: {e}")
    
    def load_model(
        self, 
        encoder_path: Path,
        decoder_path: Path,
        config_path: Optional[Path] = None,
        use_gpu: bool = True,
        gpu_device_id: int = 0,
        gpu_memory_limit: int = 8192,
        enable_memory_arena: bool = True,
        language: str = "auto",
        task: str = "transcribe"
    ) -> None:
        """加载 ONNX 模型（使用 sherpa-onnx）。
        
        Args:
            encoder_path: 编码器模型文件路径
            decoder_path: 解码器模型文件路径
            config_path: 配置文件路径（可选，sherpa-onnx 会使用 tokens.txt）
            use_gpu: 是否使用GPU加速
            gpu_device_id: GPU设备ID
            gpu_memory_limit: GPU内存限制（MB）
            enable_memory_arena: 是否启用内存池优化
            language: 识别语言（"auto" 自动检测，或 "zh", "en" 等）
            task: 任务类型（"transcribe" 转录，"translate" 翻译为英文）
        """
        try:
            import sherpa_onnx
        except ImportError:
            raise RuntimeError(
                "sherpa-onnx 未安装。\n"
                "请运行: pip install sherpa-onnx"
            )
        
        if not encoder_path.exists():
            raise FileNotFoundError(f"编码器模型文件不存在: {encoder_path}")
        if not decoder_path.exists():
            raise FileNotFoundError(f"解码器模型文件不存在: {decoder_path}")
        
        # 查找 tokens 文件（sherpa-onnx whisper 需要）
        # 优先使用 config_path（传入的正确路径），如果为 None 则尝试查找
        if config_path and config_path.exists():
            tokens_path = config_path
        else:
            # 回退到查找通用名称
            tokens_path = encoder_path.parent / "tokens.txt"
            if not tokens_path.exists():
                # 尝试查找带模型名称的 tokens 文件（如 tiny-tokens.txt）
                for file in encoder_path.parent.glob("*tokens*.txt"):
                    tokens_path = file
                    break
        
        # tokens 文件是必需的，如果找不到则抛出错误
        if not tokens_path.exists():
            raise FileNotFoundError(
                f"tokens 文件未找到: {tokens_path}\n"
                f"请确保 tokens 文件与模型文件在同一目录下。\n"
                f"尝试查找的路径: {encoder_path.parent}\n"
                f"缺少 tokens 文件会导致识别效果差、漏字等问题。"
            )
        
        tokens_str = str(tokens_path)
        logger.info(f"使用 tokens 文件: {tokens_path.name}")
        
        # 构建 sherpa-onnx 配置
        # 配置执行提供者
        provider = "cpu"
        if use_gpu:
            try:
                import onnxruntime as ort
                import platform
                available_providers = ort.get_available_providers()
                
                if 'CUDAExecutionProvider' in available_providers:
                    provider = "cuda"
                    logger.info(f"语音识别使用 CUDA GPU (设备 {gpu_device_id})")
                    logger.warning("⚠️ 由于 sherpa-onnx 适配问题，当前工具使用 CUDA 后，可能需要重启程序才能正常使用其他 ONNX 模型")
                elif 'CoreMLExecutionProvider' in available_providers and platform.system() == 'Darwin':
                    provider = "coreml"
                    logger.info("语音识别使用 CoreML (Apple Silicon)")
                else:
                    logger.info("语音识别使用 CPU (GPU 不可用)")
            except ImportError:
                logger.warning("onnxruntime 未安装，使用 CPU")
        
        # 将语言代码转换为 sherpa-onnx 支持的格式
        # auto 时使用空字符串让模型自动检测，或者指定具体语言
        if language == "auto":
            lang_code = ""  # 空字符串表示自动检测语言
        else:
            lang_code = language
        
        # 获取可用的 CPU 线程数，最多使用 8 个线程
        import os
        num_threads = min(os.cpu_count() or 4, 8)
        
        # 创建识别器
        try:
            # 使用 from_whisper 工厂方法创建识别器
            # 这是官方推荐的方式，而不是直接实例化 OfflineRecognizer
            # 参考：https://github.com/k2-fsa/sherpa-onnx/blob/master/sherpa-onnx/python/sherpa_onnx/offline_recognizer.py
            self.recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
                encoder=str(encoder_path),
                decoder=str(decoder_path),
                tokens=tokens_str,
                language=lang_code,
                task=task,
                num_threads=num_threads,
                debug=self.debug_mode,  # 调试模式：输出详细的识别过程
                provider=provider,
                tail_paddings=1500,  # 尾部填充：增加到1500以确保音频末尾不被截断（默认800）
                decoding_method="greedy_search",  # 使用贪婪搜索，更稳定
            )
            self.current_model = encoder_path.stem
            self.current_provider = provider
            
            logger.info(
                f"Whisper模型已加载: {encoder_path.name} + {decoder_path.name}, "
                f"执行提供者: {provider.upper()}"
            )
        except Exception as e:
            error_msg = str(e)
            if "version" in error_msg.lower() and "not supported" in error_msg.lower():
                raise RuntimeError(
                    f"模型版本不兼容: {error_msg}\n\n"
                )
            raise RuntimeError(f"加载模型失败: {e}")
    
    def load_sensevoice_model(
        self,
        model_path: Path,
        tokens_path: Path,
        use_gpu: bool = True,
        gpu_device_id: int = 0,
        language: str = "auto",
        model_type: str = "sensevoice"
    ) -> None:
        """加载 SenseVoice/Paraformer 模型（使用 sherpa-onnx）。
        
        支持两种模型文件：
        - model.onnx: FP32 完整版（高精度，需要 onnxruntime 支持 opset 17）
        - model.int8.onnx: INT8 量化版（兼容性好，支持标准 onnxruntime）
        
        Args:
            model_path: 模型文件路径（model.onnx 或 model.int8.onnx）
            tokens_path: tokens.txt 文件路径
            use_gpu: 是否使用GPU加速
            gpu_device_id: GPU设备ID
            language: 识别语言（"auto" 自动检测，或 "zh", "en" 等）
            model_type: 模型类型（"sensevoice" 或 "paraformer"）
        """
        try:
            import sherpa_onnx
        except ImportError:
            raise RuntimeError(
                "sherpa-onnx 未安装。\n"
                "请运行: pip install sherpa-onnx"
            )
        
        if not model_path.exists():
            raise FileNotFoundError(f"模型文件不存在: {model_path}")
        if not tokens_path.exists():
            raise FileNotFoundError(f"tokens 文件不存在: {tokens_path}")
        
        # 配置执行提供者
        provider = "cpu"
        if use_gpu:
            try:
                import onnxruntime as ort
                import platform
                available_providers = ort.get_available_providers()
                
                if 'CUDAExecutionProvider' in available_providers:
                    provider = "cuda"
                    logger.info(f"语音识别使用 CUDA GPU (设备 {gpu_device_id})")
                else:
                    logger.info("语音识别使用 CPU (GPU 不可用)")
            except ImportError:
                logger.warning("onnxruntime 未安装，使用 CPU")
        
        # 根据模型类型创建识别器
        try:
            num_threads = min(os.cpu_count() or 4, 8)
            
            if model_type == "paraformer":
                # 加载 Paraformer 模型
                self.recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(
                    paraformer=str(model_path),
                    tokens=str(tokens_path),
                    num_threads=num_threads,
                    debug=self.debug_mode,
                    provider=provider,
                )
                model_name = "Paraformer"
            else:
                # 加载 SenseVoice 模型
                self.recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                    model=str(model_path),
                    tokens=str(tokens_path),
                    num_threads=num_threads,
                    debug=self.debug_mode,
                    provider=provider,
                    use_itn=True,  # 使用逆文本规范化（数字、日期等）
                    language=language if language != "auto" else "",
                )
                model_name = "SenseVoice"
            
            self.current_model = model_path.stem
            self.model_type = model_type
            self.current_provider = provider
            
            logger.info(
                f"{model_name}模型已加载: {model_path.name}, "
                f"执行提供者: {provider.upper()}"
            )
        except Exception as e:
            raise RuntimeError(f"加载SenseVoice模型失败: {e}")
    
    def load_punctuation_model(
        self,
        model_path: Path,
        use_gpu: bool = False,
        num_threads: int = 4
    ) -> None:
        """加载标点恢复模型。
        
        Args:
            model_path: 模型目录路径（包含 model.onnx 或 model.int8.onnx）
            use_gpu: 是否使用 GPU
            num_threads: CPU 线程数
        """
        try:
            import sherpa_onnx
            
            # 检查模型目录是否存在
            if not model_path.exists():
                raise FileNotFoundError(f"标点恢复模型目录不存在: {model_path}")
            
            # 检查模型文件是否存在（支持多种命名）
            model_file = None
            for name in ["model.int8.onnx", "model.onnx"]:
                candidate = model_path / name
                if candidate.exists():
                    model_file = candidate
                    break
            
            if not model_file:
                files = list(model_path.glob("*.onnx"))
                if files:
                    model_file = files[0]
                else:
                    raise FileNotFoundError(f"标点恢复模型文件不存在于: {model_path}")
            
            # 确定执行提供者
            if use_gpu:
                provider = "cuda"
            else:
                provider = "cpu"
            
            # 创建模型配置 - sherpa-onnx 期望的是完整的模型文件路径（包含 .onnx 文件）
            # 使用正斜杠确保跨平台兼容性
            model_file_str = str(model_file).replace("\\", "/")
            model_config = sherpa_onnx.OfflinePunctuationModelConfig(
                ct_transformer=model_file_str,
                num_threads=num_threads,
                debug=self.debug_mode,
                provider=provider
            )
            
            # 创建配置
            config = sherpa_onnx.OfflinePunctuationConfig(model=model_config)
            
            # 验证配置
            if not config.validate():
                # 列出目录内容帮助调试
                files_in_dir = list(model_path.iterdir()) if model_path.exists() else []
                logger.error(f"模型目录内容: {[f.name for f in files_in_dir]}")
                raise RuntimeError(f"标点恢复模型配置无效，请确保目录包含正确的模型文件: {model_path}")
            
            # 创建标点恢复器
            self.punctuator = sherpa_onnx.OfflinePunctuation(config=config)
            self.punctuation_model_path = model_path
            
            logger.info(f"标点恢复模型已加载: {model_path.name}, 执行提供者: {provider.upper()}")
            
        except Exception as e:
            logger.error(f"加载标点恢复模型失败: {e}")
            self.punctuator = None
            raise RuntimeError(f"加载标点恢复模型失败: {e}")
    
    def is_punctuation_model_loaded(self) -> bool:
        """检查标点恢复模型是否已加载。
        
        Returns:
            是否已加载
        """
        return self.punctuator is not None
    
    def add_punctuation(self, text: str) -> str:
        """为文本添加标点符号。
        
        Args:
            text: 输入文本（可能无标点）
            
        Returns:
            带标点的文本
        """
        if not text or not text.strip():
            return text
        
        if not self.is_punctuation_model_loaded():
            logger.debug("标点恢复模型未加载，跳过标点恢复")
            return text
        
        try:
            # 先去除原有标点，避免重复
            clean_text = self._remove_punctuation(text.strip())
            if not clean_text:
                return text
            
            # 调用标点恢复模型
            result = self.punctuator.add_punctuation(clean_text)
            
            # 去除可能的重复标点
            result = self._clean_duplicate_punctuation(result)
            
            return result
        except Exception as e:
            logger.warning(f"标点恢复失败: {e}")
            return text
    
    def _remove_punctuation(self, text: str) -> str:
        """去除文本中的标点符号。
        
        Args:
            text: 输入文本
            
        Returns:
            去除标点后的文本
        """
        import re
        # 中英文标点
        punctuation = r'[。！？!?，,、；;：:…．.～~·]'
        return re.sub(punctuation, '', text)
    
    def _clean_duplicate_punctuation(self, text: str) -> str:
        """清理文本中的重复标点符号。
        
        Args:
            text: 输入文本
            
        Returns:
            清理后的文本
        """
        import re
        
        if not text:
            return text
        
        # 去除连续重复的标点（如 。。 -> 。，，，-> ，）
        text = re.sub(r'([。！？!?，,、；;：:…])\1+', r'\1', text)
        
        # 去除标点后紧跟不同标点的情况（如 。，-> 。，？。 -> ？）
        # 保留更强的标点（句号 > 逗号）
        text = re.sub(r'[。！？!?][，,、]', lambda m: m.group(0)[0], text)
        text = re.sub(r'[，,、][。！？!?]', lambda m: m.group(0)[-1], text)
        
        # 去除开头的标点
        text = re.sub(r'^[。！？!?，,、；;：:…]+', '', text)
        
        return text
    
    def should_add_punctuation(self) -> bool:
        """判断是否需要对识别结果添加标点恢复。
        
        Returns:
            是否需要添加标点（用户启用且模型已加载时返回 True）
        """
        # 所有模型都支持标点恢复功能
        # - Paraformer 模型不输出标点，强烈建议启用
        # - SenseVoice 和 Whisper 自带标点，但启用后可优化标点质量
        return self.use_punctuation and self.is_punctuation_model_loaded()
    
    def add_punctuation_to_segments(
        self,
        segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """为分段结果添加标点符号。
        
        用于 SenseVoice 等有真实时间戳的场景，对每个分段单独做标点恢复。
        对于 Whisper 等场景，应在分段前对完整文本做标点恢复。
        
        Args:
            segments: 分段结果列表
            
        Returns:
            添加标点后的分段结果
        """
        if not segments or not self.should_add_punctuation():
            return segments
        
        if not self.is_punctuation_model_loaded():
            logger.debug("标点恢复模型未加载，跳过标点恢复")
            return segments
        
        # 为每个分段单独添加标点
        for segment in segments:
            if 'text' in segment and segment['text']:
                segment['text'] = self.add_punctuation(segment['text'])
        
        return segments
    
    def _load_audio_ffmpeg(self, audio_path: Path) -> np.ndarray:
        """使用 ffmpeg 加载音频。
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            音频数据 (samples,) 单声道16kHz float32
        """
        try:
            import ffmpeg
            
            if not audio_path.exists():
                raise FileNotFoundError(f"音频文件不存在: {audio_path}")
            
            # 设置 ffmpeg 环境
            self._setup_ffmpeg_env()
            
            # 获取 ffmpeg 命令
            ffmpeg_cmd = self._get_ffmpeg_cmd()
            
            # 使用 ffmpeg-python 读取音频为 PCM 数据
            # Whisper/sherpa-onnx 需要单声道 16kHz float32
            stream = ffmpeg.input(str(audio_path))
            
            # 音频预处理：转换为单声道 16kHz
            # 注意：不使用 loudnorm 等滤镜，避免改变音频特征导致识别不准
            stream = ffmpeg.output(stream, 'pipe:', format='f32le', acodec='pcm_f32le', ac=1, ar=str(self.sample_rate))
            
            out, err = ffmpeg.run(stream, cmd=ffmpeg_cmd, capture_stdout=True, capture_stderr=True)
            
            if not out:
                error_msg = err.decode('utf-8', errors='ignore') if err else "未知错误"
                raise RuntimeError(f"FFmpeg 未返回音频数据: {error_msg}")
            
            # 转换为 numpy 数组
            audio = np.frombuffer(out, np.float32)
            
            if audio.size == 0:
                raise RuntimeError("音频数据为空")
            
            return audio
            
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)
            raise RuntimeError(f"FFmpeg 加载音频失败: {error_msg}")
        except Exception as e:
            raise RuntimeError(f"加载音频时出错: {type(e).__name__}: {str(e)}")
    
    def _merge_segments_text(self, segments: List[str]) -> str:
        """智能合并多个文本片段（中文直接连接，英文用空格）。
        
        Args:
            segments: 文本片段列表
            
        Returns:
            合并后的文本
        """
        if not segments:
            return ""
        
        if len(segments) == 1:
            return segments[0]
        
        # 检查第一个片段是否主要是中文
        first_segment = segments[0]
        # 计算中文字符占比
        chinese_chars = sum(1 for c in first_segment if '\u4e00' <= c <= '\u9fff')
        total_chars = len(first_segment.replace(' ', '').replace('\n', ''))
        
        if total_chars > 0 and chinese_chars / total_chars > 0.3:
            # 中文为主：直接连接，但在片段之间可能需要标点
            merged = []
            for i, seg in enumerate(segments):
                seg = seg.strip()
                if not seg:
                    continue
                
                # 如果前一个片段没有结束标点，且当前片段不是以标点开头，添加逗号
                if merged and not merged[-1][-1] in '。！？，、；：,.!?;:':
                    if seg[0] not in '。！？，、；：,.!?;:':
                        merged[-1] = merged[-1] + '，'
                
                merged.append(seg)
            
            return ''.join(merged)
        else:
            # 英文为主：用空格连接
            return ' '.join(seg.strip() for seg in segments if seg.strip())
    
    def _is_hallucination(self, text: str) -> bool:
        """检测文本是否为幻觉输出（重复字符、异常语言等）。
        
        Args:
            text: 待检测文本
            
        Returns:
            是否为幻觉输出
        """
        if not text or len(text.strip()) < 2:
            return True
        
        text = text.strip()
        
        # 检测高度重复字符（如 ooooo, aaaaa, 阿拉伯语重复等）
        # 如果某个字符重复超过总长度的 60%，认为是幻觉
        from collections import Counter
        char_counts = Counter(text.replace(' ', ''))
        if char_counts:
            most_common_char, count = char_counts.most_common(1)[0]
            total_chars = sum(char_counts.values())
            if total_chars > 0 and count / total_chars > 0.6:
                return True
        
        # 检测主要由非 CJK/拉丁字符组成（如阿拉伯语、韩语重复）
        # 统计 CJK + 拉丁 + 数字 + 常用标点的占比
        normal_chars = 0
        for c in text:
            if (
                '\u4e00' <= c <= '\u9fff'  # CJK
                or '\u3040' <= c <= '\u30ff'  # 日文
                or 'a' <= c.lower() <= 'z'  # 拉丁
                or '0' <= c <= '9'  # 数字
                or c in ' ,.!?;:，。！？；：、""''（）()[]【】'  # 常用标点
            ):
                normal_chars += 1
        
        if len(text) > 0 and normal_chars / len(text) < 0.3:
            return True
        
        return False
    
    def _filter_hallucination_segments(
        self,
        segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """过滤掉幻觉输出的分段。
        
        Args:
            segments: 分段列表
            
        Returns:
            过滤后的分段列表
        """
        filtered = []
        for seg in segments:
            text = seg.get('text', '')
            if not self._is_hallucination(text):
                filtered.append(seg)
            else:
                logger.debug(f"过滤幻觉输出: {text[:50]}...")
        
        if len(filtered) < len(segments):
            logger.info(f"已过滤 {len(segments) - len(filtered)} 个幻觉分段")
        
        return filtered
    
    def _recognize_audio_chunk(self, audio_chunk: np.ndarray) -> str:
        """识别单个音频片段（内部方法）。
        
        Args:
            audio_chunk: 音频数据（不超过 30 秒）
            
        Returns:
            识别的文字内容
        """
        import sherpa_onnx
        
        try:
            # 创建离线音频流
            stream = self.recognizer.create_stream()
            
            # 接受音频样本
            stream.accept_waveform(self.sample_rate, audio_chunk)
            
            # 解码
            self.recognizer.decode_stream(stream)
            
            # 获取结果
            result = stream.result
            return result.text.strip()
            
        except Exception as e:
            error_msg = str(e)
            
            # 处理已知的 sherpa-onnx 异常
            if "invalid expand shape" in error_msg.lower():
                logger.warning(
                    f"音频片段处理异常（可能音频质量问题）: {error_msg}\n"
                    f"跳过此片段，继续处理..."
                )
                return ""  # 返回空字符串，继续处理其他片段
            
            # 其他未知异常，向上抛出
            raise RuntimeError(f"音频片段识别失败: {error_msg}")

    def _postprocess_vad_segments(
        self,
        segments: List[Tuple[float, float]],
        min_segment_duration: float = 1.0,
        merge_gap: float = 0.6,
        max_segment_duration: float = 28.0,
    ) -> List[Tuple[float, float]]:
        """对 VAD 输出的片段做二次合并，避免过短片段导致识别率下降。"""
        if not segments:
            return []

        segments = sorted(segments, key=lambda x: x[0])
        merged: List[Tuple[float, float]] = []

        cur_start, cur_end = segments[0]
        for start, end in segments[1:]:
            if end <= start:
                continue
            gap = start - cur_end
            cur_dur = cur_end - cur_start
            next_dur = end - start
            combined_dur = end - cur_start

            should_merge = (
                gap <= merge_gap
                and combined_dur <= max_segment_duration
                and (cur_dur < min_segment_duration or next_dur < min_segment_duration)
            )

            if should_merge:
                cur_end = end
            else:
                merged.append((cur_start, cur_end))
                cur_start, cur_end = start, end

        merged.append((cur_start, cur_end))
        return merged
    
    def _recognize_with_vad(
        self,
        audio: np.ndarray,
        audio_duration: float,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> str:
        """使用 VAD 智能分片进行识别（内部方法）。
        
        Args:
            audio: 完整音频数据
            audio_duration: 音频时长（秒）
            progress_callback: 进度回调函数
            
        Returns:
            识别的文字内容
        """
        if progress_callback:
            progress_callback("正在检测语音活动...", 0.15)
        
        # 使用 VAD 检测语音片段
        segments = self.vad_service.detect_speech_segments(audio)
        
        if not segments:
            logger.warning("VAD 未检测到语音片段")
            return "[未识别到语音内容]"
        
        # 合并相邻短片段，确保不超过 28 秒
        merged_segments = self.vad_service.merge_short_segments(
            segments, 
            max_segment_duration=28.0,
            min_gap=0.5
        )

        # 二次合并过短片段，避免过短导致识别率下降
        merged_segments = self._postprocess_vad_segments(
            merged_segments,
            min_segment_duration=1.0,
            merge_gap=0.6,
            max_segment_duration=28.0,
        )
        
        logger.info(
            f"VAD 智能分片：{len(merged_segments)} 个片段 "
            f"（原 {len(segments)} 个语音段）"
        )
        
        # 获取音频块
        audio_chunks = self.vad_service.get_audio_chunks(audio, merged_segments, padding=0.3)
        
        results = []
        num_chunks = len(audio_chunks)
        
        for i, (chunk, start_time, end_time) in enumerate(audio_chunks):
            if progress_callback:
                progress = 0.2 + (i / num_chunks) * 0.7
                progress_callback(
                    f"识别片段 {i+1}/{num_chunks} ({start_time:.1f}s - {end_time:.1f}s)...",
                    progress
                )
            
            chunk_text = self._recognize_audio_chunk(chunk)
            if chunk_text:
                results.append(chunk_text)
                logger.info(f"VAD 片段 {i+1}/{num_chunks} 识别完成: {len(chunk_text)} 字符")
            else:
                logger.info(f"VAD 片段 {i+1}/{num_chunks} 识别为空")
        
        if progress_callback:
            progress_callback("合并结果...", 0.95)
        
        if not results:
            logger.warning("VAD 分片识别结果为空，回退到固定分片识别")
            return self._recognize_with_fixed_chunks(audio, audio_duration, progress_callback)
        
        # 智能合并文本
        full_text = self._merge_segments_text(results)

        # 如果 VAD 输出文本过短，回退固定分片（避免 VAD 把内容“吃掉”）
        min_len = 5 if audio_duration <= 60 else 30
        if audio_duration > 28.0 and len(full_text.strip()) < min_len:
            logger.warning(
                f"VAD 识别文本过短（{len(full_text.strip())} 字符），回退到固定分片识别"
            )
            fallback_text = self._recognize_with_fixed_chunks(audio, audio_duration, progress_callback)
            if len(fallback_text.strip()) > len(full_text.strip()):
                return fallback_text
        
        if progress_callback:
            progress_callback("完成!", 1.0)
        
        logger.info(f"VAD 识别完成，{len(results)} 个片段，{len(full_text)} 字符")
        return full_text

    def _recognize_with_fixed_chunks(
        self,
        audio: np.ndarray,
        audio_duration: float,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> str:
        """Whisper 长音频的固定分片识别（作为 VAD 的回退路径）。"""
        max_chunk_duration = 28.0
        chunk_samples = int(max_chunk_duration * self.sample_rate)
        num_chunks = int(np.ceil(len(audio) / chunk_samples))

        logger.info(
            f"回退固定分片：音频时长 {audio_duration:.1f} 秒，"
            f"分成 {num_chunks} 个片段进行识别"
        )

        results: List[str] = []
        for i in range(num_chunks):
            start_idx = i * chunk_samples
            end_idx = min((i + 1) * chunk_samples, len(audio))
            chunk = audio[start_idx:end_idx]

            chunk_start_time = start_idx / self.sample_rate
            chunk_end_time = end_idx / self.sample_rate

            if progress_callback:
                progress = 0.2 + (i / max(num_chunks, 1)) * 0.7
                progress_callback(
                    f"识别片段 {i+1}/{num_chunks} ({chunk_start_time:.1f}s - {chunk_end_time:.1f}s)...",
                    progress,
                )

            chunk_text = self._recognize_audio_chunk(chunk)
            if chunk_text:
                results.append(chunk_text)

        if progress_callback:
            progress_callback("合并结果...", 0.95)

        if not results:
            return "[未识别到语音内容]"

        full_text = self._merge_segments_text(results)
        if progress_callback:
            progress_callback("完成!", 1.0)
        return full_text
    
    def _recognize_with_vad_timestamps(
        self,
        audio: np.ndarray,
        audio_duration: float,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> List[Dict[str, Any]]:
        """使用 VAD 智能分片进行识别并返回带时间戳的结果（内部方法）。
        
        Args:
            audio: 完整音频数据
            audio_duration: 音频时长（秒）
            progress_callback: 进度回调函数
            
        Returns:
            分段结果列表
        """
        if progress_callback:
            progress_callback("正在检测语音活动...", 0.15)
        
        # 使用 VAD 检测语音片段
        vad_segments = self.vad_service.detect_speech_segments(audio)
        
        if not vad_segments:
            logger.warning("VAD 未检测到语音片段")
            return []
        
        # 合并相邻短片段，确保不超过 28 秒
        merged_segments = self.vad_service.merge_short_segments(
            vad_segments, 
            max_segment_duration=28.0,
            min_gap=0.5
        )

        merged_segments = self._postprocess_vad_segments(
            merged_segments,
            min_segment_duration=1.0,
            merge_gap=0.6,
            max_segment_duration=28.0,
        )
        
        logger.info(
            f"VAD 智能分片：{len(merged_segments)} 个片段 "
            f"（原 {len(vad_segments)} 个语音段）"
        )
        
        # 获取音频块
        audio_chunks = self.vad_service.get_audio_chunks(audio, merged_segments, padding=0.3)
        
        all_segments = []
        num_chunks = len(audio_chunks)
        
        for i, (chunk, chunk_start, chunk_end) in enumerate(audio_chunks):
            chunk_duration = chunk_end - chunk_start
            
            if progress_callback:
                progress = 0.2 + (i / num_chunks) * 0.7
                progress_callback(
                    f"识别片段 {i+1}/{num_chunks} ({chunk_start:.1f}s - {chunk_end:.1f}s)...",
                    progress
                )
            
            chunk_text = self._recognize_audio_chunk(chunk)
            
            if chunk_text:
                # 先做标点恢复（对片段文本），再分段
                if self.should_add_punctuation():
                    chunk_text = self.add_punctuation(chunk_text)
                
                # 为这个片段生成带时间戳的分段
                chunk_segments = self._split_into_segments(chunk_text, chunk_duration)
                
                # 调整时间戳（加上片段的起始时间）
                for segment in chunk_segments:
                    segment['start'] += chunk_start
                    segment['end'] += chunk_start
                
                all_segments.extend(chunk_segments)
                logger.info(f"VAD 片段 {i+1}/{num_chunks} 识别完成: {len(chunk_segments)} 个分段")
            else:
                logger.info(f"VAD 片段 {i+1}/{num_chunks} 识别为空")
        
        if progress_callback:
            progress_callback("完成!", 1.0)
        
        total_text_len = sum(len((seg.get("text") or "").strip()) for seg in all_segments)
        logger.info(f"VAD 识别完成，总共 {len(all_segments)} 个分段，{total_text_len} 字符")

        # 过滤幻觉输出（重复字符、异常语言等）
        all_segments = self._filter_hallucination_segments(all_segments)
        # 处理结尾标点
        all_segments = self.process_segments_ending_punctuation(all_segments)

        # VAD 分段结果为空或文本过短时，回退固定分片生成分段（防止 VAD 导致输出几乎为空）
        if audio_duration > 28.0:
            min_len = 10 if audio_duration <= 60 else 30
            total_text_len = sum(len((seg.get("text") or "").strip()) for seg in all_segments)
            if len(all_segments) == 0:
                logger.warning("VAD 时间戳识别结果为空，回退到固定分片识别")
                segments = self._filter_hallucination_segments(
                    self._recognize_with_fixed_chunks_timestamps(audio, audio_duration, progress_callback)
                )
                return self.process_segments_ending_punctuation(segments)
            if total_text_len < min_len:
                logger.warning(
                    f"VAD 时间戳识别文本过短（{total_text_len} 字符），回退到固定分片识别"
                )
                segments = self._filter_hallucination_segments(
                    self._recognize_with_fixed_chunks_timestamps(audio, audio_duration, progress_callback)
                )
                return self.process_segments_ending_punctuation(segments)

        return all_segments

    def _recognize_with_fixed_chunks_timestamps(
        self,
        audio: np.ndarray,
        audio_duration: float,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Whisper 长音频固定分片 + 伪时间戳（作为 VAD 的回退路径）。"""
        max_chunk_duration = 28.0
        chunk_samples = int(max_chunk_duration * self.sample_rate)
        num_chunks = int(np.ceil(len(audio) / chunk_samples))

        all_segments: List[Dict[str, Any]] = []
        for i in range(num_chunks):
            start_idx = i * chunk_samples
            end_idx = min((i + 1) * chunk_samples, len(audio))
            chunk = audio[start_idx:end_idx]

            chunk_start_time = start_idx / self.sample_rate
            chunk_end_time = end_idx / self.sample_rate
            chunk_duration = (end_idx - start_idx) / self.sample_rate

            if progress_callback:
                progress = 0.2 + (i / max(num_chunks, 1)) * 0.7
                progress_callback(
                    f"识别片段 {i+1}/{num_chunks} ({chunk_start_time:.1f}s - {chunk_end_time:.1f}s)...",
                    progress,
                )

            chunk_text = self._recognize_audio_chunk(chunk)
            if chunk_text:
                # 先做标点恢复（对片段文本），再分段
                if self.should_add_punctuation():
                    chunk_text = self.add_punctuation(chunk_text)
                
                chunk_segments = self._split_into_segments(chunk_text, chunk_duration)
                for seg in chunk_segments:
                    seg["start"] += chunk_start_time
                    seg["end"] += chunk_start_time
                all_segments.extend(chunk_segments)

        if progress_callback:
            progress_callback("完成!", 1.0)
        segments = self._filter_hallucination_segments(all_segments)
        return segments
    
    def recognize(
        self,
        audio_path: Path,
        language: str = "zh",
        task: str = "transcribe",
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> str:
        """识别音频中的语音并转换为文字。
        
        注意：language 和 task 参数在此方法中不再使用，
        需要在 load_model() 或 load_sensevoice_model() 时指定。此处保留参数仅为了向后兼容。
        
        模型限制：
        - Whisper: 单次最多支持 30 秒音频，会自动分段处理
        - SenseVoice/Paraformer: 无长度限制，可直接识别任意长度音频
        
        Args:
            audio_path: 输入音频文件路径
            language: （已弃用）语言代码，请在加载模型时指定
            task: （已弃用）任务类型，请在加载模型时指定
            progress_callback: 进度回调函数 (状态消息, 进度0-1)
            
        Returns:
            识别的文字内容
        """
        if self.recognizer is None:
            raise RuntimeError("模型未加载，请先调用 load_model()")
        
        # 检查 FFmpeg 是否可用
        if self.ffmpeg_service:
            is_available, _ = self.ffmpeg_service.is_ffmpeg_available()
            if not is_available:
                raise RuntimeError(
                    "FFmpeg 未安装或不可用。\n"
                    "请在 媒体处理 -> FFmpeg终端 中安装 FFmpeg。"
                )
        
        # 加载音频
        if progress_callback:
            progress_callback("正在加载音频...", 0.1)
        
        audio = self._load_audio_ffmpeg(audio_path)
        
        # 计算音频时长（秒）
        audio_duration = len(audio) / self.sample_rate
        
        try:
            import sherpa_onnx
            
            # SenseVoice/Paraformer：可选启用 VAD（用于切静音/降噪场景）
            if self.model_type in ("sensevoice", "paraformer"):
                if self.use_vad and self.vad_service and self.vad_service.is_model_loaded():
                    result = self._recognize_with_vad(audio, audio_duration, progress_callback)
                    # 添加标点恢复（如果启用）
                    if self.should_add_punctuation() and result and result != "[未识别到语音内容]":
                        result = self.add_punctuation(result)
                    return result
                else:
                    if progress_callback:
                        progress_callback(f"正在识别语音（{audio_duration:.1f}秒）...", 0.5)
                    text = self._recognize_audio_chunk(audio)
                    if progress_callback:
                        progress_callback("完成!", 1.0)
                    # 添加标点恢复（如果启用）
                    if self.should_add_punctuation() and text:
                        text = self.add_punctuation(text)
                    return text if text else "[未识别到语音内容]"
            
            # Whisper 限制：单次最多 30 秒
            # 为了稳妥，使用 28 秒作为分段长度（留 2 秒缓冲）
            max_chunk_duration = 28.0
            chunk_samples = int(max_chunk_duration * self.sample_rate)
            
            # 如果音频短于 28 秒，直接识别
            if audio_duration <= max_chunk_duration:
                if progress_callback:
                    progress_callback("正在识别语音...", 0.5)
                
                text = self._recognize_audio_chunk(audio)
                
                if progress_callback:
                    progress_callback("完成!", 1.0)
                
                # 添加标点恢复（如果启用）
                if self.should_add_punctuation() and text:
                    text = self.add_punctuation(text)
                return text if text else "[未识别到语音内容]"
            
            # 长音频：优先使用 VAD 智能分片
            if self.use_vad and self.vad_service and self.vad_service.is_model_loaded():
                result = self._recognize_with_vad(audio, audio_duration, progress_callback)
                # 添加标点恢复（如果启用）
                if self.should_add_punctuation() and result and result != "[未识别到语音内容]":
                    result = self.add_punctuation(result)
                return result
            
            # 回退：固定时间分段识别
            # sherpa-onnx Whisper 限制：最多 30 秒，参考 https://github.com/k2-fsa/sherpa-onnx/issues/896
            num_chunks = int(np.ceil(len(audio) / chunk_samples))
            logger.info(
                f"音频时长 {audio_duration:.1f} 秒 > 28 秒，"
                f"将自动分成 {num_chunks} 个片段进行识别（固定分片）"
            )
            
            results = []
            
            for i in range(num_chunks):
                start_idx = i * chunk_samples
                end_idx = min((i + 1) * chunk_samples, len(audio))
                chunk = audio[start_idx:end_idx]
                
                chunk_start_time = start_idx / self.sample_rate
                chunk_end_time = end_idx / self.sample_rate
                
                if progress_callback:
                    progress = 0.2 + (i / num_chunks) * 0.7
                    progress_callback(
                        f"识别片段 {i+1}/{num_chunks} ({chunk_start_time:.1f}s - {chunk_end_time:.1f}s)...",
                        progress
                    )
                
                chunk_text = self._recognize_audio_chunk(chunk)
                if chunk_text:
                    results.append(chunk_text)
                    logger.info(f"片段 {i+1}/{num_chunks} 识别完成: {len(chunk_text)} 字符")
            
            if progress_callback:
                progress_callback("合并结果...", 0.95)
            
            # 合并所有片段的识别结果
            if not results:
                return "[未识别到语音内容]"
            
            # 智能合并文本（中文直接连接，英文用空格）
            full_text = self._merge_segments_text(results)
            
            # 添加标点恢复（如果启用）
            if self.should_add_punctuation() and full_text:
                full_text = self.add_punctuation(full_text)
            
            if progress_callback:
                progress_callback("完成!", 1.0)
            
            logger.info(f"识别完成，总共 {len(results)} 个片段，{len(full_text)} 字符")
            return full_text
            
        except Exception as e:
            raise RuntimeError(f"识别失败: {e}")
    
    def recognize_with_timestamps(
        self,
        audio_path: Path,
        language: str = "zh",
        task: str = "transcribe",
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> List[Dict[str, Any]]:
        """识别音频中的语音并返回带时间戳的分段结果。
        
        模型限制：
        - Whisper: 单次最多支持 30 秒音频，会自动分段处理
        - SenseVoice/Paraformer: 无长度限制，可直接识别任意长度音频
        
        Args:
            audio_path: 输入音频文件路径
            language: （已弃用）语言代码，请在加载模型时指定
            task: （已弃用）任务类型，请在加载模型时指定
            progress_callback: 进度回调函数 (状态消息, 进度0-1)
            
        Returns:
            分段结果列表，每个元素包含：
            {
                'text': str,        # 文本内容
                'start': float,     # 开始时间（秒）
                'end': float,       # 结束时间（秒）
            }
        """
        if self.recognizer is None:
            raise RuntimeError("模型未加载，请先调用 load_model()")
        
        # 检查 FFmpeg 是否可用
        if self.ffmpeg_service:
            is_available, _ = self.ffmpeg_service.is_ffmpeg_available()
            if not is_available:
                raise RuntimeError(
                    "FFmpeg 未安装或不可用。\n"
                    "请在 媒体处理 -> FFmpeg终端 中安装 FFmpeg。"
                )
        
        # 加载音频
        if progress_callback:
            progress_callback("正在加载音频...", 0.1)
        
        audio = self._load_audio_ffmpeg(audio_path)
        
        # 计算音频时长（秒）
        audio_duration = len(audio) / self.sample_rate
        
        try:
            import sherpa_onnx
            
            all_segments = []
            
            # SenseVoice/Paraformer：
            # - 默认：直接识别并获取真实时间戳
            # - 启用 VAD：改用 VAD 分片生成"近似时间戳"（按句子均分），避免 padding 重叠导致的时间戳/文本重复问题
            if self.model_type in ("sensevoice", "paraformer"):
                if self.use_vad and self.vad_service and self.vad_service.is_model_loaded():
                    logger.info("SenseVoice 启用 VAD：使用 VAD 分片生成近似时间戳")
                    return self._recognize_with_vad_timestamps(audio, audio_duration, progress_callback)
                if progress_callback:
                    progress_callback(f"正在识别语音（{audio_duration:.1f}秒）...", 0.5)
                
                # 获取字符级时间戳
                text, tokens, timestamps = self._get_sensevoice_timestamps(audio)
                
                if not text or text == "[未识别到语音内容]":
                    if progress_callback:
                        progress_callback("完成!", 1.0)
                    return []
                
                # 将字符级时间戳转换为句子级分段
                segments = self._tokens_to_segments(text, tokens, timestamps)
                
                if progress_callback:
                    progress_callback("完成!", 1.0)
                
                segments = self._filter_hallucination_segments(segments)
                # 添加标点恢复（如果启用）
                segments = self.add_punctuation_to_segments(segments)
                # 处理结尾标点
                segments = self.process_segments_ending_punctuation(segments)
                logger.info(f"识别完成，使用真实时间戳生成 {len(segments)} 个分段")
                return segments
            
            # Whisper 限制：单次最多 30 秒
            max_chunk_duration = 28.0
            chunk_samples = int(max_chunk_duration * self.sample_rate)
            
            # 如果音频短于 28 秒，直接识别
            if audio_duration <= max_chunk_duration:
                if progress_callback:
                    progress_callback("正在识别语音...", 0.5)
                
                text = self._recognize_audio_chunk(audio)
                
                if not text or text == "[未识别到语音内容]":
                    if progress_callback:
                        progress_callback("完成!", 1.0)
                    return []
                
                # 先做标点恢复（对完整文本），再分段
                if self.should_add_punctuation():
                    text = self.add_punctuation(text)
                
                # 将文本分割成句子
                segments = self._split_into_segments(text, audio_duration)
                segments = self._filter_hallucination_segments(segments)
                # 处理结尾标点
                segments = self.process_segments_ending_punctuation(segments)
                
                if progress_callback:
                    progress_callback("完成!", 1.0)
                
                return segments
            
            # 长音频：优先使用 VAD 智能分片
            if self.use_vad and self.vad_service and self.vad_service.is_model_loaded():
                return self._recognize_with_vad_timestamps(audio, audio_duration, progress_callback)
            
            # 回退：固定时间分段识别
            # sherpa-onnx Whisper 限制：最多 30 秒，参考 https://github.com/k2-fsa/sherpa-onnx/issues/896
            num_chunks = int(np.ceil(len(audio) / chunk_samples))
            logger.info(
                f"音频时长 {audio_duration:.1f} 秒 > 28 秒，"
                f"将自动分成 {num_chunks} 个片段进行识别（固定分片）"
            )
            
            for i in range(num_chunks):
                start_idx = i * chunk_samples
                end_idx = min((i + 1) * chunk_samples, len(audio))
                chunk = audio[start_idx:end_idx]
                
                chunk_start_time = start_idx / self.sample_rate
                chunk_end_time = end_idx / self.sample_rate
                chunk_duration = (end_idx - start_idx) / self.sample_rate
                
                if progress_callback:
                    progress = 0.2 + (i / num_chunks) * 0.7
                    progress_callback(
                        f"识别片段 {i+1}/{num_chunks} ({chunk_start_time:.1f}s - {chunk_end_time:.1f}s)...",
                        progress
                    )
                
                chunk_text = self._recognize_audio_chunk(chunk)
                
                if chunk_text:
                    # 先做标点恢复（对片段文本），再分段
                    if self.should_add_punctuation():
                        chunk_text = self.add_punctuation(chunk_text)
                    
                    # 为这个片段生成带时间戳的分段
                    chunk_segments = self._split_into_segments(chunk_text, chunk_duration)
                    
                    # 调整时间戳（加上片段的起始时间）
                    for segment in chunk_segments:
                        segment['start'] += chunk_start_time
                        segment['end'] += chunk_start_time
                    
                    all_segments.extend(chunk_segments)
                    logger.info(f"片段 {i+1}/{num_chunks} 识别完成: {len(chunk_segments)} 个分段")
            
            all_segments = self._filter_hallucination_segments(all_segments)
            # 处理结尾标点
            all_segments = self.process_segments_ending_punctuation(all_segments)
            
            if progress_callback:
                progress_callback("完成!", 1.0)
            
            logger.info(f"识别完成，总共 {len(all_segments)} 个分段")
            return all_segments
            
        except Exception as e:
            raise RuntimeError(f"识别失败: {e}")
    
    def _get_sensevoice_timestamps(self, audio_chunk: np.ndarray) -> tuple[str, List[str], List[float]]:
        """获取 SenseVoice 的字符级时间戳。
        
        Args:
            audio_chunk: 音频数据
            
        Returns:
            (文本, token列表, 时间戳列表)
        """
        import sherpa_onnx
        
        # 创建离线音频流
        stream = self.recognizer.create_stream()
        stream.accept_waveform(self.sample_rate, audio_chunk)
        self.recognizer.decode_stream(stream)
        
        # 获取结果
        result = stream.result
        return result.text.strip(), result.tokens, result.timestamps
    
    def _tokens_to_segments(
        self,
        text: str,
        tokens: List[str],
        timestamps: List[float],
        max_segment_length: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """将 SenseVoice 的字符级时间戳转换为句子级分段。
        
        Args:
            text: 完整文本
            tokens: 字符列表
            timestamps: 对应的时间戳列表（秒）
            max_segment_length: 每段的最大字符数，None 时使用 self.subtitle_max_length
            
        Returns:
            分段结果列表
        """
        import re
        
        if not text or not tokens or not timestamps:
            return []
        
        # 使用配置的最大长度
        if max_segment_length is None:
            max_segment_length = self.subtitle_max_length
        
        # 强分割符：句号、问号、感叹号、换行
        sentence_endings = r'[。！？!?\n]+'
        # 弱分割符：逗号、顿号、分号、冒号
        weak_endings = r'([，,、；;：:]+)'
        
        # 辅助函数：添加分段
        def add_segment(text_part: str, segments_list: list, char_idx: int) -> int:
            """添加分段并返回更新后的字符索引。"""
            if not text_part.strip():
                return char_idx
            seg_len = len(text_part)
            start_idx = char_idx
            end_idx = min(char_idx + seg_len, len(timestamps))
            
            if start_idx < len(timestamps) and end_idx <= len(timestamps):
                start_time = timestamps[start_idx] if start_idx < len(timestamps) else 0
                end_time = timestamps[end_idx - 1] if end_idx > 0 and end_idx <= len(timestamps) else start_time + 1.0
                
                segments_list.append({
                    'text': text_part.strip(),
                    'start': start_time,
                    'end': end_time,
                })
            return end_idx
        
        # 如果启用标点分段
        if self.subtitle_split_by_punctuation:
            # 先按强分割符分割
            sentences = re.split(f'({sentence_endings})', text)
            
            # 合并句子和标点
            merged_sentences = []
            i = 0
            while i < len(sentences):
                if i + 1 < len(sentences) and re.match(sentence_endings, sentences[i + 1]):
                    merged_sentences.append(sentences[i] + sentences[i + 1])
                    i += 2
                else:
                    if sentences[i].strip():
                        merged_sentences.append(sentences[i])
                    i += 1
            
            if not merged_sentences:
                merged_sentences = [text]
            
            # 为每个句子找到时间戳
            segments = []
            char_index = 0
            
            for sentence in merged_sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                
                if len(sentence) <= max_segment_length:
                    char_index = add_segment(sentence, segments, char_index)
                else:
                    # 按弱分割符进一步分割
                    parts = re.split(weak_endings, sentence)
                    
                    # 收集所有可能的断点（标点位置）
                    segments_with_punct = []
                    current_segment = ""
                    
                    for part in parts:
                        if re.match(weak_endings, part):
                            current_segment += part
                            segments_with_punct.append((current_segment, True))
                            current_segment = ""
                        else:
                            current_segment += part
                    
                    if current_segment:
                        segments_with_punct.append((current_segment, False))
                    
                    # 智能合并：尽量在接近但不超过最大长度的标点处断开
                    current_part = ""
                    for segment_text, can_break in segments_with_punct:
                        if len(current_part + segment_text) <= max_segment_length:
                            current_part += segment_text
                        else:
                            if current_part.strip():
                                char_index = add_segment(current_part, segments, char_index)
                            
                            if len(segment_text) > max_segment_length:
                                for k in range(0, len(segment_text), max_segment_length):
                                    chunk = segment_text[k:k + max_segment_length]
                                    char_index = add_segment(chunk, segments, char_index)
                                current_part = ""
                            else:
                                current_part = segment_text
                    
                    if current_part.strip():
                        char_index = add_segment(current_part, segments, char_index)
        else:
            # 不按标点分段，仅按字数强制分割
            segments = []
            char_index = 0
            for k in range(0, len(text), max_segment_length):
                chunk = text[k:k + max_segment_length]
                char_index = add_segment(chunk, segments, char_index)
        
        return segments
    
    def _split_into_segments(
        self, 
        text: str, 
        audio_duration: float,
        max_segment_length: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """将长文本分割成带时间戳的段落（估算方法，用于 Whisper）。
        
        Args:
            text: 识别的完整文本
            audio_duration: 音频总时长（秒）
            max_segment_length: 每段的最大字符数，None 时使用 self.subtitle_max_length
            
        Returns:
            分段结果列表
        """
        import re
        
        # 使用配置的最大长度
        if max_segment_length is None:
            max_segment_length = self.subtitle_max_length
        
        # 强分割符：句号、问号、感叹号、换行
        sentence_endings = r'[。！？!?\n]+'
        # 弱分割符：逗号、顿号、分号、冒号
        weak_endings = r'([，,、；;：:]+)'
        
        # 如果启用标点分段，优先在标点处断开
        if self.subtitle_split_by_punctuation:
            # 先按强分割符分割
            sentences = re.split(f'({sentence_endings})', text)
            
            # 合并句子和标点
            merged_sentences = []
            i = 0
            while i < len(sentences):
                if i + 1 < len(sentences) and re.match(sentence_endings, sentences[i + 1]):
                    merged_sentences.append(sentences[i] + sentences[i + 1])
                    i += 2
                else:
                    if sentences[i].strip():
                        merged_sentences.append(sentences[i])
                    i += 1
            
            if not merged_sentences:
                merged_sentences = [text]
            
            # 对每个句子进行进一步分割
            final_segments = []
            
            for sentence in merged_sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                
                # 如果句子长度在限制内，直接添加
                if len(sentence) <= max_segment_length:
                    final_segments.append(sentence)
                    continue
                
                # 按弱分割符（逗号等）分割
                parts = re.split(weak_endings, sentence)
                
                # 收集所有可能的断点（标点位置）
                segments_with_punct = []
                current_segment = ""
                
                for part in parts:
                    if re.match(weak_endings, part):
                        # 标点符号：附加并标记为可断点
                        current_segment += part
                        segments_with_punct.append((current_segment, True))  # (文本, 是否可断)
                        current_segment = ""
                    else:
                        current_segment += part
                
                # 处理末尾没有标点的部分
                if current_segment:
                    segments_with_punct.append((current_segment, False))
                
                # 智能合并：尽量在接近但不超过最大长度的标点处断开
                current_part = ""
                for segment_text, can_break in segments_with_punct:
                    # 尝试追加这个片段
                    if len(current_part + segment_text) <= max_segment_length:
                        current_part += segment_text
                    else:
                        # 追加后会超长
                        if current_part.strip():
                            # 先保存当前累积的部分
                            final_segments.append(current_part.strip())
                        
                        # 如果这个片段本身就超长，强制按字数分割
                        if len(segment_text) > max_segment_length:
                            for k in range(0, len(segment_text), max_segment_length):
                                chunk = segment_text[k:k + max_segment_length].strip()
                                if chunk:
                                    final_segments.append(chunk)
                            current_part = ""
                        else:
                            current_part = segment_text
                
                # 处理剩余部分
                if current_part.strip():
                    final_segments.append(current_part.strip())
        else:
            # 不按标点分段，仅按字数强制分割
            final_segments = []
            for k in range(0, len(text), max_segment_length):
                chunk = text[k:k + max_segment_length].strip()
                if chunk:
                    final_segments.append(chunk)
        
        # 合并过短的分段（少于5个字符且不是完整句子）
        optimized_segments = []
        min_merge_length = min(5, max_segment_length // 4)
        
        for seg in final_segments:
            if optimized_segments and len(seg) < min_merge_length and not seg.endswith(('。', '！', '？', '!', '?')):
                last_seg = optimized_segments[-1]
                if not last_seg.endswith(('。', '！', '？', '!', '?')) and len(last_seg + seg) <= max_segment_length:
                    optimized_segments[-1] = last_seg + seg
                    continue
            optimized_segments.append(seg)
        
        final_segments = optimized_segments if optimized_segments else final_segments
        
        # 为每个段落分配时间戳
        total_chars = sum(len(seg) for seg in final_segments)
        
        segments = []
        current_time = 0.0
        
        for segment_text in final_segments:
            char_ratio = len(segment_text) / total_chars if total_chars > 0 else 1.0
            segment_duration = audio_duration * char_ratio
            segment_duration = max(0.5, min(segment_duration, audio_duration - current_time))
            
            segments.append({
                'text': segment_text,
                'start': current_time,
                'end': current_time + segment_duration,
            })
            
            current_time += segment_duration
        
        return segments
    
    def cleanup(self) -> None:
        """清理资源。"""
        if self.recognizer:
            try:
                # 尝试正常删除
                del self.recognizer
            except Exception:
                # 忽略销毁时的任何错误（包括日志管理器错误）
                pass
            finally:
                self.recognizer = None
    
    def __del__(self):
        """析构函数：确保对象销毁时清理资源。"""
        try:
            self.cleanup()
        except Exception:
            # 忽略析构时的任何错误
            pass
    
    def unload_model(self) -> None:
        """卸载当前模型并释放推理会话。"""
        self.cleanup()
        self.current_model = None
        self.current_provider = "未加载"
    
    def get_device_info(self) -> str:
        """获取当前使用的设备信息。
        
        Returns:
            设备信息字符串
        """
        if not self.recognizer:
            return "未加载"
        
        # 返回提供者信息
        if self.current_provider == "cuda":
            return "NVIDIA GPU (CUDA)"
        elif self.current_provider == "coreml":
            return "Apple GPU (CoreML)"
        elif self.current_provider == "directml":
            return "DirectML GPU"
        elif self.current_provider == "cpu":
            return "CPU"
        else:
            return self.current_provider.upper()
    
    def set_vad_service(self, vad_service: 'VADService') -> None:
        """设置 VAD 服务。
        
        Args:
            vad_service: VAD 服务实例
        """
        self.vad_service = vad_service
    
    def set_use_vad(self, use_vad: bool) -> None:
        """设置是否使用 VAD 智能分片。
        
        Args:
            use_vad: 是否使用 VAD
        """
        self.use_vad = use_vad
    
    def is_vad_available(self) -> bool:
        """检查 VAD 是否可用。
        
        Returns:
            VAD 是否可用
        """
        return (
            self.vad_service is not None 
            and self.vad_service.is_model_loaded()
        )
    
    def set_subtitle_settings(
        self,
        max_length: Optional[int] = None,
        split_by_punctuation: Optional[bool] = None,
        keep_ending_punctuation: Optional[bool] = None
    ) -> None:
        """设置字幕分段参数。
        
        Args:
            max_length: 每段字幕最大字符数（10-100）
            split_by_punctuation: 是否在标点处分段
            keep_ending_punctuation: 是否保留结尾标点
        """
        if max_length is not None:
            self.subtitle_max_length = max(10, min(100, max_length))
        if split_by_punctuation is not None:
            self.subtitle_split_by_punctuation = split_by_punctuation
        if keep_ending_punctuation is not None:
            self.subtitle_keep_ending_punctuation = keep_ending_punctuation
    
    def strip_ending_punctuation(self, text: str) -> str:
        """去除文本结尾的标点符号。
        
        Args:
            text: 输入文本
            
        Returns:
            去除结尾标点后的文本
        """
        if not text:
            return text
        
        # 中英文结尾标点
        ending_puncts = '。！？!?，,、；;：:…'
        
        # 从结尾开始去除标点
        while text and text[-1] in ending_puncts:
            text = text[:-1]
        
        return text
    
    def process_segments_ending_punctuation(
        self,
        segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """根据设置处理分段结尾标点，同时清理重复标点。
        
        Args:
            segments: 分段结果列表
            
        Returns:
            处理后的分段结果
        """
        if not segments:
            return segments
        
        for segment in segments:
            if 'text' in segment and segment['text']:
                # 先清理重复标点和开头标点
                segment['text'] = self._clean_duplicate_punctuation(segment['text'])
                
                # 如果不保留结尾标点，去除
                if not self.subtitle_keep_ending_punctuation:
                    segment['text'] = self.strip_ending_punctuation(segment['text'])
        
        return segments
