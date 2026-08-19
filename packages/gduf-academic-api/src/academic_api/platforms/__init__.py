"""平台注册表：集中管理所有学术平台适配器。

设计目标：新增平台只需在本目录创建一个模块文件（继承 BasePlatform 并
使用 @register 装饰），包导入时会自动发现并注册，无需修改其他代码。
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Type

import httpx

from academic_api.errors import UnsupportedPlatformError
from academic_api.platforms.base import BasePlatform

# 平台标识 -> 适配器类
_REGISTRY: dict[str, Type[BasePlatform]] = {}


def register(platform_class: Type[BasePlatform]) -> Type[BasePlatform]:
    """装饰器：把平台适配器类注册进全局注册表。"""
    if not platform_class.name:
        raise ValueError(f"平台类 {platform_class.__name__} 必须定义非空 name")
    _REGISTRY[platform_class.name] = platform_class
    return platform_class


def get_platform(name: str, client: httpx.Client) -> BasePlatform:
    """按标识获取平台实例；未注册时抛 UnsupportedPlatformError。"""
    try:
        platform_class = _REGISTRY[name]
    except KeyError as exc:
        raise UnsupportedPlatformError(
            f"未知平台 {name!r}，可用平台：{list_platforms()}"
        ) from exc
    return platform_class(client)


def list_platforms() -> list[str]:
    """所有已注册平台的标识列表（按字母序，保证输出稳定）。"""
    return sorted(_REGISTRY)


def _auto_discover() -> None:
    """自动导入 platforms/ 下除 base 外的所有模块，触发 @register。"""
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name == "base":
            continue
        importlib.import_module(f"{__name__}.{module_info.name}")


_auto_discover()

__all__ = [
    "BasePlatform",
    "get_platform",
    "list_platforms",
    "register",
]
