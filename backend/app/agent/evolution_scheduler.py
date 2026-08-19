"""定时自进化调度器：按固定间隔自动跑进化流水线，产出待审草稿。

设计要点：
- 纯 asyncio 后台任务，随 FastAPI lifespan 启动/取消，不引入额外依赖；
- 触发时刻取本地时间 EVOLUTION_RUN_HOUR 点（低峰期），且距上次运行
  至少 EVOLUTION_INTERVAL_DAYS 天；上次运行时间落盘到
  data/last_evolution_run.txt，服务重启不会导致重复执行；
- 生成的仍是草稿，必须经管理员审核才会对线上对话生效；
- 单次运行失败仅记录日志，不中断后续调度。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.evolution import EvolutionService, build_evolution_service
from app.config import get_settings

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]  # backend 目录
LAST_RUN_FILE = BASE_DIR / "data" / "last_evolution_run.txt"


def next_run_at(
    now: datetime, last_run: datetime | None, interval_days: int, run_hour: int
) -> datetime:
    """计算下一次运行时刻：不早于 now 之后最近的 run_hour 点，且距上次运行满间隔。"""
    candidate = now.replace(hour=run_hour, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    if last_run is not None:
        earliest = last_run + timedelta(days=interval_days)
        if earliest > candidate:
            candidate = earliest.replace(hour=run_hour, minute=0, second=0, microsecond=0)
            if candidate <= now:
                candidate += timedelta(days=1)
    return candidate


def read_last_run(path: Path | None = None) -> datetime | None:
    """读取上次运行时间；文件缺失或损坏视为从未运行。"""
    try:
        target = path or LAST_RUN_FILE
        return datetime.fromisoformat(target.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def write_last_run(when: datetime, path: Path | None = None) -> None:
    target = path or LAST_RUN_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(when.isoformat(timespec="seconds"), encoding="utf-8")


async def run_evolution_once(
    session_factory: async_sessionmaker[AsyncSession],
    build_service=build_evolution_service,
) -> dict:
    """跑一次完整进化流水线并记录运行时间。"""
    async with session_factory() as db:
        service: EvolutionService = build_service(db)
        result = await service.run()
    write_last_run(datetime.now())
    return result


async def _schedule_loop(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """调度主循环：睡到下一触发时刻 → 执行 → 重复，直到被取消。"""
    settings = get_settings()
    while True:
        run_at = next_run_at(
            datetime.now(),
            read_last_run(),
            settings.evolution_interval_days,
            settings.evolution_run_hour,
        )
        delay = (run_at - datetime.now()).total_seconds()
        logger.info("定时进化已排程：下一次运行 %s（%.1f 小时后）", run_at, delay / 3600)
        await asyncio.sleep(max(delay, 1.0))
        try:
            result = await run_evolution_once(session_factory)
            logger.info(
                "定时进化完成：发现 %d 个高频簇，产出 %d 条草稿结果",
                result.get("clusters_found", 0),
                len(result.get("drafts", [])),
            )
        except Exception:  # 单次失败不中断调度
            logger.exception("定时进化执行失败，等待下一周期")


def start_scheduler(
    session_factory: async_sessionmaker[AsyncSession],
) -> asyncio.Task | None:
    """启动定时进化后台任务；EVOLUTION_SCHEDULE_ENABLED=false 时返回 None。"""
    settings = get_settings()
    if not settings.evolution_schedule_enabled:
        logger.info("定时进化已关闭（EVOLUTION_SCHEDULE_ENABLED=false）")
        return None
    return asyncio.create_task(_schedule_loop(session_factory), name="evolution-scheduler")


async def stop_scheduler(task: asyncio.Task | None) -> None:
    """取消后台任务并等待其退出。"""
    if task is None or task.cancelled():
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
