"""高德地图适配层：隔离高德/百度 Web 服务 API 与 Agent 工具。

职责（与 adapters/ 下其他适配层保持一致的三段式）：
1. 把上游 API 的业务失败映射为统一错误码（ApiError）。
2. 把上游 JSON 精简为可序列化的 dict（截断条目数，控制模型上下文）。
3. 同步 httpx 调用统一包装为 async（asyncio.to_thread），避免阻塞事件循环。

高德 Web 服务 API 免费（个人认证后 QPS 3 / 日配额 5000），无需登录；
模块内维护共享 httpx.Client 复用连接。密钥与默认起点来自 .env 配置。

口碑说明：高德免费接口只返回星级评分与人均消费，不提供评论文本；
配置 BAIDU_MAP_API_KEY 后会用百度地图按名称匹配补充点评数（可选增强，
失败不影响高德结果）。
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Callable, TypeVar
from urllib.parse import quote

import httpx

from app.config import get_settings
from app.schemas.common import (
    INVALID_PARAM,
    PARSE_ERROR,
    UPSTREAM_ERROR,
    ApiError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 高德/百度 Web 服务入口
AMAP_BASE = "https://restapi.amap.com"
BAIDU_BASE = "https://api.map.baidu.com"

# 默认起点与城市（AMAP_DEFAULT_ORIGIN 可覆盖起点名称）
DEFAULT_ORIGIN = "广东金融学院清远校区"
DEFAULT_CITY = "清远"

# 单次返回给模型的最大 POI/路线步骤条数，控制上下文窗口占用
PLACES_MAX_ITEMS = 8
STEPS_MAX_ITEMS = 6
# 文本字段截断长度
NAME_LIMIT = 40
ADDRESS_LIMIT = 60

# 出行方式 -> 高德路径规划接口（v4 骑行接口响应结构与 v3 不同）
ROUTE_ENDPOINTS = {
    "walking": "/v3/direction/walking",
    "driving": "/v3/direction/driving",
    "bicycling": "/v4/direction/bicycling",
    "transit": "/v3/direction/transit/integrated",
}
# 高德 URI 导航链接的 mode 参数（与接口 mode 名不同）
NAVIGATION_MODES = {
    "walking": "walk",
    "driving": "car",
    "bicycling": "ride",
    "transit": "bus",
}

_LOCATION_RE = re.compile(r"^\s*(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\s*$")

_client: httpx.Client | None = None
# 地理编码结果缓存：同一文字位置不重复消耗配额
_location_cache: dict[str, tuple[str, str]] = {}


def get_client() -> httpx.Client:
    """获取共享的 HTTP 客户端（懒加载，关闭后自动重建）。"""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(timeout=15.0, headers={"User-Agent": "finmind-agent/0.1"})
    return _client


def reset_client() -> None:
    """关闭并重置共享客户端（供测试或应用关闭时调用）。"""
    global _client
    if _client is not None and not _client.is_closed:
        _client.close()
    _client = None


def clear_location_cache() -> None:
    """清空地理编码缓存（供测试使用）。"""
    _location_cache.clear()


def _amap_key() -> str:
    key = get_settings().amap_api_key.strip()
    if not key:
        raise ApiError(
            UPSTREAM_ERROR,
            "高德地图 API Key 未配置，请在 .env 中设置 AMAP_API_KEY",
            status_code=503,
        )
    return key


def _baidu_key() -> str:
    return get_settings().baidu_map_api_key.strip()


def _amap_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    """同步调用高德接口并校验业务状态码。"""
    request_params = {**params, "key": _amap_key(), "output": "JSON"}
    try:
        response = get_client().get(AMAP_BASE + path, params=request_params)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise ApiError(UPSTREAM_ERROR, f"高德地图请求失败：{exc}", status_code=502) from exc
    except ValueError as exc:
        raise ApiError(PARSE_ERROR, f"高德地图响应解析失败：{exc}", status_code=502) from exc
    if str(payload.get("status")) != "1":
        info = str(payload.get("info") or payload.get("infocode") or "未知错误")
        raise ApiError(UPSTREAM_ERROR, f"高德地图接口返回错误：{info}", status_code=502)
    return payload


def _to_float(value: Any) -> float:
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _looks_like_location(value: str) -> bool:
    """判断是否为“经度,纬度”坐标字符串。"""
    return bool(_LOCATION_RE.match(value))


def _geocode(address: str) -> tuple[str, str]:
    """地理编码：返回 (location, adcode) 二元组（location 为“经度,纬度”）。"""
    cached = _location_cache.get(address)
    if cached is not None:
        return cached
    payload = _amap_get("/v3/geocode/geo", {"address": address})
    geocodes = payload.get("geocodes") or []
    if not geocodes:
        raise ApiError(INVALID_PARAM, f"无法解析位置：{address}", status_code=400)
    geocode = geocodes[0]
    location = str(geocode.get("location") or "")
    if not location:
        raise ApiError(INVALID_PARAM, f"无法解析位置：{address}", status_code=400)
    result = (location, str(geocode.get("adcode") or ""))
    _location_cache[address] = result
    return result


def _poi_location(keywords: str, city: str = DEFAULT_CITY) -> tuple[str, str]:
    """城市限定 POI 关键词搜索，返回首个有坐标结果的 (location, adcode)。"""
    payload = _amap_get("/v3/place/text", {"keywords": keywords, "city": city})
    for poi in payload.get("pois") or []:
        location = str(poi.get("location") or "")
        if location:
            return location, str(poi.get("adcode") or "")
    return "", ""


def resolve_location_sync(name: str) -> str:
    """把文字位置解析为“经度,纬度”；坐标字符串原样返回。

    回退链：配置的默认起点坐标 -> 地理编码 -> 城市限定 POI 关键词搜索。
    """
    if _looks_like_location(name):
        return name.strip()
    settings = get_settings()
    if name == settings.amap_default_origin and settings.amap_default_location.strip():
        return settings.amap_default_location.strip()
    try:
        location, _ = _geocode(name)
        return location
    except ApiError as exc:
        if exc.code != INVALID_PARAM:
            raise
        # 地理编码失败时退化为城市限定 POI 搜索取首个结果的坐标
        location, adcode = _poi_location(name)
        if location:
            _location_cache[name] = (location, adcode)
            return location
        raise


def _normalize_poi(poi: dict[str, Any], has_distance: bool) -> dict[str, Any]:
    """把高德 POI 精简为紧凑结构，评分/人均缺失时置 0。"""
    biz_ext = poi.get("biz_ext") or {}
    rating = _to_float(biz_ext.get("rating") or poi.get("rating"))
    return {
        "name": str(poi.get("name") or "")[:NAME_LIMIT],
        "location": str(poi.get("location") or ""),
        "address": str(poi.get("address") or "")[:ADDRESS_LIMIT],
        "tel": str(poi.get("tel") or ""),
        "type": str(poi.get("type") or ""),
        "rating": rating,
        "cost": _to_float(biz_ext.get("cost") or poi.get("cost")),
        "distance": _to_int(poi.get("distance")) if has_distance else None,
        "city": str(poi.get("cityname") or poi.get("adname") or ""),
        "comment_num": 0,
        "review_source": "amap",
    }


def search_places_sync(
    keywords: str,
    location: str | None = None,
    radius: int = 5000,
    city: str = DEFAULT_CITY,
) -> dict[str, Any]:
    """周边 POI 搜索（有坐标）或城市限定关键词搜索（无坐标）。"""
    if location:
        payload = _amap_get(
            "/v3/place/around",
            {
                "keywords": keywords,
                "location": location,
                "radius": str(max(radius, 100)),
                "sortrule": "distance",
            },
        )
        pois = payload.get("pois") or []
        items = [_normalize_poi(poi, True) for poi in pois]
    else:
        payload = _amap_get("/v3/place/text", {"keywords": keywords, "city": city})
        pois = payload.get("pois") or []
        items = [_normalize_poi(poi, False) for poi in pois]
    # 过滤无坐标的无效条目并截断
    items = [item for item in items if item["location"]][:PLACES_MAX_ITEMS]
    return {"query": keywords, "total": len(pois), "places": items}


def enrich_reviews_sync(places: list[dict[str, Any]], city: str) -> list[dict[str, Any]]:
    """用百度地图按“名称+城市”匹配，补充点评数与评分（可选增强）。

    百度接口失败/未配置 key 时静默跳过，不阻塞高德结果。
    """
    key = _baidu_key()
    if not key or not places:
        return places
    enriched: list[dict[str, Any]] = []
    for place in places:
        item = dict(place)
        try:
            response = get_client().get(
                BAIDU_BASE + "/place/v2/search",
                params={
                    "query": place["name"],
                    "region": city or DEFAULT_CITY,
                    "output": "json",
                    "ak": key,
                    "scope": "2",
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            # 补充数据源不可用不影响主流程
            enriched.append(item)
            continue
        results = payload.get("results") if str(payload.get("status")) == "0" else None
        if results:
            first = results[0]
            item["rating"] = item["rating"] or _to_float(first.get("rating"))
            item["comment_num"] = _to_int(first.get("comment_num"))
            item["review_source"] = "amap+baidu"
        enriched.append(item)
    return enriched


def get_route_sync(
    destination: str,
    mode: str = "walking",
    origin: str | None = None,
) -> dict[str, Any]:
    """路径规划：起点默认广东金融学院清远校区，支持步行/驾车/骑行/公交。"""
    mode = mode if mode in ROUTE_ENDPOINTS else "walking"
    origin_name = origin or get_settings().amap_default_origin or DEFAULT_ORIGIN
    origin_location = resolve_location_sync(origin_name)
    if _looks_like_location(destination):
        dest_location = destination.strip()
        dest_adcode = ""
    else:
        dest_location, dest_adcode = _geocode(destination)

    params: dict[str, Any] = {"origin": origin_location, "destination": dest_location}
    if mode == "transit":
        # 公交规划必须指定出发/到达城市（用地理编码得到的行政区划码）
        params["city"] = DEFAULT_CITY
        params["cityd"] = dest_adcode or DEFAULT_CITY
    try:
        payload = _amap_get(ROUTE_ENDPOINTS[mode], params)
    except ApiError as exc:
        # 长店名/同名地点可能被地理编码到错误位置（如跨市同名）导致超距，
        # 回退为城市限定 POI 搜索取真实坐标后重试一次
        if _looks_like_location(destination) or "OVER_DIRECTION_RANGE" not in exc.message:
            raise
        fallback_location, fallback_adcode = _poi_location(destination)
        if not fallback_location:
            raise
        params["destination"] = fallback_location
        if mode == "transit":
            params["cityd"] = fallback_adcode or DEFAULT_CITY
        payload = _amap_get(ROUTE_ENDPOINTS[mode], params)
        dest_location = fallback_location
        dest_adcode = fallback_adcode

    if mode == "bicycling":
        data = payload.get("data") or {}
        paths = data.get("paths") or []
        route = data
    else:
        route = payload.get("route") or {}
        paths = route.get("paths") or []

    if mode == "transit":
        transits = route.get("transits") or []
        if not transits:
            raise ApiError(UPSTREAM_ERROR, "未找到可用的公交路线", status_code=404)
        plan = transits[0]
        distance = _to_int(plan.get("distance"))
        duration = _to_int(plan.get("duration"))
        steps: list[str] = []
        for segment in plan.get("segments") or []:
            for bus in segment.get("bus") or []:
                bus_name = str(bus.get("busname") or "公交")
                dep = str((bus.get("departure_stop") or {}).get("name") or "").strip()
                arr = str((bus.get("arrival_stop") or {}).get("name") or "").strip()
                if dep and arr:
                    steps.append(f"乘{bus_name}：{dep} → {arr}")
                else:
                    steps.append(f"乘{bus_name}")
    else:
        if not paths:
            raise ApiError(UPSTREAM_ERROR, "未找到可用路线", status_code=404)
        plan = paths[0]
        distance = _to_int(plan.get("distance"))
        duration = _to_int(plan.get("duration"))
        steps = [
            str(step.get("instruction") or "")[:60]
            for step in (plan.get("steps") or [])
            if step.get("instruction")
        ]

    lng, lat = dest_location.split(",")[:2]
    navigation_mode = NAVIGATION_MODES[mode]
    # 名称目的地附带文字标签便于导航 App 展示；坐标目的地不加冗余名称
    destination_label = (
        "" if _looks_like_location(destination) else quote(destination)
    )
    return {
        "origin": origin_name,
        "destination": destination,
        "mode": mode,
        "distance_m": distance,
        "duration_s": duration,
        "distance_text": f"{distance / 1000:.1f} 公里" if distance >= 1000 else f"{distance} 米",
        "duration_text": f"{max(1, round(duration / 60))} 分钟",
        "steps": steps[:STEPS_MAX_ITEMS],
        "navigation_url": (
            f"https://uri.amap.com/navigation?to={lng},{lat}{destination_label and ',' + destination_label}&mode={navigation_mode}&coordinate=gaode"
        ),
    }


async def run_map(func: Callable[[], T]) -> T:
    """在线程中执行同步地图 API 调用，避免阻塞事件循环。"""
    return await asyncio.to_thread(func)


async def search_map_places(
    keywords: str,
    location: str | None = None,
    radius: int | None = None,
    city: str | None = None,
) -> dict[str, Any]:
    """搜索周边地点（美食/景点等），返回 POI 列表（含评分、人均、距离）。

    未指定 location 时以默认起点（广东金融学院清远校区）为中心做周边搜索，
    而不是全城关键词搜索，保证“学校周边有什么”的语义。
    """
    settings = get_settings()
    radius = radius or settings.amap_search_radius
    city = city or DEFAULT_CITY
    center_name = location or settings.amap_default_origin or DEFAULT_ORIGIN
    resolved_location = await run_map(lambda: resolve_location_sync(center_name))
    places = await run_map(
        lambda: search_places_sync(keywords, resolved_location, radius, city)
    )
    places["places"] = await run_map(lambda: enrich_reviews_sync(places["places"], city))
    return places


async def query_map_route(
    destination: str,
    mode: str = "walking",
    origin: str | None = None,
) -> dict[str, Any]:
    """规划从默认起点到目的地的出行路线，返回距离、耗时与导航链接。"""
    return await run_map(lambda: get_route_sync(destination, mode, origin))


__all__ = [
    "DEFAULT_ORIGIN",
    "clear_location_cache",
    "get_route_sync",
    "query_map_route",
    "reset_client",
    "resolve_location_sync",
    "search_map_places",
    "search_places_sync",
]
