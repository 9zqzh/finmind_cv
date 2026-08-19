"""高德地图适配层测试（使用 MockTransport 模拟高德/百度响应，不请求真实 API）。"""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.adapters import amap as amap_adapter
from app.schemas.common import INVALID_PARAM, UPSTREAM_ERROR, ApiError


def _settings(**overrides) -> SimpleNamespace:
    defaults = {
        "amap_api_key": "test-amap-key",
        "baidu_map_api_key": "",
        "amap_default_origin": "广东金融学院清远校区",
        "amap_default_location": "",
        "amap_search_radius": 5000,
    }
    return SimpleNamespace(**{**defaults, **overrides})


@pytest.fixture
def amap_client(monkeypatch):
    """把适配层的共享 client 换成 MockTransport 驱动的假客户端，并注入测试密钥。"""
    handler_calls: dict[str, int] = {}
    monkeypatch.setattr(amap_adapter, "get_settings", lambda: _settings())

    def make_client() -> httpx.Client:
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            handler_calls[path] = handler_calls.get(path, 0) + 1
            return _dispatch(request)

        return httpx.Client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(amap_adapter, "get_client", make_client)
    amap_adapter.clear_location_cache()
    yield handler_calls
    amap_adapter.clear_location_cache()


def _dispatch(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    params = request.url.params

    def json_response(payload: dict) -> httpx.Response:
        return httpx.Response(200, json=payload)

    if path == "/v3/geocode/geo":
        if params.get("address") == "无法解析的地方":
            return json_response({"status": "1", "geocodes": []})
        return json_response(
            {
                "status": "1",
                "geocodes": [
                    {"location": "113.05,23.68", "adcode": "441800", "formatted_address": "广东省清远市"}
                ],
            }
        )
    if path == "/v3/place/around":
        return json_response(
            {
                "status": "1",
                "pois": [
                    {
                        "name": "清远烧鹅饭店",
                        "location": "113.06,23.69",
                        "address": "清城区凤城街道",
                        "tel": "0763-1234567",
                        "type": "餐饮服务;中餐厅",
                        "biz_ext": {"rating": "4.5", "cost": "45"},
                        "distance": "800",
                        "cityname": "清远市",
                    },
                    {
                        "name": "无坐标店",
                        "location": "",
                        "address": "无坐标",
                        "type": "餐饮服务",
                    },
                ],
            }
        )
    if path == "/v3/place/text":
        if params.get("keywords") == "无法解析的地方":
            return json_response({"status": "1", "pois": [{"name": "清远万达广场", "location": "113.10,23.66", "adcode": "441800"}]})
        return json_response(
            {
                "status": "1",
                "pois": [
                    {
                        "name": "万达广场",
                        "location": "113.10,23.66",
                        "address": "清城区人民路",
                        "type": "购物服务;商场",
                        "rating": "4.3",
                        "cityname": "清远市",
                    }
                ],
            }
        )
    if path == "/v3/direction/walking":
        return json_response(
            {
                "status": "1",
                "route": {
                    "paths": [
                        {
                            "distance": "1500",
                            "duration": "1200",
                            "steps": [
                                {"instruction": "从起点出发向东南步行"},
                                {"instruction": "沿凤城大道走 500 米"},
                            ],
                        }
                    ]
                },
            }
        )
    if path == "/v4/direction/bicycling":
        return json_response(
            {
                "status": "1",
                "data": {"paths": [{"distance": "3000", "duration": "900", "steps": [{"instruction": "骑行出发"}]}]},
            }
        )
    if path == "/v3/direction/transit/integrated":
        return json_response(
            {
                "status": "1",
                "route": {
                    "transits": [
                        {
                            "distance": "5000",
                            "duration": "1800",
                            "segments": [
                                {
                                    "bus": [
                                        {
                                            "busname": "101路",
                                            "departure_stop": {"name": "金融学院站"},
                                            "arrival_stop": {"name": "万达广场站"},
                                        }
                                    ]
                                }
                            ],
                        }
                    ]
                },
            }
        )
    if path == "/v3/direction/driving":
        return json_response({"status": "1", "route": {"paths": []}})
    if path == "/place/v2/search":
        return json_response(
            {
                "status": "0",
                "results": [{"name": "清远烧鹅饭店", "rating": "4.6", "comment_num": "1234"}],
            }
        )
    return json_response({"status": "0", "info": "未知接口"})


# ---- 周边搜索 ----


def test_search_places_around_parses_poi(amap_client):
    result = amap_adapter.search_places_sync("烧鹅", location="113.05,23.68")
    assert result["query"] == "烧鹅"
    places = result["places"]
    assert len(places) == 1  # 无坐标的条目被过滤
    first = places[0]
    assert first["name"] == "清远烧鹅饭店"
    assert first["location"] == "113.06,23.69"
    assert first["rating"] == 4.5
    assert first["cost"] == 45
    assert first["distance"] == 800
    assert first["city"] == "清远市"
    assert first["review_source"] == "amap"


def test_search_places_text_without_location(amap_client):
    result = amap_adapter.search_places_sync("商场", city="清远")
    first = result["places"][0]
    assert first["name"] == "万达广场"
    assert first["distance"] is None  # 关键词搜索无距离
    assert first["rating"] == 4.3


# ---- 位置解析 ----


def test_resolve_location_coordinate_passthrough(amap_client):
    assert amap_adapter.resolve_location_sync(" 113.05,23.68 ") == "113.05,23.68"


def test_resolve_location_geocode_and_cache(amap_client):
    assert amap_adapter.resolve_location_sync("广东金融学院清远校区") == "113.05,23.68"
    assert amap_adapter.resolve_location_sync("广东金融学院清远校区") == "113.05,23.68"
    assert amap_client["/v3/geocode/geo"] == 1  # 第二次命中缓存，不重复请求


def test_resolve_location_uses_configured_default(amap_client, monkeypatch):
    monkeypatch.setattr(
        amap_adapter, "get_settings", lambda: _settings(amap_default_location="114.00,24.00")
    )
    assert amap_adapter.resolve_location_sync("广东金融学院清远校区") == "114.00,24.00"
    assert "/v3/geocode/geo" not in amap_client


def test_resolve_location_falls_back_to_poi_search(amap_client):
    assert amap_adapter.resolve_location_sync("无法解析的地方") == "113.10,23.66"
    assert amap_client["/v3/place/text"] == 1


# ---- 路径规划 ----


def test_get_route_walking(amap_client):
    route = amap_adapter.get_route_sync("万达广场", mode="walking")
    assert route["mode"] == "walking"
    assert route["distance_m"] == 1500
    assert route["duration_s"] == 1200
    assert route["distance_text"] == "1.5 公里"
    assert route["duration_text"] == "20 分钟"
    assert route["steps"][0].startswith("从起点出发")
    assert "uri.amap.com/navigation" in route["navigation_url"]
    assert "mode=walk" in route["navigation_url"]


def test_get_route_bicycling_uses_v4_structure(amap_client):
    route = amap_adapter.get_route_sync("万达广场", mode="bicycling")
    assert route["distance_m"] == 3000
    assert route["mode"] == "bicycling"
    assert "mode=ride" in route["navigation_url"]


def test_get_route_transit_parses_bus_steps(amap_client):
    route = amap_adapter.get_route_sync("万达广场", mode="transit")
    assert route["distance_m"] == 5000
    assert route["duration_text"] == "30 分钟"
    assert "101路" in route["steps"][0]
    assert "金融学院站" in route["steps"][0]


def test_get_route_invalid_mode_falls_back_to_walking(amap_client):
    route = amap_adapter.get_route_sync("万达广场", mode="teleport")
    assert route["mode"] == "walking"


def test_get_route_no_paths_raises(amap_client):
    with pytest.raises(ApiError) as excinfo:
        amap_adapter.get_route_sync("万达广场", mode="driving")
    assert excinfo.value.code == UPSTREAM_ERROR
    assert excinfo.value.status_code == 404


def test_get_route_coordinate_destination(amap_client):
    route = amap_adapter.get_route_sync("113.10,23.66", mode="walking")
    assert route["destination"] == "113.10,23.66"


# ---- 错误映射 ----


def test_amap_business_error_maps_to_upstream(amap_client, monkeypatch):
    def fail_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "0", "info": "INVALID_USER_KEY"})

    monkeypatch.setattr(amap_adapter, "get_client", lambda: httpx.Client(transport=httpx.MockTransport(fail_handler)))
    with pytest.raises(ApiError) as excinfo:
        amap_adapter.search_places_sync("烧鹅", location="113.05,23.68")
    assert excinfo.value.code == UPSTREAM_ERROR
    assert "INVALID_USER_KEY" in excinfo.value.message


