# -*- coding: utf-8 -*-
"""天气服务模块

提供天气信息查询功能，使用 MSN 天气 API。
"""

import httpx
import json
from typing import Dict, Optional, Tuple
from utils import logger
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
            logger.error(f"Bing API 搜索失败: {e}")
        
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
            logger.error(f"OpenStreetMap 搜索失败: {e}")
        
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
            logger.error(f"获取天气数据失败: {e}")
        
        return None
    
    async def get_location_info(self) -> Optional[Tuple[str, float, float]]:
        """获取当前位置信息（通过 IP 地理位置 API）
        
        Returns:
            元组 (城市名称, 纬度, 经度)，失败返回 None
        """
        client = self._ensure_client()
        
        # 检查是否包含中文字符
        def contains_cjk(s: str) -> bool:
            try:
                return any('\u4e00' <= ch <= '\u9fff' for ch in s)
            except Exception:
                return False
        
        # 尝试 ipapi.co
        try:
            api_url = "https://ipapi.co/json"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = await client.get(api_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                city = data.get('city', '')
                region = data.get('region', '')
                latitude = data.get('latitude')
                longitude = data.get('longitude')
                
                # 如果城市名不是中文，优先使用 region
                location_name = region if (region and contains_cjk(region)) else (city or region)
                
                if location_name and latitude is not None and longitude is not None:
                    return (location_name, latitude, longitude)
        except Exception as e:
            logger.error(f"ipapi.co 获取位置信息失败: {e}")
        
        # 备用方案：尝试 ipwhois.app
        try:
            api_url = "https://ipwhois.app/json/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = await client.get(api_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success'):
                    city = data.get('city', '')
                    region = data.get('region', '')
                    latitude = data.get('latitude')
                    longitude = data.get('longitude')
                    
                    # 如果城市名不是中文，优先使用 region
                    location_name = region if (region and contains_cjk(region)) else (city or region)
                    
                    if location_name and latitude is not None and longitude is not None:
                        return (location_name, latitude, longitude)
        except Exception as e:
            logger.error(f"ipwhois.app 获取位置信息失败: {e}")
        
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
                    
                    # 检查字符串是否包含中文字符
                    def contains_cjk(s: str) -> bool:
                        try:
                            return any('\u4e00' <= ch <= '\u9fff' for ch in s)
                        except Exception:
                            return False
                    
                    # 优先使用天气数据中的中文地名
                    state_code = location.get('StateCode', '')  # 如 "北京"
                    provider_loc = location.get('Name', '')      # 如 "beijing"
                    
                    # 优先级：中文 StateCode > 包含中文的 Name > fallback_location > 英文 Name
                    if state_code and contains_cjk(state_code):
                        display_loc = state_code
                    elif provider_loc and contains_cjk(provider_loc):
                        display_loc = provider_loc
                    elif fallback_location:
                        display_loc = fallback_location
                    elif provider_loc:
                        display_loc = provider_loc
                    else:
                        display_loc = '未知'

                    return {
                        'temperature': current_data.get('temp'),
                        'condition': current_data.get('cap'),
                        'icon': self._get_weather_icon(current_data.get('cap', '')),
                        'location': display_loc,
                        'feels_like': current_data.get('feels'),
                        'humidity': current_data.get('rh')
                    }
        except Exception as e:
            logger.error(f"格式化天气数据失败: {e}")
        
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
        lat = None
        lon = None
        
        # 如果没有提供偏好城市，通过 ipapi.co 获取位置
        if not city:
            location_info = await self.get_location_info()
            if location_info:
                city, lat, lon = location_info
        
        # 如果有城市但没有坐标，搜索城市坐标
        if city and (lat is None or lon is None):
            location = await self.search_location(city)
            if location:
                lat = location['lat']
                lon = location['lon']
        
        # 获取天气数据
        if lat is not None and lon is not None:
            weather_data = await self.get_weather_detailed(lat, lon)
            if weather_data:
                formatted = self.format_weather_simple(weather_data, fallback_location=city)
                return formatted
        
        # 如果失败，使用默认位置（上海）
        weather_data = await self.get_weather_detailed()
        if weather_data:
            return self.format_weather_simple(weather_data)
        
        return None
