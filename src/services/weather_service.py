# -*- coding: utf-8 -*-
"""天气服务模块

提供天气信息查询功能，使用 MSN 天气 API。
"""

import httpx
import json
from typing import Dict, Optional, Tuple
import asyncio


class WeatherService:
    """天气服务类
    
    提供天气信息查询功能。
    """
    
    # 默认坐标（上海）
    DEFAULT_LAT = 31.2559617
    DEFAULT_LON = 121.2989499
    
    def __init__(self):
        """初始化天气服务"""
        self.client: Optional[httpx.AsyncClient] = None
    
    def _ensure_client(self) -> httpx.AsyncClient:
        """确保客户端存在"""
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=10)
        return self.client
    
    async def close(self):
        """关闭客户端连接"""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    async def search_location(self, city_name: str) -> Optional[Dict[str, float]]:
        """搜索城市坐标
        
        Args:
            city_name: 城市名称
            
        Returns:
            包含 lat 和 lon 的字典，失败返回 None
        """
        client = self._ensure_client()
        
        try:
            # 使用 Bing Places API
            search_url = f"https://cn.bing.com/api/v6/Places/AutoSuggest"
            params = {
                'appid': 'EDEC3CB74CF190BBBE26DF7938F3D961E925F593',
                'count': 5,
                'q': city_name,
                'localcircularview': '40,116,100',
                'setmkt': 'zh-cn',
                'setlang': 'zh-cn',
                'types': 'Place,Address,Business',
                'abbrtext': 1,
                'structuredaddress': 'true',
                'strucaddrread': 1,
                'setflight': ''
            }
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = await client.get(search_url, params=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if 'value' in data and data['value']:
                    # 优先选择类型为 Place 的结果
                    places = [item for item in data['value'] if item.get('_type') == 'Place']
                    
                    if not places:
                        # 如果没有 Place 类型，则选择第一个有坐标的结果
                        places = [item for item in data['value'] if 'geo' in item]
                    
                    if places:
                        location = places[0]
                        if 'geo' in location and 'latitude' in location['geo'] and 'longitude' in location['geo']:
                            return {
                                'lat': location['geo']['latitude'],
                                'lon': location['geo']['longitude']
                            }
        except Exception as e:
            print(f"Bing API 搜索失败: {e}")
        
        try:
            # 备用方法：使用 OpenStreetMap
            search_url = f"https://nominatim.openstreetmap.org/search"
            params = {
                'q': city_name,
                'format': 'json',
                'limit': 1
            }
            headers = {
                'User-Agent': 'MSN Weather App (Python)'
            }
            
            response = await client.get(search_url, params=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    return {
                        'lat': float(data[0]['lat']),
                        'lon': float(data[0]['lon'])
                    }
        except Exception as e:
            print(f"OpenStreetMap 搜索失败: {e}")
        
        return None
    
    async def get_weather_detailed(self, lat: float = None, lon: float = None) -> Optional[Dict]:
        """获取详细的 MSN 天气数据
        
        Args:
            lat: 纬度，默认使用上海坐标
            lon: 经度，默认使用上海坐标
            
        Returns:
            天气数据字典，失败返回 None
        """
        if lat is None:
            lat = self.DEFAULT_LAT
        if lon is None:
            lon = self.DEFAULT_LON
        
        client = self._ensure_client()
        
        try:
            api_url = "https://api.msn.cn/weatherfalcon/weather/current"
            params = {
                'apikey': 'j5i4gDqHL6nGYwx5wi5kRhXjtf2c5qgFX9fzfk0TOo',
                'activityId': '08288E0B-4966-4C36-88E8-4E1739BA6862',
                'ocid': 'msftweather',
                'cm': 'zh-cn',
                'it': 'edgeid',
                'user': 'm-15F638649D00626A086D2DB29CD263ED',
                'scn': 'APP_ANON',
                'latLongList': f'{lat},{lon}',
                'locale': 'zh-cn',
                'units': 'C',
                'appId': '9e21380c-ff19-4c78-b4ea-19558e93a5d3',
                'wrapOData': 'false',
                'includenowcasting': 'true',
                'usemscloudcover': 'true',
                'getCmaAlert': 'true'
            }
            headers = {
                'accept': '*/*',
                'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'origin': 'https://www.msn.cn',
                'referer': 'https://www.msn.cn/',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = await client.get(api_url, params=params, headers=headers)
            
            if response.status_code == 200 and response.text.strip():
                return response.json()
        except Exception as e:
            print(f"获取天气数据失败: {e}")
        
        return None
    
    async def get_city_from_ip(self, ip: str = None) -> Optional[str]:
        """通过 IP 地址查询城市信息
        
        Args:
            ip: IP 地址，为 None 时自动获取当前公网 IP
            
        Returns:
            城市名称，失败返回 None
        """
        client = self._ensure_client()
        
        # 如果没有提供 IP，先获取公网 IP
        if ip is None:
            try:
                
                # 尝试多个仅支持 IPv4 的 API 服务
                ip_services = [
                    "https://ipv4.icanhazip.com",
                    "https://api.ipify.org?format=text",  # 仅返回 IPv4
                    "https://api4.ipify.org",  # 专用 IPv4 端点
                    "https://v4.ident.me",  # 专用 IPv4 端点
                    "http://ipv4.myip.com.tw",  # 备用服务
                ]
                
                ip = ""
                for service_url in ip_services:
                    try:
                        ip_response = await client.get(service_url, timeout=5)
                        if ip_response.status_code == 200:
                            ip = ip_response.text.strip()
                            # 验证是否为 IPv4 格式（包含点且不包含冒号）
                            if '.' in ip and ':' not in ip and len(ip.split('.')) == 4:
                                break
                    except Exception as e:
                        print(f"从 {service_url} 获取 IP 失败: {e}")
                        continue
                
                if not ip:
                    print("所有 IP 获取服务均失败")
                        
            except Exception as e:
                print(f"获取公网 IP 失败: {e}")
                ip = ""
        
        # 如果还是没有 IP，使用空字符串（淘宝 API 会自动识别）
        if not ip:
            ip = ""
        
        try:
            api_url = "https://ip.taobao.com/outGetIpInfo"
            
            data = {
                'ip': ip,
                'accessKey': 'alibaba-inc'
            }
            headers = {
                'accept': '*/*',
                'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://ip.taobao.com',
                'referer': f'https://ip.taobao.com/ipSearch?ipAddr={ip}',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = await client.post(api_url, data=data, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('code') == 0 and 'data' in result:
                    location_data = result['data']
                    
                    # 优先使用城市，如果城市是区级名称（如"普陀区"），则使用省份/地区
                    city = location_data.get('city', '')
                    region = location_data.get('region', '')
                    country = location_data.get('country', '')
                    
                    # 如果城市或地区是 "XX"（未知），则使用国家
                    if city == 'XX' or region == 'XX':
                        if country and country != 'XX':
                            return country
                    
                    # 如果城市名包含"区"或"县"，说明是区县级，使用上级地区
                    if city and not ('区' in city or '县' in city):
                        return city
                    elif region:
                        return region
                    elif city:
                        # 如果只有区县名，去掉"区"或"县"后缀
                        city_clean = city.replace('区', '').replace('县', '')
                        return city_clean
        except Exception as e:
            print(f"IP 查询失败: {e}")
        
        return None
    
    def format_weather_simple(self, weather_data: Dict, fallback_location: str = None) -> Optional[Dict]:
        """将天气数据格式化为简单版本（用于标题栏显示）
        
        Args:
            weather_data: 原始天气数据
            fallback_location: 可选的回退位置名称（优先用于替换非中文 provider 名称）
            
        Returns:
            格式化后的天气数据，包含：
            - temperature: 温度
            - condition: 天气状况
            - icon: 天气图标名称
            - location: 位置名称
        """
        try:
            if weather_data and 'responses' in weather_data and weather_data['responses']:
                response_item = weather_data['responses'][0]
                weather_list = response_item.get('weather', [])
                source = response_item.get('source', {})
                
                if weather_list:
                    current_weather = weather_list[0]
                    current_data = current_weather.get('current', {})
                    location = source.get('location', {})
                    
                    # 尝试获取 provider 返回的位置名称
                    provider_loc = location.get('Name', '')

                    # 检查字符串是否包含中文字符
                    def contains_cjk(s: str) -> bool:
                        try:
                            return any('\u4e00' <= ch <= '\u9fff' for ch in s)
                        except Exception:
                            return False

                    if provider_loc:
                        if not contains_cjk(provider_loc) and fallback_location:
                            display_loc = fallback_location
                        else:
                            display_loc = provider_loc
                    else:
                        display_loc = fallback_location or '未知'

                    return {
                        'temperature': current_data.get('temp'),
                        'condition': current_data.get('cap'),
                        'icon': self._get_weather_icon(current_data.get('cap', '')),
                        'location': display_loc,
                        'feels_like': current_data.get('feels'),
                        'humidity': current_data.get('rh')
                    }
        except Exception as e:
            print(f"格式化天气数据失败: {e}")
        
        return None
    
    def _get_weather_icon(self, condition: str) -> str:
        """根据天气状况获取对应的图标名称
        
        Args:
            condition: 天气状况描述
            
        Returns:
            Flet 图标名称
        """
        condition = condition.lower() if condition else ''
        
        # 晴天
        if '晴' in condition or 'sunny' in condition or 'clear' in condition:
            return 'WB_SUNNY'
        # 多云
        elif '云' in condition or 'cloud' in condition:
            return 'CLOUD'
        # 雨
        elif '雨' in condition or 'rain' in condition:
            return 'UMBRELLA'
        # 雪
        elif '雪' in condition or 'snow' in condition:
            return 'AC_UNIT'
        # 雾霾
        elif '雾' in condition or '霾' in condition or 'fog' in condition or 'haze' in condition:
            return 'FOGGY'
        # 雷暴
        elif '雷' in condition or 'thunder' in condition or 'storm' in condition:
            return 'BOLT'
        # 默认
        else:
            return 'WB_CLOUDY'
    
    async def get_current_location_weather(self, preferred_city: str = None) -> Optional[Dict]:
        """获取当前位置的天气信息
        
        Args:
            preferred_city: 用户偏好的城市，如果提供则优先使用
        
        Returns:
            简化的天气数据字典
        """
        city = preferred_city
        
        # 如果没有提供偏好城市，通过 IP 获取
        if not city:
            city = await self.get_city_from_ip()
        
        if city:
            # 搜索城市坐标
            location = await self.search_location(city)
            
            if location:
                # 获取天气数据
                weather_data = await self.get_weather_detailed(location['lat'], location['lon'])
                if weather_data:
                    formatted = self.format_weather_simple(weather_data, fallback_location=city)
                    return formatted
        
        # 如果失败，使用默认位置（上海）
        weather_data = await self.get_weather_detailed()
        if weather_data:
            return self.format_weather_simple(weather_data)
        
        return None
