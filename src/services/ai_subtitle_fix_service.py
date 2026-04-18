# -*- coding: utf-8 -*-
"""AI 字幕修复 / 翻译服务。

使用 OpenAI 兼容的 Chat Completions 接口（/v1/chat/completions + Bearer Token）
调用远程 LLM 进行字幕修复或翻译，用户自行提供 base_url / api_key / model。
"""

import httpx
from typing import List, Dict, Any, Optional, Callable
from utils import logger


class AISubtitleFixService:
    """AI 字幕修复 / 翻译服务（OpenAI 兼容接口）。"""

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        model: str = "",
    ) -> None:
        """初始化服务。

        Args:
            base_url: OpenAI 兼容 API 的 base URL，如 https://api.openai.com/v1
            api_key: API Key
            model: 模型名称，如 gpt-4o-mini
        """
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    # ── 配置 ──────────────────────────────────────────────────────
    def set_config(
        self,
        base_url: str = "",
        api_key: str = "",
        model: str = "",
    ) -> None:
        """一次性设置 base_url / api_key / model。"""
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    def set_api_key(self, api_key: str) -> None:
        """设置 API Key（保留兼容旧调用）。"""
        self.api_key = api_key

    def is_configured(self) -> bool:
        """检查是否已配置（base_url / api_key / model 都必须非空）。"""
        return bool(
            self.base_url and self.base_url.strip()
            and self.api_key and self.api_key.strip()
            and self.model and self.model.strip()
        )

    @property
    def api_url(self) -> str:
        """根据 base_url 拼出 chat/completions 端点。

        兼容用户填写带或不带 /v1、带或不带 /chat/completions 的情况：
          - https://api.openai.com          → https://api.openai.com/v1/chat/completions
          - https://api.openai.com/v1       → https://api.openai.com/v1/chat/completions
          - https://x.com/v1/chat/completions → 原样返回
        """
        base = (self.base_url or "").strip().rstrip("/")
        if not base:
            return ""
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return base + "/chat/completions"
        return base + "/v1/chat/completions"
    
    def fix_text(self, text: str, language: str = "zh") -> str:
        """修复单段文本。
        
        Args:
            text: 待修复的文本
            language: 语言代码
            
        Returns:
            修复后的文本
        """
        if not self.is_configured():
            raise ValueError("API Key 未配置")
        
        if not text or not text.strip():
            return text
        
        lang_name = {
            "zh": "中文",
            "en": "英文",
            "ja": "日文",
            "ko": "韩文",
            "auto": "自动检测语言",
        }.get(language, "中文")
        
        prompt = f"""你是一个专业的字幕校对助手。请修复以下语音识别生成的字幕文本中可能存在的错词、同音字错误、语法问题等。

要求：
1. 只修复明显的错误，保持原文的语义和风格
2. 不要添加或删除内容，只做必要的纠正
3. 如果文本没有明显错误，直接返回原文
4. 只返回修复后的文本，不要添加任何解释或标注
5. 语言：{lang_name}
6. 【严禁】修改任何数字、时间、日期、年份、金额等数值内容，必须原样保留

原文：
{text}

修复后的文本："""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,  # 较低的温度以保持稳定性
            "max_tokens": len(text) * 3 + 100,  # 预留足够的 token
        }
        
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(self.api_url, json=data, headers=headers)
                response.raise_for_status()
                result = response.json()
                
                # 检查返回格式
                if "choices" not in result:
                    error_msg = result.get("error", {}).get("message", str(result))
                    raise ValueError(f"API 返回格式异常: {error_msg}")
                
                if not result["choices"]:
                    raise ValueError("API 返回空的 choices")
                
                fixed_text = result["choices"][0]["message"]["content"].strip()
                
                # 移除可能的思考过程标签（qwen3 可能会返回 <think>...</think>）
                if "<think>" in fixed_text and "</think>" in fixed_text:
                    think_end = fixed_text.find("</think>")
                    fixed_text = fixed_text[think_end + 8:].strip()
                
                return fixed_text
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ValueError("API Key 无效，请检查后重试")
            elif e.response.status_code == 429:
                raise ValueError("请求过于频繁，请稍后重试")
            else:
                raise ValueError(f"API 请求失败: {e.response.status_code}")
        except httpx.TimeoutException:
            raise ValueError("请求超时，请检查网络后重试")
        except Exception as e:
            raise ValueError(f"修复失败: {e}")
    
    def fix_segments(
        self,
        segments: List[Dict[str, Any]],
        language: str = "zh",
        progress_callback: Optional[Callable[[str, float], None]] = None,
        batch_size: int = 50
    ) -> List[Dict[str, Any]]:
        """修复字幕分段列表。
        
        优化策略：
        - 短文本（< 3000 字）：一次性处理所有分段，只需 1 次 API 调用
        - 长文本：按批次处理，每批最多 50 个分段
        
        Args:
            segments: 字幕分段列表，每个分段包含 'text', 'start', 'end'
            language: 语言代码
            progress_callback: 进度回调函数 (message, progress)
            batch_size: 每批处理的分段数量（默认 50）
            
        Returns:
            修复后的字幕分段列表
        """
        if not self.is_configured():
            raise ValueError("API Key 未配置")
        
        if not segments:
            return segments
        
        total = len(segments)
        all_texts = [seg.get("text", "") for seg in segments]
        total_chars = sum(len(t) for t in all_texts)
        
        # 一次性处理所有分段
        if progress_callback:
            progress_callback(f"AI 修复中 (共 {total} 段, {total_chars} 字)...", 0.3)
        
        combined_text = "\n---\n".join(all_texts)
        
        try:
            fixed_combined = self._fix_batch(combined_text, language, total)
            fixed_texts = fixed_combined.split("\n---\n")
            
            # 确保数量匹配
            if len(fixed_texts) != total:
                logger.warning(f"AI 返回分段数 {len(fixed_texts)} 与原始 {total} 不匹配，尝试分批处理")
                return self._fix_segments_batched(segments, language, progress_callback, batch_size)
            
            fixed_segments = []
            for i, seg in enumerate(segments):
                new_seg = seg.copy()
                new_seg["text"] = fixed_texts[i].strip()
                fixed_segments.append(new_seg)
            
            if progress_callback:
                progress_callback("AI 修复完成", 1.0)
            
            logger.info(f"AI 字幕修复完成: {total} 个分段, {total_chars} 字 (单次请求)")
            return fixed_segments
            
        except Exception as e:
            logger.warning(f"一次性修复失败，尝试分批处理: {e}")
            return self._fix_segments_batched(segments, language, progress_callback, batch_size)
    
    def _fix_segments_batched(
        self,
        segments: List[Dict[str, Any]],
        language: str,
        progress_callback: Optional[Callable[[str, float], None]],
        batch_size: int
    ) -> List[Dict[str, Any]]:
        """分批修复字幕分段。"""
        total = len(segments)
        fixed_segments = []
        
        for i in range(0, total, batch_size):
            batch = segments[i:i + batch_size]
            batch_texts = [seg.get("text", "") for seg in batch]
            
            if progress_callback:
                progress = i / total
                progress_callback(f"AI 修复中 ({i}/{total})...", progress)
            
            combined_text = "\n---\n".join(batch_texts)
            
            try:
                fixed_combined = self._fix_batch(combined_text, language, len(batch))
                fixed_texts = fixed_combined.split("\n---\n")
                
                # 确保数量匹配
                if len(fixed_texts) != len(batch):
                    fixed_texts = []
                    for text in batch_texts:
                        try:
                            fixed = self.fix_text(text, language)
                            fixed_texts.append(fixed)
                        except Exception:
                            fixed_texts.append(text)
                
                for j, seg in enumerate(batch):
                    new_seg = seg.copy()
                    if j < len(fixed_texts):
                        new_seg["text"] = fixed_texts[j].strip()
                    fixed_segments.append(new_seg)
                    
            except Exception as e:
                logger.warning(f"批量修复失败，跳过: {e}")
                fixed_segments.extend(batch)
        
        if progress_callback:
            progress_callback("AI 修复完成", 1.0)
        
        logger.info(f"AI 字幕修复完成: {total} 个分段 (分批处理)")
        return fixed_segments
    
    def _fix_batch(self, combined_text: str, language: str, count: int) -> str:
        """批量修复合并的文本。"""
        if not combined_text.strip():
            return combined_text
        
        lang_name = {
            "zh": "中文",
            "en": "英文",
            "ja": "日文",
            "ko": "韩文",
            "auto": "自动检测语言",
        }.get(language, "中文")
        
        prompt = f"""你是一个专业的字幕校对助手。下面是 {count} 段语音识别生成的字幕文本，用 "---" 分隔。请修复每段文本中可能存在的错词、同音字错误、语法问题等。

要求：
1. 只修复明显的错误，保持原文的语义和风格
2. 不要添加或删除内容，只做必要的纠正
3. 如果某段文本没有明显错误，保持原样
4. 保持 "---" 分隔符，确保输出的段落数量与输入一致
5. 只返回修复后的文本，不要添加任何解释
6. 语言：{lang_name}
7. 【严禁】修改任何数字、时间、日期、年份、金额等数值内容，必须原样保留

原文：
{combined_text}

修复后的文本："""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": len(combined_text) * 3 + 200,
        }
        
        with httpx.Client(timeout=120.0) as client:
            response = client.post(self.api_url, json=data, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            # 检查返回格式
            if "choices" not in result:
                error_msg = result.get("error", {}).get("message", str(result))
                logger.error(f"API 返回格式异常: {error_msg}")
                raise ValueError(f"API 返回格式异常: {error_msg}")
            
            if not result["choices"]:
                logger.error("API 返回空的 choices")
                raise ValueError("API 返回空的 choices")
            
            fixed_text = result["choices"][0]["message"]["content"].strip()
            
            # 移除可能的思考过程标签
            if "<think>" in fixed_text and "</think>" in fixed_text:
                think_end = fixed_text.find("</think>")
                fixed_text = fixed_text[think_end + 8:].strip()
            
            return fixed_text
    
    def fix_plain_text(
        self,
        text: str,
        language: str = "zh",
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> str:
        """修复纯文本（非分段格式）。
        
        Args:
            text: 待修复的纯文本
            language: 语言代码
            progress_callback: 进度回调函数
            
        Returns:
            修复后的文本
        """
        if not self.is_configured():
            raise ValueError("API Key 未配置")
        
        if not text or not text.strip():
            return text
        
        if progress_callback:
            progress_callback("AI 修复中...", 0.5)
        
        try:
            fixed = self.fix_text(text, language)
            
            if progress_callback:
                progress_callback("AI 修复完成", 1.0)
            
            logger.info("AI 文本修复完成")
            return fixed
            
        except Exception as e:
            logger.error(f"AI 文本修复失败: {e}")
            raise
    
    def translate_text(self, text: str, target_lang: str, source_lang: str = "auto") -> str:
        """翻译单段文本。
        
        Args:
            text: 待翻译的文本
            target_lang: 目标语言代码
            source_lang: 源语言代码（auto 为自动检测）
            
        Returns:
            翻译后的文本
        """
        if not self.is_configured():
            raise ValueError("API Key 未配置")
        
        if not text or not text.strip():
            return text
        
        lang_names = {
            "zh": "中文",
            "en": "英文",
            "ja": "日文",
            "ko": "韩文",
            "fr": "法文",
            "de": "德文",
            "es": "西班牙文",
            "ru": "俄文",
            "pt": "葡萄牙文",
            "it": "意大利文",
            "auto": "自动检测",
        }
        
        source_name = lang_names.get(source_lang, source_lang)
        target_name = lang_names.get(target_lang, target_lang)
        
        prompt = f"""你是一个专业的翻译助手。请将以下文本翻译成{target_name}。

要求：
1. 保持原文的语义和风格
2. 翻译要自然流畅，符合目标语言的表达习惯
3. 只返回翻译结果，不要添加任何解释或标注
4. 源语言：{source_name}

原文：
{text}

翻译："""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": len(text) * 4 + 100,
        }
        
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(self.api_url, json=data, headers=headers)
                response.raise_for_status()
                result = response.json()
                
                # 检查返回格式
                if "choices" not in result:
                    error_msg = result.get("error", {}).get("message", str(result))
                    raise ValueError(f"API 返回格式异常: {error_msg}")
                
                if not result["choices"]:
                    raise ValueError("API 返回空的 choices")
                
                translated = result["choices"][0]["message"]["content"].strip()
                
                # 移除可能的思考过程标签
                if "<think>" in translated and "</think>" in translated:
                    think_end = translated.find("</think>")
                    translated = translated[think_end + 8:].strip()
                
                return translated
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ValueError("API Key 无效，请检查后重试")
            elif e.response.status_code == 429:
                raise ValueError("请求过于频繁，请稍后重试")
            else:
                raise ValueError(f"API 请求失败: {e.response.status_code}")
        except httpx.TimeoutException:
            raise ValueError("请求超时，请检查网络后重试")
        except Exception as e:
            raise ValueError(f"翻译失败: {e}")
    
    def translate_segments(
        self,
        segments: List[Dict[str, Any]],
        target_lang: str,
        source_lang: str = "auto",
        progress_callback: Optional[Callable[[str, float], None]] = None,
        batch_size: int = 50
    ) -> List[Dict[str, Any]]:
        """翻译字幕分段列表。
        
        优化策略：
        - 短文本（< 3000 字）：一次性处理所有分段，只需 1 次 API 调用
        - 长文本：按批次处理，每批最多 50 个分段
        
        Args:
            segments: 字幕分段列表
            target_lang: 目标语言代码
            source_lang: 源语言代码
            progress_callback: 进度回调函数
            batch_size: 每批处理的分段数量（默认 50）
            
        Returns:
            翻译后的字幕分段列表（每个分段添加 translated_text 字段）
        """
        if not self.is_configured():
            raise ValueError("API Key 未配置")
        
        if not segments:
            return segments
        
        total = len(segments)
        all_texts = [seg.get("text", "").strip() for seg in segments]
        total_chars = sum(len(t) for t in all_texts)
        
        # 一次性处理所有分段
        if progress_callback:
            progress_callback(f"AI 翻译中 (共 {total} 段, {total_chars} 字)...", 0.3)
        
        combined_text = "\n---\n".join(all_texts)
        
        try:
            translated_combined = self._translate_batch(combined_text, target_lang, source_lang, total)
            translated_texts = translated_combined.split("\n---\n")
            
            if len(translated_texts) != total:
                logger.warning(f"AI 返回分段数 {len(translated_texts)} 与原始 {total} 不匹配，尝试分批处理")
                return self._translate_segments_batched(segments, target_lang, source_lang, progress_callback, batch_size)
            
            translated_segments = []
            for i, seg in enumerate(segments):
                new_seg = seg.copy()
                new_seg["translated_text"] = translated_texts[i].strip()
                translated_segments.append(new_seg)
            
            if progress_callback:
                progress_callback("AI 翻译完成", 1.0)
            
            logger.info(f"AI 字幕翻译完成: {total} 个分段, {total_chars} 字 (单次请求)")
            return translated_segments
            
        except Exception as e:
            logger.warning(f"一次性翻译失败，尝试分批处理: {e}")
            return self._translate_segments_batched(segments, target_lang, source_lang, progress_callback, batch_size)
    
    def _translate_segments_batched(
        self,
        segments: List[Dict[str, Any]],
        target_lang: str,
        source_lang: str,
        progress_callback: Optional[Callable[[str, float], None]],
        batch_size: int
    ) -> List[Dict[str, Any]]:
        """分批翻译字幕分段。"""
        total = len(segments)
        translated_segments = []
        
        for i in range(0, total, batch_size):
            batch = segments[i:i + batch_size]
            batch_texts = [seg.get("text", "").strip() for seg in batch]
            
            if progress_callback:
                progress = i / total
                progress_callback(f"AI 翻译中 ({i}/{total})...", progress)
            
            combined_text = "\n---\n".join(batch_texts)
            
            try:
                translated_combined = self._translate_batch(combined_text, target_lang, source_lang, len(batch))
                translated_texts = translated_combined.split("\n---\n")
                
                if len(translated_texts) != len(batch):
                    translated_texts = []
                    for text in batch_texts:
                        try:
                            translated = self.translate_text(text, target_lang, source_lang)
                            translated_texts.append(translated)
                        except Exception:
                            translated_texts.append(text)
                
                for j, seg in enumerate(batch):
                    new_seg = seg.copy()
                    if j < len(translated_texts):
                        new_seg["translated_text"] = translated_texts[j].strip()
                    else:
                        new_seg["translated_text"] = seg.get("text", "")
                    translated_segments.append(new_seg)
                    
            except Exception as e:
                logger.warning(f"批量翻译失败，保留原文: {e}")
                for seg in batch:
                    new_seg = seg.copy()
                    new_seg["translated_text"] = seg.get("text", "")
                    translated_segments.append(new_seg)
        
        if progress_callback:
            progress_callback("AI 翻译完成", 1.0)
        
        logger.info(f"AI 字幕翻译完成: {total} 个分段 (分批处理)")
        return translated_segments
    
    def _translate_batch(self, combined_text: str, target_lang: str, source_lang: str, count: int) -> str:
        """批量翻译合并的文本。"""
        if not combined_text.strip():
            return combined_text
        
        lang_names = {
            "zh": "中文",
            "en": "英文",
            "ja": "日文",
            "ko": "韩文",
            "fr": "法文",
            "de": "德文",
            "es": "西班牙文",
            "ru": "俄文",
            "pt": "葡萄牙文",
            "it": "意大利文",
            "auto": "自动检测",
        }
        
        source_name = lang_names.get(source_lang, source_lang)
        target_name = lang_names.get(target_lang, target_lang)
        
        prompt = f"""你是一个专业的翻译助手。下面是 {count} 段字幕文本，用 "---" 分隔。请将每段文本翻译成{target_name}。

要求：
1. 保持原文的语义和风格
2. 翻译要自然流畅
3. 保持 "---" 分隔符，确保输出的段落数量与输入一致
4. 只返回翻译结果，不要添加任何解释
5. 源语言：{source_name}

原文：
{combined_text}

翻译："""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": len(combined_text) * 4 + 200,
        }
        
        with httpx.Client(timeout=120.0) as client:
            response = client.post(self.api_url, json=data, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            # 检查返回格式
            if "choices" not in result:
                error_msg = result.get("error", {}).get("message", str(result))
                logger.error(f"API 返回格式异常: {error_msg}")
                raise ValueError(f"API 返回格式异常: {error_msg}")
            
            if not result["choices"]:
                logger.error("API 返回空的 choices")
                raise ValueError("API 返回空的 choices")
            
            translated = result["choices"][0]["message"]["content"].strip()
            
            # 移除可能的思考过程标签
            if "<think>" in translated and "</think>" in translated:
                think_end = translated.find("</think>")
                translated = translated[think_end + 8:].strip()
            
            return translated

