# -*- coding: utf-8 -*-
"""语音识别服务模块。

使用 sherpa-onnx 和 Whisper 模型进行语音转文字。
"""

import os
from pathlib import Path
from typing import Optional, Callable, TYPE_CHECKING
from utils import logger
import numpy as np

if TYPE_CHECKING:
    from services import FFmpegService
    from constants import WhisperModelInfo


class SpeechRecognitionService:
    """语音识别服务类。
    
    使用 sherpa-onnx Whisper 模型进行音视频转文字。
    """
    
    def __init__(
        self,
        model_dir: Optional[Path] = None,
        ffmpeg_service: Optional['FFmpegService'] = None
    ):
        """初始化语音识别服务。
        
        Args:
            model_dir: 模型存储目录，默认为用户数据目录下的 models/whisper
            ffmpeg_service: FFmpeg 服务实例
        """
        self.ffmpeg_service = ffmpeg_service
        self.model_dir = model_dir
        # 确保目录存在
        if self.model_dir:
            self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.recognizer = None
        self.current_model: Optional[str] = None
        self.sample_rate: int = 16000  # Whisper 固定使用 16kHz
        self.current_provider: str = "未加载"
        
        # 设置 ONNX Runtime DLL 搜索路径（解决 sherpa-onnx 版本冲突）
        self._setup_onnxruntime_path()
        
        # 设置 FFmpeg 环境
        self._setup_ffmpeg_env()
    
    def _setup_onnxruntime_path(self) -> None:
        """设置 ONNX Runtime 库搜索路径。
        
        解决 sherpa-onnx 可能使用错误版本 ONNX Runtime 的问题。
        通过设置 DLL 搜索路径，让系统优先加载项目依赖的 ONNX Runtime。
        """
        import sys
        import platform
        
        system = platform.system()
        
        try:
            import onnxruntime
            onnxruntime_path = Path(onnxruntime.__file__).parent
            
            # 查找库文件目录
            lib_path = onnxruntime_path / "capi"
            if not lib_path.exists():
                lib_path = onnxruntime_path
            
            if not lib_path.exists():
                return
            
            if system == "Windows":
                # Windows: 设置 DLL 搜索路径
                # Python 3.8+ 推荐使用 os.add_dll_directory
                if sys.version_info >= (3, 8):
                    try:
                        os.add_dll_directory(str(lib_path))
                        logger.info(f"ONNX Runtime DLL 目录已添加: {lib_path}")
                    except Exception as e:
                        logger.warning(f"添加 DLL 目录失败: {e}")
                
                # 同时设置 PATH 环境变量（兼容旧版本 Python）
                if str(lib_path) not in os.environ.get('PATH', ''):
                    os.environ['PATH'] = str(lib_path) + os.pathsep + os.environ.get('PATH', '')
                    logger.debug(f"ONNX Runtime 已添加到 PATH: {lib_path}")
            
            elif system == "Linux":
                # Linux: 设置 LD_LIBRARY_PATH
                ld_path = os.environ.get('LD_LIBRARY_PATH', '')
                if str(lib_path) not in ld_path:
                    os.environ['LD_LIBRARY_PATH'] = str(lib_path) + os.pathsep + ld_path
                    logger.info(f"ONNX Runtime 已添加到 LD_LIBRARY_PATH: {lib_path}")
            
            elif system == "Darwin":
                # macOS: 设置 DYLD_LIBRARY_PATH
                dyld_path = os.environ.get('DYLD_LIBRARY_PATH', '')
                if str(lib_path) not in dyld_path:
                    os.environ['DYLD_LIBRARY_PATH'] = str(lib_path) + os.pathsep + dyld_path
                    logger.info(f"ONNX Runtime 已添加到 DYLD_LIBRARY_PATH: {lib_path}")
        
        except ImportError:
            logger.debug("onnxruntime 未安装，跳过路径设置")
        except Exception as e:
            logger.warning(f"设置 ONNX Runtime 路径时出错: {e}")
    
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
    
    def load_model(
        self, 
        encoder_path: Path,
        decoder_path: Path,
        config_path: Optional[Path] = None,
        use_gpu: bool = True,
        gpu_device_id: int = 0,
        gpu_memory_limit: int = 2048,
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
        
        # 如果没有 tokens 文件，尝试使用空字符串（某些模型可能不需要）
        tokens_str = ""
        if tokens_path.exists():
            tokens_str = str(tokens_path)
            logger.info(f"使用 tokens 文件: {tokens_path.name}")
        else:
            logger.warning(f"tokens 文件未找到，将使用内置词表（可能影响识别效果）")
        
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
                elif 'CoreMLExecutionProvider' in available_providers and platform.system() == 'Darwin':
                    provider = "coreml"
                    logger.info("语音识别使用 CoreML (Apple Silicon)")
                else:
                    logger.info("语音识别使用 CPU (GPU 不可用)")
            except ImportError:
                logger.warning("onnxruntime 未安装，使用 CPU")
        
        # 将语言代码转换为 sherpa-onnx 支持的格式
        lang_code = language if language != "auto" else "en"  # 默认英文
        
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
                num_threads=4,
                debug=False,
                provider=provider,
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
                    "sherpa-onnx 需要使用特定版本的 Whisper ONNX 模型。\n"
                    "请从 https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models 下载兼容的模型。"
                )
            raise RuntimeError(f"加载模型失败: {e}")
    
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
    
    def recognize(
        self,
        audio_path: Path,
        language: str = "zh",
        task: str = "transcribe",
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> str:
        """识别音频中的语音并转换为文字。
        
        注意：language 和 task 参数在此方法中不再使用，
        需要在 load_model() 时指定。此处保留参数仅为了向后兼容。
        
        Args:
            audio_path: 输入音频文件路径
            language: （已弃用）语言代码，请在 load_model 时指定
            task: （已弃用）任务类型，请在 load_model 时指定
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
            progress_callback("正在加载音频...", 0.2)
        
        audio = self._load_audio_ffmpeg(audio_path)
        
        # 创建音频流
        if progress_callback:
            progress_callback("正在识别语音...", 0.5)
        
        try:
            import sherpa_onnx
            
            # 创建离线音频流
            stream = self.recognizer.create_stream()
            
            # 接受音频样本（对于离线识别，只需调用一次）
            stream.accept_waveform(self.sample_rate, audio)
            
            # 解码（对于离线识别器，不需要 input_finished()）
            self.recognizer.decode_stream(stream)
            
            # 获取结果
            result = stream.result
            text = result.text.strip()
            
            if progress_callback:
                progress_callback("完成!", 1.0)
            
            if not text:
                return "[未识别到语音内容]"
            
            return text
            
        except Exception as e:
            raise RuntimeError(f"识别失败: {e}")
    
    def cleanup(self) -> None:
        """清理资源。"""
        if self.recognizer:
            del self.recognizer
            self.recognizer = None
    
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
