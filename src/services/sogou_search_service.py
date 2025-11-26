"""
搜狗识图服务模块

对搜狗识图API进行封装，提供异步接口供视图层调用。
"""

import uuid
import httpx
import re
from typing import Dict, List, Optional


class SogouSearchService:
    """搜狗识图搜索服务
    
    提供图片上传、相似图片搜索等功能。
    """
    
    UPLOAD_URL: str = "https://pic.sogou.com/pic/upload_pic.jsp"
    SEARCH_URL: str = "https://ris.sogou.com/risapi/pc/sim"

    def __init__(self) -> None:
        """初始化服务"""
        self.client: Optional[httpx.AsyncClient] = None

    def _ensure_client(self) -> httpx.AsyncClient:
        """确保客户端存在"""
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=30)
        return self.client

    async def close(self) -> None:
        """关闭HTTP客户端连接"""
        if self.client:
            await self.client.aclose()
            self.client = None

    def _is_url(self, path: str) -> bool:
        """判断输入是否为URL"""
        return path.startswith(('http://', 'https://'))

    async def upload_image(self, image_path_or_url: str) -> Dict:
        """上传图片到搜狗识图
        
        Args:
            image_path_or_url (str): 本地图片文件路径或网络图片URL
            
        Returns:
            Dict: 上传结果，包含status和image_url字段
            
        Raises:
            httpx.HTTPError: HTTP请求异常
            FileNotFoundError: 图片文件不存在
        """
        if self._is_url(image_path_or_url):
            # 如果是URL，直接返回，不需要上传
            return {
                "status": 0,
                "image_url": image_path_or_url,
                "message": "URL图片无需上传"
            }
        else:
            # 本地文件：上传到搜狗
            return await self._upload_local_image(image_path_or_url)

    async def _upload_local_image(self, image_path: str) -> Dict:
        """上传本地图片文件
        
        Args:
            image_path (str): 本地图片路径
            
        Returns:
            Dict: 上传结果，包含status和image_url
            
        Raises:
            FileNotFoundError: 文件不存在
        """
        client = self._ensure_client()
        
        upload_uuid = str(uuid.uuid4())
        token = str(uuid.uuid4())
        url = f"{self.UPLOAD_URL}?uuid={upload_uuid}"
        
        with open(image_path, "rb") as f:
            files = {"pic_path": (image_path, f, "image/jpeg")}
            data = {"token": token}
            
            resp = await client.post(url, files=files, data=data)
            resp.raise_for_status()
            
            # 从响应中提取图片URL
            response_text = resp.text
            
            # 解析返回的图片URL
            # 搜狗返回格式通常是: http://img04.sogoucdn.com/app/a/100520146/xxxxx
            image_url = self._extract_image_url(response_text)
            
            if image_url:
                return {
                    "status": 0,
                    "image_url": image_url,
                    "message": "上传成功"
                }
            else:
                return {
                    "status": -1,
                    "image_url": "",
                    "message": "上传失败，无法获取图片URL"
                }

    @staticmethod
    def _extract_image_url(response_text: str) -> str:
        """从响应文本中提取图片URL"""
        # 搜狗返回的是图片URL字符串
        response_text = response_text.strip()
        if response_text.startswith("http"):
            return response_text
        return ""

    @staticmethod
    def is_upload_success(result: Dict) -> bool:
        """检查上传是否成功
        
        Args:
            result (Dict): upload_image方法返回的结果
            
        Returns:
            bool: 上传成功返回True，否则返回False
        """
        return result.get("status") == 0 and result.get("image_url", "")

    async def search_similar_images(self, image_url: str, start: int = 0, 
                                   page_size: int = 20) -> Dict:
        """搜索相似图片
        
        Args:
            image_url (str): 图片URL
            start (int): 起始位置，用于分页（start = (page-1) * page_size）
            page_size (int): 每页数量
            
        Returns:
            Dict: 搜索结果，包含items列表
            
        Raises:
            httpx.HTTPError: HTTP请求异常
        """
        client = self._ensure_client()
        
        params = {
            "query": image_url,
            "start": start,
            "plevel": -1  # 相似度等级，-1表示不限制
        }
        
        resp = await client.get(self.SEARCH_URL, params=params)
        resp.raise_for_status()
        
        data = resp.json()
        items = data.get("data", {}).get("items", [])
        
        # 限制返回数量
        items = items[:page_size]
        
        # 检查是否还有更多结果
        has_more = len(items) >= page_size
        
        return {
            "status": 0,
            "items": items,
            "has_more": has_more,
            "total": len(items)
        }
