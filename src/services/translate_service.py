# -*- coding: utf-8 -*-
"""翻译服务模块。

使用 Bing 翻译 API 进行文本翻译。
"""

import httpx
import asyncio
from typing import Optional, Dict, Any
from utils import logger


# 错误代码映射
ERROR_CODES = {
    "400000": "某个请求输入无效。",
    "400001": "scope参数无效。",
    "400002": "category参数无效。",
    "400003": "语言说明符缺失或无效。",
    "400004": "目标脚本说明符缺失或无效。",
    "400005": "输入文本缺失或无效。",
    "400006": "语言和脚本的组合无效。",
    "400019": "指定的某个语言不受支持。",
    "400035": "源语言无效。",
    "400036": "目标语言缺失或无效。",
    "400050": "输入文本过长。",
    "401000": "由于凭据缺失或无效，请求未授权。",
    "403001": "订阅已超过免费配额。",
    "429000": "请求过于频繁，服务器拒绝了请求。",
    "500000": "发生了意外错误。",
    "503000": "服务暂时不可用。",
}

# 支持的语言列表
SUPPORTED_LANGUAGES = {
    "zh-Hans": "简体中文",
    "zh-Hant": "繁体中文",
    "en": "英语",
    "ja": "日语",
    "ko": "韩语",
    "fr": "法语",
    "de": "德语",
    "es": "西班牙语",
    "it": "意大利语",
    "pt": "葡萄牙语",
    "ru": "俄语",
    "ar": "阿拉伯语",
    "th": "泰语",
    "vi": "越南语",
    "id": "印尼语",
    "ms": "马来语",
    "hi": "印地语",
    "nl": "荷兰语",
    "pl": "波兰语",
    "tr": "土耳其语",
}


class TranslateService:
    """Bing 翻译服务。"""
    
    def __init__(self):
        self._auth_token: Optional[str] = None
        self._token_lock = asyncio.Lock()
    
    async def _get_auth_token(self) -> str:
        """获取认证令牌（异步）。"""
        async with self._token_lock:
            ua = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
            }
            auth_url = "https://edge.microsoft.com/translate/auth"
            
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(auth_url, headers=ua)
                    if resp.status_code == 200:
                        self._auth_token = resp.text
                        return self._auth_token
                    else:
                        logger.error(f"获取翻译认证令牌失败: {resp.status_code}")
                        return ""
            except Exception as ex:
                logger.error(f"获取翻译认证令牌异常: {ex}")
                return ""
    
    async def translate(
        self,
        text: str,
        target_lang: str = "zh-Hans",
        source_lang: str = "",
    ) -> Dict[str, Any]:
        """翻译文本（异步）。
        
        Args:
            text: 要翻译的文本
            target_lang: 目标语言代码
            source_lang: 源语言代码（空字符串表示自动检测）
        
        Returns:
            翻译结果字典，包含 code、message、data
        """
        if not text or not text.strip():
            return {
                "code": 200,
                "message": "success",
                "data": {"text": ""}
            }
        
        # 获取认证令牌
        auth_token = await self._get_auth_token()
        if not auth_token:
            return {
                "code": 401,
                "message": "无法获取认证令牌",
                "data": {"text": text}
            }
        
        url = f"https://api-edge.cognitive.microsofttranslator.com/translate?from={source_lang}&to={target_lang}&api-version=3.0&includeSentenceLength=true"
        
        post_data = [{"Text": text}]
        
        headers = {
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "authorization": f"Bearer {auth_token}",
            "content-type": "application/json",
            "sec-ch-ua": "\"Microsoft Edge\";v=\"120\", \"Chromium\";v=\"120\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "referer": "https://www.bing.com/",
        }
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json=post_data, headers=headers)
                
                try:
                    data = resp.json()
                except Exception:
                    logger.error(f"翻译响应解析失败: {resp.text}")
                    return {
                        "code": 500,
                        "message": "响应解析失败",
                        "data": {"text": text}
                    }
                
                if isinstance(data, dict) and "error" in data:
                    error_code = str(data["error"].get("code", ""))
                    msg = ERROR_CODES.get(error_code, f"未知错误: {error_code}")
                    logger.error(f"翻译失败: {msg}")
                    return {
                        "code": int(error_code) if error_code.isdigit() else 500,
                        "message": msg,
                        "data": {"text": text}
                    }
                else:
                    translated_text = data[0]["translations"][0]["text"]
                    return {
                        "code": 200,
                        "message": "success",
                        "data": {"text": translated_text}
                    }
        
        except httpx.TimeoutException:
            logger.error("翻译请求超时")
            return {
                "code": 408,
                "message": "请求超时",
                "data": {"text": text}
            }
        except Exception as ex:
            logger.error(f"翻译异常: {ex}")
            return {
                "code": 500,
                "message": str(ex),
                "data": {"text": text}
            }
    
    async def translate_batch(
        self,
        texts: list,
        target_lang: str = "zh-Hans",
        source_lang: str = "",
        progress_callback=None,
    ) -> list:
        """批量翻译文本（异步）。
        
        Args:
            texts: 要翻译的文本列表
            target_lang: 目标语言代码
            source_lang: 源语言代码
            progress_callback: 进度回调函数 (current, total)
        
        Returns:
            翻译结果列表
        """
        results = []
        total = len(texts)
        
        for i, text in enumerate(texts):
            result = await self.translate(text, target_lang, source_lang)
            results.append(result["data"]["text"])
            
            if progress_callback:
                progress_callback(i + 1, total)
            
            # 添加小延迟避免请求过于频繁
            if i < total - 1:
                await asyncio.sleep(0.05)
        
        return results
    
    @staticmethod
    def get_supported_languages() -> Dict[str, str]:
        """获取支持的语言列表。"""
        return SUPPORTED_LANGUAGES.copy()
