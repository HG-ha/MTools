# -*- coding: utf-8 -*-
"""HTTP 服务模块。

提供基于 httpx 的 HTTP 请求功能。
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx

from utils import logger


class HttpService:
    """HTTP 服务类。
    
    提供发送 HTTP 请求和处理响应的功能。
    """
    
    # 支持的请求方法
    METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
    
    # 常用请求头预设
    COMMON_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }
    
    def __init__(self):
        """初始化 HTTP 服务。"""
        self.client: Optional[httpx.Client] = None
        self.timeout = 30.0  # 默认超时 30 秒
    
    def _get_client(
        self,
        follow_redirects: bool = True,
        timeout: float = None,
        proxies: Optional[Dict[str, str]] = None
    ) -> httpx.Client:
        """获取或创建 HTTP 客户端。
        
        Args:
            follow_redirects: 是否跟随重定向
            timeout: 超时时间（秒）
            proxies: 代理配置字典
            
        Returns:
            httpx.Client 实例
        """
        if timeout is None:
            timeout = self.timeout
        
        client_kwargs = {
            "follow_redirects": follow_redirects,
            "timeout": timeout,
            "verify": False,  # 允许不验证 SSL 证书
        }
        
        # 添加代理配置
        if proxies:
            client_kwargs["proxies"] = proxies
        
        return httpx.Client(**client_kwargs)
    
    def parse_headers(self, headers_text: str) -> Dict[str, str]:
        """解析请求头文本。
        
        Args:
            headers_text: 请求头文本，每行一个键值对，格式为 "Key: Value"
            
        Returns:
            解析后的请求头字典
        """
        headers = {}
        if not headers_text:
            return headers
        
        for line in headers_text.strip().split('\n'):
            line = line.strip()
            if not line or ':' not in line:
                continue
            
            key, value = line.split(':', 1)
            headers[key.strip()] = value.strip()
        
        return headers
    
    def parse_query_params(self, params_text: str) -> Dict[str, str]:
        """解析查询参数文本。
        
        Args:
            params_text: 查询参数文本，每行一个键值对，格式为 "key=value"
            
        Returns:
            解析后的查询参数字典
        """
        params = {}
        if not params_text:
            return params
        
        for line in params_text.strip().split('\n'):
            line = line.strip()
            if not line or '=' not in line:
                continue
            
            key, value = line.split('=', 1)
            params[key.strip()] = value.strip()
        
        return params
    
    def parse_proxy(self, proxy_text: str) -> Optional[Dict[str, str]]:
        """解析代理配置。
        
        Args:
            proxy_text: 代理文本，格式如:
                - http://proxy.example.com:8080
                - socks5://127.0.0.1:1080
                - http://user:pass@proxy.com:8080
            
        Returns:
            代理配置字典，如 {"http://": "...", "https://": "..."}
            如果为空则返回 None
        """
        if not proxy_text or not proxy_text.strip():
            return None
        
        proxy_url = proxy_text.strip()
        
        # 支持的代理协议
        if proxy_url.startswith(('http://', 'https://', 'socks5://', 'socks5h://')):
            # httpx 的代理格式：对所有请求使用相同代理
            return {
                "http://": proxy_url,
                "https://": proxy_url,
            }
        else:
            # 如果没有协议前缀，假定为 http 代理
            proxy_url = f"http://{proxy_url}"
            return {
                "http://": proxy_url,
                "https://": proxy_url,
            }
    
    def send_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        body: Optional[str] = None,
        body_type: str = "raw",
        files: Optional[Dict[str, str]] = None,
        proxy: Optional[str] = None,
        follow_redirects: bool = True,
        timeout: float = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """发送 HTTP 请求。
        
        Args:
            method: HTTP 方法（GET, POST, PUT, DELETE 等）
            url: 请求 URL
            headers: 请求头字典
            params: URL 查询参数字典
            body: 请求体内容
            body_type: 请求体类型（raw, json, form）
            files: 文件字典 {field_name: file_path}
            proxy: 代理地址（如 http://127.0.0.1:8080 或 socks5://127.0.0.1:1080）
            follow_redirects: 是否跟随重定向
            timeout: 超时时间（秒）
            
        Returns:
            (是否成功, 结果字典)
        """
        method = method.upper()
        
        if method not in self.METHODS:
            return False, {"error": f"不支持的 HTTP 方法: {method}"}
        
        if not url:
            return False, {"error": "URL 不能为空"}
        
        # 添加协议前缀（如果没有）
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        opened_files = []
        try:
            # 合并请求头
            final_headers = self.COMMON_HEADERS.copy()
            if headers:
                final_headers.update(headers)
            
            # 准备请求参数
            request_kwargs = {
                "method": method,
                "url": url,
                "headers": final_headers,
            }
            
            # 添加查询参数
            if params:
                request_kwargs["params"] = params
            
            # 处理请求体
            if method in ["POST", "PUT", "PATCH"]:
                # 优先处理文件上传 (Multipart)
                if files:
                    files_data = {}
                    for field_name, file_path in files.items():
                        try:
                            f = open(file_path, "rb")
                            opened_files.append(f)
                            files_data[field_name] = f
                        except Exception as e:
                            return False, {"error": f"无法打开文件 {file_path}: {str(e)}"}
                    
                    request_kwargs["files"] = files_data
                    # 如果有额外的表单数据
                    if body:
                        try:
                            form_data = {}
                            for line in body.strip().split('\n'):
                                if '=' in line:
                                    key, value = line.split('=', 1)
                                    form_data[key.strip()] = value.strip()
                            request_kwargs["data"] = form_data
                        except Exception as e:
                            pass # 忽略非关键错误
                            
                    # httpx 会自动设置 Content-Type: multipart/form-data
                    if "Content-Type" in final_headers:
                        del final_headers["Content-Type"]
                        
                # 普通请求体处理
                elif body:
                    if body_type == "json":
                        try:
                            json_data = json.loads(body)
                            request_kwargs["json"] = json_data
                            final_headers["Content-Type"] = "application/json"
                        except json.JSONDecodeError as e:
                            return False, {"error": f"JSON 格式错误: {str(e)}"}
                    elif body_type == "form":
                        try:
                            # 解析表单数据
                            form_data = {}
                            for line in body.strip().split('\n'):
                                if '=' in line:
                                    key, value = line.split('=', 1)
                                    form_data[key.strip()] = value.strip()
                            request_kwargs["data"] = form_data
                            final_headers["Content-Type"] = "application/x-www-form-urlencoded"
                        except Exception as e:
                            return False, {"error": f"表单数据解析错误: {str(e)}"}
                    else:  # raw
                        request_kwargs["content"] = body.encode('utf-8')
            
            # 解析代理配置
            proxies = self.parse_proxy(proxy) if proxy else None
            
            # 创建客户端并发送请求
            with self._get_client(follow_redirects=follow_redirects, timeout=timeout, proxies=proxies) as client:
                import time
                start_time = time.time()
                
                response = client.request(**request_kwargs)
                
                end_time = time.time()
                time_ms = int((end_time - start_time) * 1000)
                
                # 尝试解析响应体
                try:
                    # 尝试解析为 JSON
                    response_body = response.json()
                    body_text = json.dumps(response_body, ensure_ascii=False, indent=2)
                    content_type = "application/json"
                except:
                    # 使用文本
                    body_text = response.text
                    content_type = response.headers.get("Content-Type", "text/plain")
                
                # 构建响应字典
                result = {
                    "status_code": response.status_code,
                    "status_text": response.reason_phrase,
                    "headers": dict(response.headers),
                    "body": body_text,
                    "content_type": content_type,
                    "time_ms": time_ms,
                    "size_bytes": len(response.content),
                }
                
                return True, result
                
        except httpx.TimeoutException:
            return False, {"error": f"请求超时（{timeout}秒）"}
        except httpx.ConnectError as e:
            return False, {"error": f"连接失败: {str(e)}"}
        except httpx.HTTPError as e:
            return False, {"error": f"HTTP 错误: {str(e)}"}
        except Exception as e:
            logger.error(f"HTTP 请求错误: {e}")
            import traceback
            traceback.print_exc()
            return False, {"error": f"请求失败: {str(e)}"}
        finally:
            # 关闭所有打开的文件
            for f in opened_files:
                try:
                    f.close()
                except:
                    pass
    
    def get_curl_command(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        body: Optional[str] = None,
        body_type: str = "raw",
        files: Optional[Dict[str, str]] = None,
    ) -> str:
        """生成等效的 curl 命令。
        
        Args:
            method: HTTP 方法
            url: 请求 URL
            headers: 请求头字典
            params: URL 查询参数字典
            body: 请求体内容
            body_type: 请求体类型
            files: 文件字典
            
        Returns:
            curl 命令字符串
        """
        # 添加协议前缀
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # 添加查询参数
        if params:
            url += '?' + urlencode(params)
        
        # 构建 curl 命令
        parts = [f'curl -X {method.upper()}']
        
        # 添加请求头
        # 如果是 multipart，curl会自动处理 Content-Type，所以不需要手动添加
        # 如果是 raw/json，保留 Content-Type
        if headers:
            for key, value in headers.items():
                if files and key.lower() == 'content-type':
                    continue
                parts.append(f'-H "{key}: {value}"')
        
        # 处理 multipart/form-data
        if files:
            # 添加文件字段
            for field_name, file_path in files.items():
                parts.append(f'-F "{field_name}=@{file_path}"')
            
            # 添加表单字段
            if body:
                try:
                    # 解析 form 数据
                    for line in body.strip().split('\n'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            parts.append(f'-F "{key.strip()}={value.strip()}"')
                except:
                    pass
        
        # 处理普通请求体
        elif body and method.upper() in ["POST", "PUT", "PATCH"]:
            if body_type == "json":
                # JSON 格式
                # 尝试美化 JSON 用于显示
                try:
                    json_obj = json.loads(body)
                    json_str = json.dumps(json_obj)
                    # 转义单引号
                    json_str = json_str.replace("'", "'\\''")
                    parts.append(f"-d '{json_str}'")
                except:
                    parts.append(f"-d '{body}'")
            elif body_type == "form":
                # Form 格式：转换为 -d "key=value" 或 --data-urlencode
                try:
                    for line in body.strip().split('\n'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            # 使用 --data-urlencode 自动处理编码
                            parts.append(f'--data-urlencode "{key.strip()}={value.strip()}"')
                except:
                    parts.append(f"-d '{body}'")
            else:
                # Raw 格式
                # 转义单引号
                escaped_body = body.replace("'", "'\\''")
                parts.append(f"-d '{escaped_body}'")
        
        # 添加 URL（放在最后）
        parts.append(f'"{url}"')
        
        return ' \\\n  '.join(parts)
    
    def close(self):
        """关闭 HTTP 客户端。"""
        if self.client:
            self.client.close()
            self.client = None