def test_missing_api_key_raises(amap_client, monkeypatch):
    monkeypatch.setattr(amap_adapter, "get_settings", lambda: _settings(amap_api_key=""))
    with pytest.raises(ApiError) as excinfo:
        amap_adapter.search_places_sync("烧鹅", location="113.05,23.68")
    assert excinfo.value.code == UPSTREAM_ERROR
    assert "AMAP_API_KEY" in excinfo.value.message


def test_unresolvable_location_raises(amap_client, monkeypatch):
    """地理编码与 POI 回退均失败时抛出 INVALID_PARAM。"""
    def fail_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v3/geocode/geo":
            return httpx.Response(200, json={"status": "1", "geocodes": []})
        return httpx.Response(200, json={"status": "1", "pois": []})

    monkeypatch.setattr(amap_adapter, "get_client", lambda: httpx.Client(transport=httpx.MockTransport(fail_handler)))
    with pytest.raises(ApiError) as excinfo:
        amap_adapter.resolve_location_sync("找不到的地方")
    assert excinfo.value.code == INVALID_PARAM


# ---- 百度口碑补充 ----


def test_enrich_reviews_with_baidu(amap_client, monkeypatch):
    monkeypatch.setattr(amap_adapter, "get_settings", lambda: _settings(baidu_map_api_key="baidu-key"))
    places = [
        {
            "name": "清远烧鹅饭店",
            "rating": 4.5,
            "cost": 45,
            "comment_num": 0,
            "review_source": "amap",
        }
    ]
    enriched = amap_adapter.enrich_reviews_sync(places, "清远")
    assert enriched[0]["rating"] == 4.5  # 高德评分优先，百度只补充缺失项
    assert enriched[0]["comment_num"] == 1234
    assert enriched[0]["review_source"] == "amap+baidu"
    assert amap_client["/place/v2/search"] == 1


