# -*- coding: utf-8 -*-
"""VAD（语音活动检测）服务模块。

使用 Silero VAD 检测音频中的语音段落，用于智能分片。
"""

import os
from pathlib import Path
from typing import Optional, Callable, List, Tuple, TYPE_CHECKING, Any
import numpy as np

from utils import logger

if TYPE_CHECKING:
    from constants import VADModelInfo


class VADService:
    """VAD（语音活动检测）服务类。
    
    使用 Silero VAD 模型检测音频中的语音段落，
    返回语音片段的起止时间，用于智能分片。
    """
    
    def __init__(
        self,
        model_dir: Optional[Path] = None,
        debug_mode: bool = False
    ):
        """初始化 VAD 服务。
        
        Args:
            model_dir: 模型存储目录
            debug_mode: 是否启用调试模式
        """
        self.model_dir = model_dir
        self.debug_mode = debug_mode
        
        if self.model_dir:
            self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.vad = None
        self.current_model: Optional[str] = None
        self.sample_rate: int = 16000
        # sherpa-onnx VoiceActivityDetector 的内部缓冲区长度（秒）
        # 用于将 segment.start（可能是“缓冲区内相对索引”）换算为全局时间
        self.buffer_size_in_seconds: float = 30.0
        # 保存 VAD 配置，用于必要时为长音频创建“大缓冲”的临时 VAD 实例
        self._vad_config: Optional[Any] = None
        
        # VAD 参数
        self.threshold: float = 0.5
        self.min_silence_duration: float = 0.5  # 秒
        self.min_speech_duration: float = 0.25  # 秒
        self.window_size: int = 512  # 采样点数
    
    def get_model_dir(self, model_key: str) -> Path:
        """获取指定模型的存储目录。
        
        Args:
            model_key: 模型键名
            
        Returns:
            模型存储目录路径
        """
        model_subdir = self.model_dir / model_key
        model_subdir.mkdir(parents=True, exist_ok=True)
        return model_subdir
    
    def download_model(
        self,
        model_key: str,
        model_info: 'VADModelInfo',
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Path:
        """下载 VAD 模型文件。
        
        Args:
            model_key: 模型键名
            model_info: VAD 模型信息
            progress_callback: 进度回调函数 (进度0-1, 状态消息)
            
        Returns:
            模型文件路径
        """
        import httpx
        
        model_dir = self.get_model_dir(model_key)
        model_path = model_dir / model_info.filename
        
        # 检查文件是否已存在
        if model_path.exists():
            return model_path
        
        if progress_callback:
            progress_callback(0.0, "下载 VAD 模型...")
        
        # 使用临时文件下载
        temp_path = model_path.with_suffix(model_path.suffix + '.tmp')
        
        try:
            with httpx.stream("GET", model_info.url, follow_redirects=True, timeout=300.0) as response:
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(temp_path, 'wb') as f:
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
                                    f"下载 VAD 模型: {size_mb:.1f}/{total_mb:.1f} MB"
                                )
                
                # 验证文件大小
                if total_size > 0:
                    actual_size = temp_path.stat().st_size
                    if actual_size != total_size:
                        raise RuntimeError(
                            f"文件大小不匹配: 预期 {total_size} 字节, 实际 {actual_size} 字节"
                        )
                
                # 重命名为正式文件
                temp_path.replace(model_path)
                
                logger.info(f"✓ VAD 模型下载完成: {model_path.name}")
                
                if progress_callback:
                    progress_callback(1.0, "下载完成!")
                
                return model_path
                
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise RuntimeError(f"下载 VAD 模型失败: {e}")
    
    def load_model(
        self,
        model_path: Path,
        threshold: float = 0.5,
        min_silence_duration: float = 0.5,
        min_speech_duration: float = 0.25,
        window_size: int = 512,
        use_gpu: bool = False
    ) -> None:
        """加载 VAD 模型。
        
        Args:
            model_path: 模型文件路径
            threshold: 语音检测阈值（0-1）
            min_silence_duration: 最小静音时长（秒）
            min_speech_duration: 最小语音时长（秒）
            window_size: 窗口大小（采样点）
            use_gpu: 是否使用 GPU（目前 VAD 模型很小，CPU 足够快）
        """
        try:
            import sherpa_onnx
        except ImportError:
            raise RuntimeError(
                "sherpa-onnx 未安装。\n"
                "请运行: pip install sherpa-onnx"
            )
        
        if not model_path.exists():
            raise FileNotFoundError(f"VAD 模型文件不存在: {model_path}")
        
        # 保存参数
        self.threshold = threshold
        self.min_silence_duration = min_silence_duration
        self.min_speech_duration = min_speech_duration
        self.window_size = window_size
        
        # 配置执行提供者
        provider = "cpu"  # VAD 模型很小，CPU 足够快
        
        # 获取可用的 CPU 线程数
        num_threads = min(os.cpu_count() or 4, 4)
        
        try:
            # 创建 VAD 配置
            config = sherpa_onnx.VadModelConfig(
                silero_vad=sherpa_onnx.SileroVadModelConfig(
                    model=str(model_path),
                    threshold=threshold,
                    min_silence_duration=min_silence_duration,
                    min_speech_duration=min_speech_duration,
                    window_size=window_size,
                ),
                sample_rate=self.sample_rate,
                num_threads=num_threads,
                provider=provider,
                debug=self.debug_mode,
            )
            self._vad_config = config
            
            # 创建 VAD 实例
            self.buffer_size_in_seconds = 30.0
            self.vad = sherpa_onnx.VoiceActivityDetector(
                config,
                buffer_size_in_seconds=self.buffer_size_in_seconds
            )
            self.current_model = model_path.stem
            
            logger.info(
                f"VAD 模型已加载: {model_path.name}, "
                f"阈值: {threshold}, 最小静音: {min_silence_duration}s"
            )
            
        except Exception as e:
            raise RuntimeError(f"加载 VAD 模型失败: {e}")
    
    def detect_speech_segments(
        self,
        audio: np.ndarray,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> List[Tuple[float, float]]:
        """检测音频中的语音片段。
        
        Args:
            audio: 音频数据（单声道 16kHz float32）
            progress_callback: 进度回调函数
            
        Returns:
            语音片段列表，每个元素为 (开始时间, 结束时间) 秒
        """
        if self.vad is None:
            raise RuntimeError("VAD 模型未加载，请先调用 load_model()")
        
        if progress_callback:
            progress_callback("正在检测语音活动...", 0.1)
        
        # 分块处理音频
        window_samples = self.window_size
        total_samples = len(audio)
        audio_duration = total_samples / self.sample_rate

        # 仅供 VAD 使用的音频（确保 float32，且当幅度>1时归一化到 [-1, 1]）
        audio_vad = audio.astype(np.float32, copy=False)
        try:
            peak = float(np.max(np.abs(audio_vad))) if audio_vad.size else 0.0
            if peak > 1.0:
                audio_vad = audio_vad / peak
                logger.info(f"VAD 输入归一化: peak {peak:.6f} -> 1.000000")
        except Exception:
            pass

        def _run_detection(vad_inst, vad_buffer_seconds: float) -> List[Tuple[float, float]]:
            """在给定 VAD 实例上跑一次检测，返回 (start,end) 秒。"""
            segments_local: List[Tuple[float, float]] = []

            # reset（必须对当前实例）
            try:
                reset_attr = getattr(vad_inst, "reset")
                if callable(reset_attr):
                    reset_attr()
            except Exception:
                pass

            def _vad_is_empty() -> bool:
                empty_attr = getattr(vad_inst, "empty")
                return empty_attr() if callable(empty_attr) else bool(empty_attr)

            def _vad_front():
                front_attr = getattr(vad_inst, "front")
                return front_attr() if callable(front_attr) else front_attr

            def _vad_pop() -> None:
                pop_attr = getattr(vad_inst, "pop")
                if callable(pop_attr):
                    pop_attr()

            def _segment_samples(seg):
                samples_attr = getattr(seg, "samples", [])
                return samples_attr() if callable(samples_attr) else samples_attr

            vad_buffer_samples = int(vad_buffer_seconds * self.sample_rate)

            def _drain_segments(total_accepted_samples: int) -> None:
                buffer_start = max(0, total_accepted_samples - vad_buffer_samples)
                while not _vad_is_empty():
                    seg = _vad_front()
                    _vad_pop()

                    samples = _segment_samples(seg)
                    seg_start = getattr(seg, "start", 0)
                    try:
                        seg_start_i = int(seg_start)
                    except Exception:
                        seg_start_i = 0

                    cand_global = seg_start_i
                    cand_relative = buffer_start + seg_start_i

                    def _is_valid(start_sample: int) -> bool:
                        end_sample = start_sample + len(samples)
                        return 0 <= start_sample <= end_sample <= (total_accepted_samples + window_samples)

                    if _is_valid(cand_global):
                        start_sample = cand_global
                    elif _is_valid(cand_relative):
                        start_sample = cand_relative
                    else:
                        start_sample = cand_global

                    end_sample = start_sample + len(samples)
                    segments_local.append((start_sample / self.sample_rate, end_sample / self.sample_rate))

            for i in range(0, total_samples, window_samples):
                end_idx = min(i + window_samples, total_samples)
                chunk = audio_vad[i:end_idx]
                if len(chunk) < window_samples:
                    chunk = np.pad(chunk, (0, window_samples - len(chunk)), mode='constant')
                if chunk.dtype != np.float32:
                    chunk = chunk.astype(np.float32, copy=False)

                vad_inst.accept_waveform(chunk)
                _drain_segments(total_accepted_samples=end_idx)

                if progress_callback:
                    progress = 0.1 + 0.8 * (i / total_samples)
                    progress_callback(f"检测语音活动... {i // self.sample_rate}s", progress)

            # flush + drain 收尾
            flush_attr = getattr(vad_inst, "flush", None)
            if callable(flush_attr):
                flush_attr()
            _drain_segments(total_accepted_samples=total_samples)
            return segments_local

        # 先尝试：对长音频使用临时“大缓冲” VAD（如果可用）
        vad = self.vad
        vad_buffer_seconds = self.buffer_size_in_seconds
        used_temp_vad = False
        if self._vad_config is not None and audio_duration > self.buffer_size_in_seconds * 1.2:
            try:
                import sherpa_onnx
                big_buffer = min(max(audio_duration + 5.0, 30.0), 900.0)
                vad = sherpa_onnx.VoiceActivityDetector(
                    self._vad_config,
                    buffer_size_in_seconds=big_buffer,
                )
                vad_buffer_seconds = big_buffer
                used_temp_vad = True
            except Exception:
                vad = self.vad
                vad_buffer_seconds = self.buffer_size_in_seconds
                used_temp_vad = False

        segments = _run_detection(vad, vad_buffer_seconds)

        # 自愈：如果临时 VAD 得到 0 段，回退用 self.vad(30s buffer) 再跑一次
        if not segments and used_temp_vad:
            logger.warning("临时大缓冲 VAD 未检测到片段，回退使用默认 VAD 再尝试一次")
            segments = _run_detection(self.vad, self.buffer_size_in_seconds)

        # 规范化并按时间排序（否则后续 merge_short_segments 会因乱序导致误合并）
        cleaned: List[Tuple[float, float]] = []
        for s, e in segments:
            s = max(0.0, float(s))
            e = min(audio_duration, float(e))
            if e > s:
                cleaned.append((s, e))
        cleaned.sort(key=lambda x: x[0])
        segments = cleaned

        # 兜底：如果 sherpa-onnx VAD 最终返回 0 段，使用能量型 VAD 做降级分片
        if not segments:
            logger.warning("sherpa-onnx VAD 未检测到语音片段，启用能量型 VAD 兜底分片")
            fallback_segs = self._fallback_energy_vad(
                audio=audio_vad,
                sample_rate=self.sample_rate,
                min_silence_duration=self.min_silence_duration,
                min_speech_duration=self.min_speech_duration,
            )
            # 对兜底结果也做规范化
            for s, e in fallback_segs:
                s = max(0.0, float(s))
                e = min(audio_duration, float(e))
                if e > s:
                    segments.append((s, e))
            segments.sort(key=lambda x: x[0])

        # 统计信息：帮助定位 VAD 时间轴是否覆盖整个音频
        if segments:
            min_start = segments[0][0]
            max_end = max(e for _, e in segments)
            logger.info(
                f"VAD 片段时间范围: {min_start:.2f}s ~ {max_end:.2f}s / 音频 {audio_duration:.2f}s"
            )
        else:
            # 辅助诊断：音频能量过低时 VAD 可能全空
            try:
                rms = float(np.sqrt(np.mean(audio_vad.astype(np.float32) ** 2)))
                peak = float(np.max(np.abs(audio_vad.astype(np.float32))))
                logger.warning(f"VAD 无片段：音频能量 rms={rms:.6f}, peak={peak:.6f}")
            except Exception:
                pass

        if progress_callback:
            progress_callback(f"检测完成，找到 {len(segments)} 个语音片段", 1.0)
        
        logger.info(f"VAD 检测完成，找到 {len(segments)} 个语音片段")
        
        return segments

    def _fallback_energy_vad(
        self,
        audio: np.ndarray,
        sample_rate: int,
        min_silence_duration: float,
        min_speech_duration: float,
        frame_ms: float = 20.0,
        hop_ms: float = 10.0,
        padding: float = 0.08,
    ) -> List[Tuple[float, float]]:
        """能量型 VAD 兜底实现（不依赖 sherpa-onnx）。

        设计目标：当 Silero VAD 失效/返回空时，保证至少能做出“还不错”的静音切分。
        """
        if audio is None or audio.size == 0:
            return []

        audio = audio.astype(np.float32, copy=False)
        frame = max(1, int(sample_rate * frame_ms / 1000.0))
        hop = max(1, int(sample_rate * hop_ms / 1000.0))

        # 计算每帧 RMS
        n_frames = 1 + max(0, (len(audio) - frame) // hop)
        rms = np.empty(n_frames, dtype=np.float32)
        for i in range(n_frames):
            start = i * hop
            seg = audio[start:start + frame]
            if seg.size < frame:
                seg = np.pad(seg, (0, frame - seg.size), mode="constant")
            rms[i] = np.sqrt(np.mean(seg * seg, dtype=np.float32))

        # 动态阈值：用分位数估计噪声底和语音上界
        noise = float(np.percentile(rms, 20))
        hi = float(np.percentile(rms, 95))
        # 若几乎全静音，直接返回空
        if hi < 1e-4:
            return []
        thr = noise + 0.25 * max(hi - noise, 0.0)
        thr = max(thr, 0.01)  # 经验下限，避免过敏感

        voiced = rms >= thr

        # 将 voiced 帧合并成时间段
        segments: List[Tuple[float, float]] = []
        in_seg = False
        seg_start = 0.0
        for i, v in enumerate(voiced):
            t = (i * hop) / sample_rate
            if v and not in_seg:
                in_seg = True
                seg_start = t
            elif not v and in_seg:
                in_seg = False
                seg_end = t
                segments.append((seg_start, seg_end))
        if in_seg:
            segments.append((seg_start, len(audio) / sample_rate))

        if not segments:
            return []

        # 合并短静音间隔
        merged: List[Tuple[float, float]] = []
        cur_s, cur_e = segments[0]
        for s, e in segments[1:]:
            gap = s - cur_e
            if gap < min_silence_duration:
                cur_e = e
            else:
                merged.append((cur_s, cur_e))
                cur_s, cur_e = s, e
        merged.append((cur_s, cur_e))

        # 过滤过短语音段，并加 padding
        out: List[Tuple[float, float]] = []
        audio_dur = len(audio) / sample_rate
        for s, e in merged:
            if e - s < min_speech_duration:
                continue
            s2 = max(0.0, s - padding)
            e2 = min(audio_dur, e + padding)
            if e2 > s2:
                out.append((s2, e2))

        logger.info(
            f"能量型 VAD 兜底：thr={thr:.4f}, segments={len(out)} "
            f"(noise={noise:.4f}, p95={hi:.4f})"
        )
        return out
    
    def merge_short_segments(
        self,
        segments: List[Tuple[float, float]],
        max_segment_duration: float = 28.0,
        min_gap: float = 0.3
    ) -> List[Tuple[float, float]]:
        """合并相邻的短片段，确保每个片段不超过最大时长。
        
        Args:
            segments: 语音片段列表
            max_segment_duration: 最大片段时长（秒）
            min_gap: 最小间隔（秒），小于此间隔的片段会被合并
            
        Returns:
            合并后的片段列表
        """
        if not segments:
            return []
        
        merged = []
        current_start, current_end = segments[0]
        
        for start, end in segments[1:]:
            gap = start - current_end
            current_duration = current_end - current_start
            new_duration = end - current_start
            
            # 如果间隔小于 min_gap 且合并后不超过最大时长，则合并
            if gap < min_gap and new_duration <= max_segment_duration:
                current_end = end
            # 如果当前片段太长，需要分割
            elif current_duration > max_segment_duration:
                # 将长片段分割成多个
                split_segments = self._split_long_segment(current_start, current_end, max_segment_duration)
                merged.extend(split_segments)
                current_start, current_end = start, end
            else:
                merged.append((current_start, current_end))
                current_start, current_end = start, end
        
        # 处理最后一个片段
        if current_end - current_start > max_segment_duration:
            split_segments = self._split_long_segment(current_start, current_end, max_segment_duration)
            merged.extend(split_segments)
        else:
            merged.append((current_start, current_end))
        
        logger.info(f"合并后 {len(merged)} 个片段（原 {len(segments)} 个）")
        return merged
    
    def _split_long_segment(
        self,
        start: float,
        end: float,
        max_duration: float
    ) -> List[Tuple[float, float]]:
        """将长片段分割成多个短片段。
        
        Args:
            start: 开始时间（秒）
            end: 结束时间（秒）
            max_duration: 最大时长（秒）
            
        Returns:
            分割后的片段列表
        """
        segments = []
        current = start
        
        while current < end:
            segment_end = min(current + max_duration, end)
            segments.append((current, segment_end))
            current = segment_end
        
        return segments
    
    def get_audio_chunks(
        self,
        audio: np.ndarray,
        segments: List[Tuple[float, float]],
        padding: float = 0.1
    ) -> List[Tuple[np.ndarray, float, float]]:
        """根据语音片段提取音频块。
        
        Args:
            audio: 完整音频数据
            segments: 语音片段列表 [(start, end), ...]
            padding: 前后填充（秒）
            
        Returns:
            音频块列表，每个元素为 (音频数据, 开始时间, 结束时间)
        """
        chunks = []
        audio_duration = len(audio) / self.sample_rate
        
        for start, end in segments:
            # 添加填充
            padded_start = max(0, start - padding)
            padded_end = min(audio_duration, end + padding)
            
            # 转换为采样点索引
            start_idx = int(padded_start * self.sample_rate)
            end_idx = int(padded_end * self.sample_rate)
            
            chunk = audio[start_idx:end_idx]
            chunks.append((chunk, padded_start, padded_end))
        
        return chunks
    
    def is_model_loaded(self) -> bool:
        """检查模型是否已加载。"""
        return self.vad is not None
    
    def cleanup(self) -> None:
        """清理资源。"""
        if self.vad:
            try:
                del self.vad
            except Exception:
                pass
            finally:
                self.vad = None
    
    def __del__(self):
        """析构函数。"""
        try:
            self.cleanup()
        except Exception:
            pass

