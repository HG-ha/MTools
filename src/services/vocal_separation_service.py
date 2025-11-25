# -*- coding: utf-8 -*-
"""人声分离服务模块。

使用 ONNX Runtime 和 UVR MDX-Net 模型进行人声/伴奏分离。
"""

import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple, Callable, Union, TYPE_CHECKING

import numpy as np
import onnxruntime as ort
import ffmpeg

if TYPE_CHECKING:
    from services import FFmpegService
    from constants import ModelInfo


class VocalSeparationService:
    """人声分离服务类。
    
    使用 UVR MDX-Net ONNX 模型进行音频源分离。
    """
    
    def __init__(
        self,
        model_dir: Optional[Path] = None,
        ffmpeg_service: Optional['FFmpegService'] = None
    ):
        """初始化人声分离服务。
        
        Args:
            model_dir: 模型存储目录，默认为用户数据目录下的 models/vocal_separation
            ffmpeg_service: FFmpeg 服务实例
        """
        self.ffmpeg_service = ffmpeg_service
        self.model_dir = model_dir
        # 确保目录存在
        if self.model_dir:
            self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.session: Optional['ort.InferenceSession'] = None
        self.current_model: Optional[str] = None
        self.invert_output: bool = False  # 是否反转输出（模型输出伴奏而非人声）
        
        # 模型参数
        self.sample_rate: int = 44100  # MDX-Net 标准采样率
        self.hop_length: int = 1024
        self.n_fft: int = 6144  # MDX-Net 标准 FFT 大小
        self.chunk_size: int = 485100  # 约11秒的音频块
        self.overlap: float = 0.25  # 重叠比例
        
        # MDX-Net 补偿因子 (UVR 标准)
        # 模型输出需要除以此因子来恢复到正确的幅度
        # 1.035 是 Kim Vocal 2 等模型的标准值
        self.compensate: float = 1.035
        
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
        from constants import VOCAL_SEPARATION_MODELS
        return list(VOCAL_SEPARATION_MODELS.keys())
    
    def download_model(
        self,
        model_key: str,
        model_info: 'ModelInfo',
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Path:
        """下载模型文件。
        
        Args:
            model_key: 模型键名
            model_info: 模型信息
            progress_callback: 进度回调函数 (进度0-1, 状态消息)
            
        Returns:
            模型文件路径
        """
        import httpx
        
        model_path = self.model_dir / model_info.filename
        
        # 如果已存在，直接返回
        if model_path.exists():
            return model_path
        
        try:
            # 开始下载
            if progress_callback:
                progress_callback(0.0, "开始下载模型...")
            
            with httpx.stream("GET", model_info.url, follow_redirects=True, timeout=300.0) as response:
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(model_path, 'wb') as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if progress_callback and total_size > 0:
                                progress = downloaded / total_size
                                size_mb = downloaded / (1024 * 1024)
                                total_mb = total_size / (1024 * 1024)
                                progress_callback(
                                    progress,
                                    f"下载中: {size_mb:.1f}/{total_mb:.1f} MB"
                                )
            
            if progress_callback:
                progress_callback(1.0, "下载完成!")
            
            return model_path
            
        except Exception as e:
            # 删除不完整的文件
            if model_path.exists():
                model_path.unlink()
            raise RuntimeError(f"下载模型失败: {e}")
    
    def load_model(self, model_path: Path, invert_output: bool = False) -> None:
        """加载 ONNX 模型。
        
        Args:
            model_path: 模型文件路径
            invert_output: 是否反转输出 (True=模型输出伴奏, False=模型输出人声)
        """
        if not model_path.exists():
            raise FileNotFoundError(f"模型文件不存在: {model_path}")
        
        # 设置是否反转输出
        self.invert_output = invert_output
        
        # 配置 ONNX Runtime
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        # 尝试使用 GPU
        providers = ['CPUExecutionProvider']
        if ort.get_available_providers():
            available = ort.get_available_providers()
            if 'CUDAExecutionProvider' in available:
                providers.insert(0, 'CUDAExecutionProvider')
            elif 'DmlExecutionProvider' in available:  # DirectML for Windows
                providers.insert(0, 'DmlExecutionProvider')
        
        # 创建推理会话
        self.session = ort.InferenceSession(
            str(model_path),
            sess_options=sess_options,
            providers=providers
        )
        self.current_model = model_path.name
        
        # 从模型输入获取参数
        input_shape = self.session.get_inputs()[0].shape
        # 输入格式: (batch, channels, freq_bins, time_frames)
        # channels: 通常是2(L/R)或4(实部/虚部分开)
        # freq_bins: n_fft // 2 + 1
        # time_frames: chunk大小对应的帧数
        
        self.model_channels = input_shape[1]  # 2 或 4
        self.model_freq_bins = input_shape[2]  # 如 3072
        self.model_time_frames = input_shape[3]  # 如 256
        
        # 根据频率bins计算n_fft
        # MDX-Net 模型通常使用: freq_bins = n_fft // 2 (不加1)
        # 所以 n_fft = freq_bins * 2
        self.n_fft = self.model_freq_bins * 2  # 3072 * 2 = 6144
        
        # 根据时间帧计算chunk大小
        # time_frames = chunk_samples // hop_length + 1
        # chunk_samples = (time_frames - 1) * hop_length
        self.chunk_size = (self.model_time_frames - 1) * self.hop_length
        
    
    def _load_audio_ffmpeg(self, audio_path: Path) -> np.ndarray:
        """使用 ffmpeg 加载音频。
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            音频数据 (channels, samples)
        """
        try:
            if not audio_path.exists():
                raise FileNotFoundError(f"音频文件不存在: {audio_path}")
            
            # 设置 ffmpeg 环境
            self._setup_ffmpeg_env()
            
            # 获取 ffmpeg 命令
            ffmpeg_cmd = self._get_ffmpeg_cmd()
            
            # 使用 ffmpeg-python 读取音频为 PCM 数据
            stream = ffmpeg.input(str(audio_path))
            stream = ffmpeg.output(stream, 'pipe:', format='f32le', acodec='pcm_f32le', ac=2, ar=str(self.sample_rate))
            
            out, err = ffmpeg.run(stream, cmd=ffmpeg_cmd, capture_stdout=True, capture_stderr=True)
            
            if not out:
                error_msg = err.decode('utf-8', errors='ignore') if err else "未知错误"
                raise RuntimeError(f"FFmpeg 未返回音频数据: {error_msg}")
            
            # 转换为 numpy 数组
            audio = np.frombuffer(out, np.float32).reshape(-1, 2).T
            
            if audio.size == 0:
                raise RuntimeError("音频数据为空")
            
            return audio
            
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)
            raise RuntimeError(f"FFmpeg 加载音频失败: {error_msg}")
        except Exception as e:
            raise RuntimeError(f"加载音频时出错: {type(e).__name__}: {str(e)}")
    
    def _save_audio_ffmpeg(
        self, 
        audio: np.ndarray, 
        output_path: Path, 
        output_format: str = 'wav',
        mp3_bitrate: str = '320k',
        ogg_quality: Union[int, str] = 10
    ) -> None:
        """使用 ffmpeg 保存音频。
        
        Args:
            audio: 音频数据 (channels, samples)
            output_path: 输出文件路径
            output_format: 输出格式 ('wav', 'flac', 'mp3', 'ogg')
            mp3_bitrate: MP3码率 (仅当format='mp3'时使用)
            ogg_quality: OGG质量 (仅当format='ogg'时使用, 0-10的整数)
        """
        try:
            # 确保输出目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 设置 ffmpeg 环境
            self._setup_ffmpeg_env()
            
            # 获取 ffmpeg 命令
            ffmpeg_cmd = self._get_ffmpeg_cmd()
            
            # 转置为 (samples, channels)
            audio_interleaved = audio.T
            
            # 检查音频统计信息
            max_val = np.abs(audio_interleaved).max()
            rms_val = np.sqrt(np.mean(audio_interleaved**2))

            # 归一化音频到 [-1, 1] 范围
            if max_val > 1.0:
                audio_interleaved = audio_interleaved / max_val
            
            # 转换为字节
            audio_bytes = audio_interleaved.astype(np.float32).tobytes()
            
            # 使用 ffmpeg-python 写入音频
            stream = ffmpeg.input('pipe:', format='f32le', acodec='pcm_f32le', ac=2, ar=str(self.sample_rate))
            
            # 根据输出格式设置编码参数
            if output_format == 'wav':
                stream = ffmpeg.output(stream, str(output_path), acodec='pcm_s16le', ar=str(self.sample_rate))
            elif output_format == 'flac':
                stream = ffmpeg.output(stream, str(output_path), acodec='flac', ar=str(self.sample_rate), compression_level=8)
            elif output_format == 'mp3':
                stream = ffmpeg.output(stream, str(output_path), acodec='libmp3lame', audio_bitrate=mp3_bitrate, ar=str(self.sample_rate))
            elif output_format == 'ogg':
                # OGG Vorbis 使用 q:a 参数设置质量 (0-10, 10最高)
                stream = ffmpeg.output(stream, str(output_path), acodec='libvorbis', ar=str(self.sample_rate), **{'q:a': ogg_quality})
            else:
                # 默认使用 WAV
                stream = ffmpeg.output(stream, str(output_path), acodec='pcm_s16le', ar=str(self.sample_rate))
            
            ffmpeg.run(stream, cmd=ffmpeg_cmd, input=audio_bytes, overwrite_output=True, capture_stdout=True, capture_stderr=True)
            
            # 验证文件是否成功创建
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise RuntimeError(f"输出文件未成功创建: {output_path}")
                
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)
            raise RuntimeError(f"FFmpeg 保存音频失败: {error_msg}")
        except Exception as e:
            raise RuntimeError(f"保存音频时出错: {type(e).__name__}: {str(e)}")
    
    def separate(
        self,
        audio_path: Path,
        output_dir: Path,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        output_format: str = 'wav',
        output_sample_rate: Optional[int] = None,
        mp3_bitrate: str = '320k',
        ogg_quality: Union[int, str] = 10
    ) -> Tuple[Path, Path]:
        """分离人声和伴奏。
        
        Args:
            audio_path: 输入音频文件路径
            output_dir: 输出目录
            progress_callback: 进度回调函数 (状态消息, 进度0-1)
            output_format: 输出格式 ('wav', 'flac', 'mp3', 'ogg')
            output_sample_rate: 输出采样率 (None表示使用原始音频采样率)
            mp3_bitrate: MP3码率 ('original' 或 '128k'/'192k'/'256k'/'320k')
            ogg_quality: OGG质量 ('original' 或 0-10的整数)
            
        Returns:
            (人声文件路径, 伴奏文件路径)
        """
        if self.session is None:
            raise RuntimeError("模型未加载，请先调用 load_model()")
        
        # 检查 FFmpeg 是否可用
        if self.ffmpeg_service:
            is_available, _ = self.ffmpeg_service.is_ffmpeg_available()
            if not is_available:
                raise RuntimeError(
                    "FFmpeg 未安装或不可用。\n"
                    "请在 音频处理 -> FFmpeg终端 中安装 FFmpeg。"
                )
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载音频
        if progress_callback:
            progress_callback("正在加载音频...", 0.1)
        
        audio = self._load_audio_ffmpeg(audio_path)
        original_sample_rate = self.sample_rate
        
        # 获取原始文件的比特率信息（如果需要）
        original_bitrate = None
        if mp3_bitrate == "original" or ogg_quality == "original":
            original_bitrate = self._get_audio_bitrate(audio_path)
        
        # 确保是立体声
        if audio.ndim == 1:
            audio = np.stack([audio, audio])
        elif audio.shape[0] == 1:
            audio = np.vstack([audio, audio])
        
        # 处理音频
        if progress_callback:
            progress_callback("正在分离人声...", 0.2)
        
        vocals, instrumentals = self._process_audio(audio, progress_callback)
        
        # 处理采样率转换
        target_sample_rate = output_sample_rate if output_sample_rate else original_sample_rate
        if target_sample_rate != original_sample_rate:
            if progress_callback:
                progress_callback(f"正在转换采样率至 {target_sample_rate} Hz...", 0.85)
            vocals = self._resample_audio(vocals, original_sample_rate, target_sample_rate)
            instrumentals = self._resample_audio(instrumentals, original_sample_rate, target_sample_rate)
            # 临时更新采样率用于保存
            original_sr = self.sample_rate
            self.sample_rate = target_sample_rate
        else:
            original_sr = None
        
        # 保存结果
        if progress_callback:
            progress_callback("正在保存文件...", 0.9)
        
        # 生成输出文件名
        stem = audio_path.stem
        vocals_path = output_dir / f"{stem}_vocals.{output_format}"
        instrumental_path = output_dir / f"{stem}_instrumental.{output_format}"
        
        # 处理比特率/质量设置
        final_mp3_bitrate = mp3_bitrate
        final_ogg_quality = ogg_quality
        
        if mp3_bitrate == "original" and original_bitrate:
            # 将原始比特率转换为最接近的标准MP3比特率
            bitrate_kbps = original_bitrate // 1000
            if bitrate_kbps >= 280:
                final_mp3_bitrate = "320k"
            elif bitrate_kbps >= 224:
                final_mp3_bitrate = "256k"
            elif bitrate_kbps >= 160:
                final_mp3_bitrate = "192k"
            else:
                final_mp3_bitrate = "128k"
        elif mp3_bitrate == "original":
            final_mp3_bitrate = "320k"  # 默认最高质量
        
        if ogg_quality == "original" and original_bitrate:
            # 将原始比特率转换为OGG质量等级
            bitrate_kbps = original_bitrate // 1000
            if bitrate_kbps >= 224:
                final_ogg_quality = 10
            elif bitrate_kbps >= 192:
                final_ogg_quality = 8
            elif bitrate_kbps >= 160:
                final_ogg_quality = 6
            else:
                final_ogg_quality = 4
        elif ogg_quality == "original":
            final_ogg_quality = 10  # 默认最高质量
        
        # 保存人声
        self._save_audio_ffmpeg(
            vocals, 
            vocals_path, 
            output_format=output_format,
            mp3_bitrate=final_mp3_bitrate,
            ogg_quality=final_ogg_quality
        )
        
        # 保存伴奏
        self._save_audio_ffmpeg(
            instrumentals, 
            instrumental_path, 
            output_format=output_format,
            mp3_bitrate=final_mp3_bitrate,
            ogg_quality=final_ogg_quality
        )
        
        # 恢复原始采样率
        if original_sr is not None:
            self.sample_rate = original_sr
        
        if progress_callback:
            progress_callback("完成!", 1.0)
        
        return vocals_path, instrumental_path
    
    def _get_audio_bitrate(self, audio_path: Path) -> Optional[int]:
        """获取音频文件的比特率。
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            比特率（bps），如果无法获取则返回None
        """
        try:
            # 设置 ffmpeg 环境
            self._setup_ffmpeg_env()
            
            # 使用 ffprobe 获取音频信息
            probe = ffmpeg.probe(str(audio_path))
            
            # 查找音频流
            audio_streams = [stream for stream in probe['streams'] if stream['codec_type'] == 'audio']
            
            if audio_streams:
                audio_stream = audio_streams[0]
                # 尝试获取比特率
                if 'bit_rate' in audio_stream:
                    return int(audio_stream['bit_rate'])
                elif 'tags' in audio_stream and 'BPS' in audio_stream['tags']:
                    return int(audio_stream['tags']['BPS'])
            
            # 如果无法从流中获取，尝试从格式中获取
            if 'format' in probe and 'bit_rate' in probe['format']:
                return int(probe['format']['bit_rate'])
            
            return None
            
        except Exception as e:
            return None
    
    def _resample_audio(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """重采样音频到目标采样率。
        
        使用 sinc 插值进行高质量重采样（基于 FFT 的方法）。
        
        Args:
            audio: 音频数据 (channels, samples)
            orig_sr: 原始采样率
            target_sr: 目标采样率
            
        Returns:
            重采样后的音频数据
        """
        if orig_sr == target_sr:
            return audio
        
        def resample_single_channel(y: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
            """对单通道音频进行重采样（使用 FFT 方法）。"""
            # 计算新的采样点数
            n_samples = int(np.ceil(len(y) * target_sr / orig_sr))
            
            # 使用 FFT 进行重采样（频域插值）
            Y = np.fft.rfft(y)
            
            # 计算新的频率bins数量
            n_fft_new = n_samples if n_samples % 2 == 0 else n_samples + 1
            n_freq_new = n_fft_new // 2 + 1
            n_freq_old = len(Y)
            
            # 创建新的频谱
            if target_sr > orig_sr:
                # 上采样：在频谱末尾补零
                Y_new = np.zeros(n_freq_new, dtype=Y.dtype)
                Y_new[:n_freq_old] = Y
            else:
                # 下采样：截断高频
                Y_new = Y[:n_freq_new]
            
            # 逆FFT并调整幅度
            y_new = np.fft.irfft(Y_new, n=n_fft_new)[:n_samples]
            y_new *= target_sr / orig_sr
            
            return y_new
        
        if audio.shape[0] == 2:
            # 立体声，分别处理每个通道
            resampled_left = resample_single_channel(audio[0], orig_sr, target_sr)
            resampled_right = resample_single_channel(audio[1], orig_sr, target_sr)
            return np.stack([resampled_left, resampled_right])
        else:
            # 单声道
            return resample_single_channel(audio, orig_sr, target_sr)
    
    def _stft(self, y: np.ndarray, n_fft: int, hop_length: int, window: str = 'hann', center: bool = True) -> np.ndarray:
        """手动实现 STFT（短时傅里叶变换）。
        
        Args:
            y: 输入信号
            n_fft: FFT 大小
            hop_length: 帧移
            window: 窗口类型
            center: 是否中心填充
            
        Returns:
            复数频谱 (n_fft//2 + 1, n_frames)
        """
        # 创建窗口
        if window == 'hann':
            win = np.hanning(n_fft)
        else:
            win = np.ones(n_fft)
        
        # Center padding（镜像填充）
        if center:
            pad_len = n_fft // 2
            y = np.pad(y, (pad_len, pad_len), mode='reflect')
        
        # 计算帧数
        n_frames = 1 + (len(y) - n_fft) // hop_length
        
        # 初始化频谱
        spec = np.zeros((n_fft // 2 + 1, n_frames), dtype=np.complex64)
        
        # 对每一帧进行 FFT
        for i in range(n_frames):
            start = i * hop_length
            frame = y[start:start + n_fft]
            
            # 应用窗口并进行 FFT
            windowed = frame * win
            spec[:, i] = np.fft.rfft(windowed, n=n_fft)
        
        return spec
    
    def _istft(
        self, 
        spec: np.ndarray, 
        hop_length: int, 
        window: str = 'hann', 
        center: bool = True,
        length: Optional[int] = None
    ) -> np.ndarray:
        """手动实现 ISTFT（逆短时傅里叶变换）。
        
        Args:
            spec: 复数频谱 (n_fft//2 + 1, n_frames)
            hop_length: 帧移
            window: 窗口类型
            center: 是否使用了中心填充（需要裁剪）
            length: 输出长度
            
        Returns:
            重建的信号
        """
        n_fft = (spec.shape[0] - 1) * 2
        n_frames = spec.shape[1]
        
        # 创建窗口
        if window == 'hann':
            win = np.hanning(n_fft)
        else:
            win = np.ones(n_fft)
        
        # 计算输出长度
        expected_len = n_fft + hop_length * (n_frames - 1)
        y = np.zeros(expected_len)
        window_sum = np.zeros(expected_len)
        
        # 重叠相加重建
        for i in range(n_frames):
            start = i * hop_length
            
            # 逆 FFT
            frame = np.fft.irfft(spec[:, i], n=n_fft)
            
            # 应用窗口并累加
            y[start:start + n_fft] += frame * win
            window_sum[start:start + n_fft] += win * win
        
        # 归一化（避免除零）
        nonzero = window_sum > 1e-10
        y[nonzero] /= window_sum[nonzero]
        
        # 如果使用了 center padding，需要裁剪
        if center:
            pad_len = n_fft // 2
            y = y[pad_len:-pad_len]
        
        # 裁剪到指定长度
        if length is not None:
            if len(y) > length:
                y = y[:length]
            elif len(y) < length:
                y = np.pad(y, (0, length - len(y)), mode='constant')
        
        return y
    
    def _process_audio(
        self,
        audio: np.ndarray,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """处理音频进行分离。
        
        Args:
            audio: 输入音频数据 (2, samples)
            progress_callback: 进度回调
            
        Returns:
            (人声, 伴奏) numpy数组
        """
        # 直接对整个音频进行 STFT
        if progress_callback:
            progress_callback("正在进行频谱分析...", 0.2)
        
        # STFT (手动实现)
        spec_left = self._stft(
            audio[0],
            n_fft=self.n_fft,
            hop_length=self.hop_length,
            window='hann',
            center=True
        )
        spec_right = self._stft(
            audio[1],
            n_fft=self.n_fft,
            hop_length=self.hop_length,
            window='hann',
            center=True
        )
        
        # MDX-Net 模型需要 n_fft//2 个bins（去掉最高频）
        if spec_left.shape[0] > self.model_freq_bins:
            spec_left = spec_left[:self.model_freq_bins, :]
            spec_right = spec_right[:self.model_freq_bins, :]

        # 组合为复数频谱 (channels, freq_bins, time_frames)
        spec = np.stack([spec_left, spec_right], axis=0)
        
        # 分块处理频谱
        total_frames = spec.shape[2]
        chunk_frames = self.model_time_frames
        overlap_frames = int(chunk_frames * self.overlap)
        stride_frames = chunk_frames - overlap_frames
        
        # 输出频谱
        vocal_spec = np.zeros_like(spec)
        weights = np.zeros(total_frames)
        
        num_chunks = (total_frames - overlap_frames) // stride_frames + 1
        
        for i in range(num_chunks):
            start_frame = i * stride_frames
            end_frame = min(start_frame + chunk_frames, total_frames)
            
            if progress_callback:
                progress = 0.2 + 0.7 * (i / num_chunks)
                progress_callback(f"处理中... ({i+1}/{num_chunks})", progress)
            
            # 提取频谱块
            spec_chunk = spec[:, :, start_frame:end_frame]
            
            # 如果块太小，填充到模型要求的大小
            actual_frames = spec_chunk.shape[2]
            if actual_frames < chunk_frames:
                padding = chunk_frames - actual_frames
                spec_chunk = np.pad(spec_chunk, ((0, 0), (0, 0), (0, padding)), mode='constant')
            
            # 准备模型输入
            if self.model_channels == 4:
                # 4通道: [实部_L, 虚部_L, 实部_R, 虚部_R] 
                # 注意：不同模型可能使用不同的通道顺序，常见的是:
                # 1. [Real_L, Imag_L, Real_R, Imag_R] (Kuielab/UVR standard)
                # 2. [Real_L, Real_R, Imag_L, Imag_R] (某些变体)
                
                # 尝试使用标准顺序 1: [Real_L, Imag_L, Real_R, Imag_R]
                real = np.real(spec_chunk)
                imag = np.imag(spec_chunk)
                input_data = np.stack([real[0], imag[0], real[1], imag[1]], axis=0)
                input_data = input_data[np.newaxis, :, :, :].astype(np.float32)
            else:
                # 2通道: 幅度谱
                mag = np.abs(spec_chunk)
                input_data = mag[np.newaxis, :, :, :].astype(np.float32)
            
            # 计算输入数据的最大幅度，用于后续可能的反归一化
            if self.model_channels == 4:
                 # 使用输入数据的绝对最大值作为参考
                max_mag = np.max(np.abs(input_data))
            else:
                max_mag = 1.0 # 幅度掩码模式下通常不需要

            # 模型推理
            input_name = self.session.get_inputs()[0].name
            output_name = self.session.get_outputs()[0].name
            output = self.session.run([output_name], {input_name: input_data})[0]
            
            # 解析输出 (batch, channels, freq_bins, time_frames)
            output_data = output[0]
                        
            # 处理模型输出
            if self.model_channels == 4:
                # 4通道输出: [Real_L, Imag_L, Real_R, Imag_R]
                # 重建复数频谱
                vocal_chunk = np.zeros((2, output_data.shape[1], output_data.shape[2]), dtype=np.complex64)
                vocal_chunk[0] = output_data[0] + 1j * output_data[1]  # L
                vocal_chunk[1] = output_data[2] + 1j * output_data[3]  # R
                
                # UVR 标准: 应用补偿因子 (Compensate)
                # 模型输出需要除以补偿因子来恢复正确的幅度
                vocal_chunk = vocal_chunk / self.compensate
                
            else:
                # 2通道输出: 幅度掩码
                mask = np.clip(output_data, 0, 1)
                vocal_chunk = spec_chunk * mask
            
            # 截取有效帧数
            vocal_chunk = vocal_chunk[:, :, :actual_frames]
            
            # 创建平滑窗口
            window = np.ones(actual_frames)
            fade_length = min(overlap_frames // 2, actual_frames // 4)
            if fade_length > 0 and i > 0:
                window[:fade_length] = np.linspace(0, 1, fade_length)
            if fade_length > 0 and end_frame < total_frames:
                window[-fade_length:] = np.linspace(1, 0, fade_length)
            
            # 应用窗口并累加
            for ch in range(2):
                vocal_spec[ch, :, start_frame:end_frame] += vocal_chunk[ch] * window
            weights[start_frame:end_frame] += window
        
        # 归一化
        weights = np.maximum(weights, 1e-8)
        for ch in range(2):
            vocal_spec[ch] = vocal_spec[ch] / weights
        
        if progress_callback:
            progress_callback("正在重建音频...", 0.9)
        
        # 如果之前裁剪了频率bins，需要补回最高频（用零填充）
        expected_freq_bins = self.n_fft // 2 + 1
        if vocal_spec.shape[1] < expected_freq_bins:
            padding = expected_freq_bins - vocal_spec.shape[1]
            vocal_spec = np.pad(vocal_spec, ((0, 0), (0, padding), (0, 0)), mode='constant')
        
        # ISTFT 重建音频 (手动实现)
        vocals_left = self._istft(
            vocal_spec[0],
            hop_length=self.hop_length,
            window='hann',
            center=True,
            length=audio.shape[1]  # 指定输出长度，避免长度不匹配
        )
        vocals_right = self._istft(
            vocal_spec[1],
            hop_length=self.hop_length,
            window='hann',
            center=True,
            length=audio.shape[1]
        )
        
        model_output = np.stack([vocals_left, vocals_right])
        
        # 根据模型类型决定输出
        if self.invert_output:
            # 模型输出的是伴奏，需要反转
            instrumentals = model_output
            vocals = audio - instrumentals
        else:
            # 模型输出的是人声（默认）
            vocals = model_output
            instrumentals = audio - vocals
                
        return vocals, instrumentals
    
    def get_available_models(self) -> list[str]:
        """获取可用的模型列表。
        
        Returns:
            模型文件名列表
        """
        return [
            "Kim_Vocal_2.onnx",
            "MDX23C-8KFFT-InstVoc_HQ.onnx",
            "UVR-MDX-NET-Inst_HQ_3.onnx",
        ]
    
    def cleanup(self) -> None:
        """清理资源。"""
        if self.session:
            del self.session
            self.session = None

