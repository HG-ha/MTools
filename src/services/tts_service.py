# -*- coding: utf-8 -*-
"""TTS（文字转语音）服务模块。

使用 sherpa-onnx 进行本地离线文字转语音合成。
支持 VITS、Kokoro、Matcha 等多种模型架构。
"""

import gc
import os
import re
import struct
import wave
from pathlib import Path
from typing import Optional, Callable, List, Tuple, TYPE_CHECKING

import numpy as np

from utils import logger

if TYPE_CHECKING:
    from constants import TTSModelInfo
    from services import FFmpegService


class TTSService:
    """TTS 服务类。

    支持 sherpa-onnx 多种 TTS 模型架构进行文字转语音合成。
    """

    def __init__(
        self,
        model_dir: Optional[Path] = None,
        ffmpeg_service: Optional['FFmpegService'] = None,
        debug_mode: bool = False,
    ) -> None:
        self.model_dir = model_dir
        self.ffmpeg_service = ffmpeg_service
        self.debug_mode = debug_mode

        if self.model_dir:
            self.model_dir.mkdir(parents=True, exist_ok=True)

        self.tts = None
        self.current_model: Optional[str] = None
        self.current_model_type: str = "vits"
        self.sample_rate: int = 22050

    # ------------------------------------------------------------------
    # Model directory helpers
    # ------------------------------------------------------------------

    def get_model_dir(self, model_key: str) -> Path:
        model_subdir = self.model_dir / model_key
        model_subdir.mkdir(parents=True, exist_ok=True)
        return model_subdir

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download_model(
        self,
        model_key: str,
        model_info: 'TTSModelInfo',
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Path:
        """下载 TTS 模型文件。

        Returns:
            模型存储目录路径。
        """
        import httpx

        model_dir = self.get_model_dir(model_key)

        files_to_download: list[tuple[str, str, Path]] = []

        model_path = model_dir / model_info.model_filename
        tokens_path = model_dir / model_info.tokens_filename

        if not model_path.exists():
            files_to_download.append(("模型文件", model_info.model_url, model_path))
        if not tokens_path.exists():
            files_to_download.append(("词表文件", model_info.tokens_url, tokens_path))

        if model_info.lexicon_url and model_info.lexicon_filename:
            lex_urls = [u.strip() for u in model_info.lexicon_url.split(",")]
            lex_names = [n.strip() for n in model_info.lexicon_filename.split(",")]
            for lex_url, lex_name in zip(lex_urls, lex_names):
                lexicon_path = model_dir / lex_name
                if not lexicon_path.exists():
                    files_to_download.append(("词典文件", lex_url, lexicon_path))

        if model_info.rule_fsts_url and model_info.rule_fsts_filename:
            fst_urls = [u.strip() for u in model_info.rule_fsts_url.split(",")]
            fst_names = [n.strip() for n in model_info.rule_fsts_filename.split(",")]
            for fst_url, fst_name in zip(fst_urls, fst_names):
                fst_path = model_dir / fst_name
                if not fst_path.exists():
                    files_to_download.append(("规则文件", fst_url, fst_path))

        if hasattr(model_info, 'rule_fars_url') and model_info.rule_fars_url and model_info.rule_fars_filename:
            far_urls = [u.strip() for u in model_info.rule_fars_url.split(",")]
            far_names = [n.strip() for n in model_info.rule_fars_filename.split(",")]
            for far_url, far_name in zip(far_urls, far_names):
                far_path = model_dir / far_name
                if not far_path.exists():
                    files_to_download.append(("规则档案", far_url, far_path))

        if model_info.vocoder_url and model_info.vocoder_filename:
            vocoder_path = model_dir / model_info.vocoder_filename
            if not vocoder_path.exists():
                files_to_download.append(("Vocoder", model_info.vocoder_url, vocoder_path))

        if model_info.voices_url and model_info.voices_filename:
            voices_path = model_dir / model_info.voices_filename
            if not voices_path.exists():
                files_to_download.append(("音色文件", model_info.voices_url, voices_path))

        if model_info.data_dir_url and model_info.data_dir_name:
            data_dir_path = model_dir / model_info.data_dir_name
            if not data_dir_path.exists():
                archive_path = model_dir / f"{model_info.data_dir_name}.tar.gz"
                if not archive_path.exists():
                    files_to_download.append(("数据目录", model_info.data_dir_url, archive_path))

        if model_info.dict_dir_url and model_info.dict_dir_name:
            dict_dir_path = model_dir / model_info.dict_dir_name
            if not dict_dir_path.exists():
                dict_archive_path = model_dir / f"{model_info.dict_dir_name}.tar.gz"
                if not dict_archive_path.exists():
                    files_to_download.append(("词典目录", model_info.dict_dir_url, dict_archive_path))

        if not files_to_download:
            if progress_callback:
                progress_callback(1.0, "模型已就绪")
            return model_dir

        total_files = len(files_to_download)
        downloaded_files: list[Path] = []

        try:
            for i, (file_type, url, file_path) in enumerate(files_to_download):
                if progress_callback:
                    progress_callback(i / total_files, f"下载{file_type}...")

                temp_path = file_path.with_suffix(file_path.suffix + ".tmp")

                try:
                    with httpx.stream("GET", url, follow_redirects=True, timeout=300.0) as response:
                        response.raise_for_status()
                        total_size = int(response.headers.get("content-length", 0))
                        downloaded = 0

                        with open(temp_path, "wb") as f:
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
                                            f"下载{file_type}: {size_mb:.1f}/{total_mb:.1f} MB",
                                        )

                        if total_size > 0:
                            actual_size = temp_path.stat().st_size
                            if actual_size != total_size:
                                raise RuntimeError(
                                    f"{file_type}大小不匹配: 预期 {total_size} 字节, "
                                    f"实际 {actual_size} 字节"
                                )

                        if file_path.exists():
                            file_path.unlink()
                        temp_path.rename(file_path)
                        downloaded_files.append(file_path)
                        logger.info(f"TTS {file_type}下载完成: {file_path.name}")

                except Exception as e:
                    if temp_path.exists():
                        try:
                            temp_path.unlink()
                        except Exception:
                            pass
                    raise RuntimeError(f"下载{file_type}失败: {e}")

            import tarfile

            if model_info.data_dir_url and model_info.data_dir_name:
                data_dir_path = model_dir / model_info.data_dir_name
                archive_path = model_dir / f"{model_info.data_dir_name}.tar.gz"
                if archive_path.exists() and not data_dir_path.exists():
                    if progress_callback:
                        progress_callback(0.95, "解压数据目录...")
                    with tarfile.open(archive_path, "r:gz") as tar:
                        tar.extractall(path=model_dir)
                    archive_path.unlink()

            if model_info.dict_dir_url and model_info.dict_dir_name:
                dict_dir_path = model_dir / model_info.dict_dir_name
                dict_archive_path = model_dir / f"{model_info.dict_dir_name}.tar.gz"
                if dict_archive_path.exists() and not dict_dir_path.exists():
                    if progress_callback:
                        progress_callback(0.97, "解压词典目录...")
                    with tarfile.open(dict_archive_path, "r:gz") as tar:
                        tar.extractall(path=model_dir)
                    dict_archive_path.unlink()

            if progress_callback:
                progress_callback(1.0, "下载完成!")

            return model_dir

        except Exception as e:
            for file_path in downloaded_files:
                if file_path.exists():
                    try:
                        file_path.unlink()
                        logger.warning(f"已删除不完整的文件: {file_path.name}")
                    except Exception:
                        pass
            raise RuntimeError(f"下载 TTS 模型失败: {e}")

    # ------------------------------------------------------------------
    # Load / Unload
    # ------------------------------------------------------------------

    def load_model(
        self,
        model_key: str,
        model_info: 'TTSModelInfo',
        model_dir: Optional[Path] = None,
        num_threads: int = 4,
    ) -> None:
        """加载 TTS 模型。"""
        try:
            import sherpa_onnx
        except ImportError:
            raise RuntimeError("sherpa-onnx 未安装。\n请运行: pip install sherpa-onnx")

        if model_dir is None:
            model_dir = self.get_model_dir(model_key)

        model_path = str(model_dir / model_info.model_filename)
        tokens_path = str(model_dir / model_info.tokens_filename)

        lexicon = ""
        if model_info.lexicon_filename:
            lex_names = [n.strip() for n in model_info.lexicon_filename.split(",")]
            lexicon = ",".join(str(model_dir / n) for n in lex_names)

        data_dir = ""
        if model_info.data_dir_name:
            data_dir = str(model_dir / model_info.data_dir_name)

        dict_dir = ""
        if model_info.dict_dir_name:
            dict_dir = str(model_dir / model_info.dict_dir_name)

        rule_fsts = ""
        if model_info.rule_fsts_filename:
            fst_names = [n.strip() for n in model_info.rule_fsts_filename.split(",")]
            rule_fsts = ",".join(str(model_dir / n) for n in fst_names)

        rule_fars = ""
        if hasattr(model_info, 'rule_fars_filename') and model_info.rule_fars_filename:
            far_names = [n.strip() for n in model_info.rule_fars_filename.split(",")]
            rule_fars = ",".join(str(model_dir / n) for n in far_names)

        if self.tts is not None:
            self.unload_model()

        from utils.onnx_helper import get_sherpa_provider
        provider = get_sherpa_provider()

        model_type = model_info.model_type

        if model_type == "vits":
            tts_config = sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(
                    vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                        model=model_path,
                        tokens=tokens_path,
                        lexicon=lexicon,
                        data_dir=data_dir,
                        dict_dir=dict_dir,
                    ),
                    num_threads=num_threads,
                    provider=provider,
                ),
                rule_fsts=rule_fsts,
                rule_fars=rule_fars,
                max_num_sentences=2,
            )
        elif model_type == "kokoro":
            voices = ""
            if model_info.voices_filename:
                voices = str(model_dir / model_info.voices_filename)
            tts_config = sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(
                    kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                        model=model_path,
                        tokens=tokens_path,
                        voices=voices,
                        data_dir=data_dir,
                        dict_dir=dict_dir,
                        lexicon=lexicon,
                    ),
                    num_threads=num_threads,
                    provider=provider,
                ),
                rule_fsts=rule_fsts,
                rule_fars=rule_fars,
                max_num_sentences=1,
            )
        elif model_type == "matcha":
            vocoder = ""
            if model_info.vocoder_filename:
                vocoder = str(model_dir / model_info.vocoder_filename)
            tts_config = sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(
                    matcha=sherpa_onnx.OfflineTtsMatchaModelConfig(
                        acoustic_model=model_path,
                        vocoder=vocoder,
                        tokens=tokens_path,
                        lexicon=lexicon,
                        data_dir=data_dir,
                        dict_dir=dict_dir,
                    ),
                    num_threads=num_threads,
                    provider=provider,
                ),
                rule_fsts=rule_fsts,
                rule_fars=rule_fars,
                max_num_sentences=2,
            )
        else:
            raise ValueError(f"不支持的模型类型: {model_type}")

        self.tts = sherpa_onnx.OfflineTts(tts_config)

        self.current_model = model_key
        self.current_model_type = model_type
        self.sample_rate = self.tts.sample_rate

        device_label = "CUDA" if provider == "cuda" else "CPU"
        logger.info(
            f"TTS 模型已加载: {model_info.display_name} "
            f"(采样率={self.sample_rate}, 说话人={self.get_num_speakers()}, "
            f"设备={device_label})"
        )

    def unload_model(self) -> None:
        """卸载当前 TTS 模型并释放内存。"""
        if self.tts is not None:
            del self.tts
            self.tts = None
            self.current_model = None
            gc.collect()
            logger.info("TTS 模型已卸载")

    def is_loaded(self) -> bool:
        return self.tts is not None

    def get_num_speakers(self) -> int:
        if self.tts is None:
            return 0
        return self.tts.num_speakers

    # ------------------------------------------------------------------
    # Generate
    # ------------------------------------------------------------------

    def generate(
        self,
        text: str,
        sid: int = 0,
        speed: float = 1.0,
    ) -> Tuple[np.ndarray, int]:
        """合成语音。

        Kokoro 等注意力模型在文本较长时容易出现重复，
        因此自动走分句合成路径。

        Returns:
            (samples, sample_rate) —— samples 为 float32 numpy 数组。
        """
        if self.tts is None:
            raise RuntimeError("TTS 模型未加载")

        if self.current_model_type == "kokoro":
            return self.generate_long_text(text, sid, speed)

        audio = self.tts.generate(text=text, sid=sid, speed=speed)

        samples = np.array(audio.samples, dtype=np.float32)
        return samples, audio.sample_rate

    def generate_long_text(
        self,
        text: str,
        sid: int = 0,
        speed: float = 1.0,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Tuple[np.ndarray, int]:
        """分段合成长文本。

        将文本按句子切分，逐段合成后拼接。
        Kokoro 等注意力模型使用更小的分段上限以避免重复。

        Args:
            text: 待合成文本
            sid: 说话人 ID
            speed: 语速
            progress_callback: 进度回调 (当前段索引, 总段数)

        Returns:
            (samples, sample_rate)
        """
        if self.tts is None:
            raise RuntimeError("TTS 模型未加载")

        max_chars = 80 if self.current_model_type == "kokoro" else 200
        segments = self._split_text(text, max_chars=max_chars)
        if not segments:
            return np.array([], dtype=np.float32), self.sample_rate

        all_samples: list[np.ndarray] = []
        total = len(segments)

        for i, seg in enumerate(segments):
            if progress_callback:
                progress_callback(i, total)
            audio = self.tts.generate(text=seg, sid=sid, speed=speed)
            seg_samples = np.array(audio.samples, dtype=np.float32)
            if len(seg_samples) > 0:
                all_samples.append(seg_samples)

        if progress_callback:
            progress_callback(total, total)

        if not all_samples:
            return np.array([], dtype=np.float32), self.sample_rate

        return np.concatenate(all_samples), self.sample_rate

    # ------------------------------------------------------------------
    # Save to file
    # ------------------------------------------------------------------

    @staticmethod
    def _write_wav(samples: np.ndarray, sample_rate: int, output_path: Path) -> None:
        """将采样数据写入 WAV 文件（内部方法，不打日志）。"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        int16_samples = (samples * 32767).clip(-32768, 32767).astype(np.int16)

        with wave.open(str(output_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(int16_samples.tobytes())

    def save_wav(self, samples: np.ndarray, sample_rate: int, output_path: Path) -> None:
        """保存音频为 WAV 文件。"""
        self._write_wav(samples, sample_rate, output_path)
        logger.info(f"WAV 已保存: {output_path}")

    def save_mp3(
        self,
        samples: np.ndarray,
        sample_rate: int,
        output_path: Path,
        bitrate: str = "192k",
    ) -> None:
        """保存音频为 MP3 文件（通过 FFmpeg 转码）。"""
        import subprocess
        import tempfile

        tmp_fd, tmp_wav = tempfile.mkstemp(suffix=".wav")
        os.close(tmp_fd)
        tmp_wav_path = Path(tmp_wav)
        try:
            self._write_wav(samples, sample_rate, tmp_wav_path)

            ffmpeg_cmd = "ffmpeg"
            if self.ffmpeg_service:
                ffmpeg_cmd = self.ffmpeg_service.get_ffmpeg_path() or "ffmpeg"

            cmd = [
                ffmpeg_cmd, "-y",
                "-i", str(tmp_wav_path),
                "-codec:a", "libmp3lame",
                "-b:a", bitrate,
                str(output_path),
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg 转码失败: {result.stderr[:200]}")

            logger.info(f"MP3 已保存: {output_path}")
        finally:
            try:
                tmp_wav_path.unlink(missing_ok=True)
            except Exception:
                pass

    def generate_to_file(
        self,
        text: str,
        output_path: Path,
        sid: int = 0,
        speed: float = 1.0,
        output_format: str = "wav",
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """合成语音并保存到文件。"""
        use_long = (
            len(text) > 200
            or self.current_model_type == "kokoro"
        )
        if use_long:
            samples, sr = self.generate_long_text(text, sid, speed, progress_callback)
        else:
            samples, sr = self.generate(text, sid, speed)

        if len(samples) == 0:
            raise RuntimeError("合成结果为空，请检查输入文本")

        if output_format == "mp3":
            self.save_mp3(samples, sr, output_path)
        else:
            self.save_wav(samples, sr, output_path)

    # ------------------------------------------------------------------
    # Text splitting
    # ------------------------------------------------------------------

    @staticmethod
    def _split_text(text: str, max_chars: int = 200) -> List[str]:
        """将长文本切分为适合逐句合成的片段。

        Args:
            text: 待切分文本
            max_chars: 每段最大字符数（Kokoro 等注意力模型建议 ≤80）
        """
        text = text.strip()
        if not text:
            return []

        sentences = re.split(r'(?<=[。！？；.!?;\n])', text)
        segments: list[str] = []
        buf = ""

        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if len(buf) + len(s) > max_chars:
                if buf:
                    segments.append(buf)
                buf = s
            else:
                buf += s

        if buf:
            segments.append(buf)

        return segments

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        self.unload_model()