def test_enrich_reviews_skipped_without_key(amap_client):
    places = [{"name": "清远烧鹅饭店", "rating": 4.5, "comment_num": 0}]
    assert amap_adapter.enrich_reviews_sync(places, "清远") == places
    assert "/place/v2/search" not in amap_client


# ---- 异步入口 ----


@pytest.mark.asyncio
async def test_search_map_places_async(amap_client, monkeypatch):
    # 未传坐标时默认以默认起点（清远校区）为中心做周边搜索
    data = await amap_adapter.search_map_places("烧鹅")
    assert data["places"][0]["name"] == "清远烧鹅饭店"
    assert amap_client["/v3/place/around"] == 1
    assert "/v3/place/text" not in amap_client


@pytest.mark.asyncio
async def test_search_map_places_defaults_to_campus_center(amap_client, monkeypatch):
    """未传 location 时中心为广东金融学院清远校区（周边搜索而非全城搜索）。"""
    data = await amap_adapter.search_map_places("烧鹅")
    assert data["places"][0]["distance"] == 800
    assert amap_client["/v3/geocode/geo"] == 1  # 解析学校坐标


def test_get_route_falls_back_on_direction_range(monkeypatch):
    """长店名被地理编码到错误位置导致超距时，回退 POI 搜索取真实坐标重试。"""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls.append(path)
        if path == "/v3/geocode/geo":
            return httpx.Response(
                200, json={"status": "1", "geocodes": [{"location": "114.71,23.77", "adcode": "441602"}]}
            )
        if path == "/v3/place/text":
            return httpx.Response(
                200, json={"status": "1", "pois": [{"name": "清远烧鹅饭店", "location": "113.06,23.69", "adcode": "441800"}]}
            )
        if path == "/v3/direction/walking" and calls.count(path) == 1:
            return httpx.Response(200, json={"status": "0", "info": "OVER_DIRECTION_RANGE"})
        return httpx.Response(
            200,
            json={
                "status": "1",
                "route": {"paths": [{"distance": "900", "duration": "700", "steps": [{"instruction": "从起点出发"}]}]},
            },
        )

    monkeypatch.setattr(amap_adapter, "get_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(amap_adapter, "get_settings", lambda: _settings())

    route = amap_adapter.get_route_sync("流浪泡泡烤肉店(顺盈时代广场商业街店)", mode="walking")

    assert calls.count("/v3/direction/walking") == 2  # 首次失败 + 回退重试
    assert calls.count("/v3/place/text") == 1
    assert route["distance_m"] == 900


def test_get_route_direction_range_no_fallback_raises(monkeypatch):
    """超距且 POI 回退无结果时，保持抛出原错误。"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v3/geocode/geo":
            return httpx.Response(200, json={"status": "1", "geocodes": [{"location": "114.71,23.77"}]})
        if request.url.path == "/v3/place/text":
            return httpx.Response(200, json={"status": "1", "pois": []})
        return httpx.Response(200, json={"status": "0", "info": "OVER_DIRECTION_RANGE"})

    monkeypatch.setattr(amap_adapter, "get_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(amap_adapter, "get_settings", lambda: _settings())

    with pytest.raises(ApiError) as excinfo:
        amap_adapter.get_route_sync("不存在的店名", mode="walking")
    assert "OVER_DIRECTION_RANGE" in excinfo.value.message


@pytest.mark.asyncio
async def test_query_map_route_async(amap_client, monkeypatch):
    route = await amap_adapter.query_map_route("万达广场", mode="walking")
    assert route["distance_m"] == 1500
