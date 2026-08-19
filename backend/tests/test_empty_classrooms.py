"""空闲教室查询适配层测试（使用伪造客户端，不请求真实教务系统）。"""

from __future__ import annotations

import pytest
from jwxtapi import ClassroomEntry, ClassroomGrid

from app.adapters import jwxt as jwxt_adapter
from app.services.session import JwxtSession


def _entry(classroom: str, weekday: int, period: str) -> ClassroomEntry:
    return ClassroomEntry(
        classroom=classroom,
        weekday=weekday,
        period=period,
        course_name="测试课程",
        teacher=None,
        weeks_text="1-16周",
        weeks=tuple(range(1, 17)),
        class_name=None,
        raw_text="",
    )


class FakeClient:
    """伪造教务客户端：固定返回一间教室被占用的网格。"""

    is_logged_in = True

    def __init__(self, grid: ClassroomGrid) -> None:
        self._grid = grid
        self.calls: list[dict] = []

    def get_classroom_grid(self, **kwargs):
        self.calls.append(kwargs)
        return self._grid


def _session_with(grid: ClassroomGrid) -> tuple[JwxtSession, FakeClient]:
    client = FakeClient(grid)
    session = JwxtSession(token="test-token", client=client)  # type: ignore[arg-type]
    return session, client


def test_period_code_range_parsing() -> None:
    assert jwxt_adapter._period_code_range("0102") == (1, 2)
    assert jwxt_adapter._period_code_range("0304") == (3, 4)
    assert jwxt_adapter._period_code_range("0910") == (9, 10)
    assert jwxt_adapter._period_code_range("1112") == (11, 12)
    assert jwxt_adapter._period_code_range("910") == (9, 10)
    assert jwxt_adapter._period_code_range("") is None
    assert jwxt_adapter._period_code_range("abc") is None


@pytest.mark.asyncio
async def test_free_classrooms_exclude_occupied_on_requested_slot() -> None:
    grid = ClassroomGrid(
        classrooms=("教室A", "教室B", "教室C"),
        entries=(_entry("教室A", weekday=1, period="0102"),),
    )
    session, _ = _session_with(grid)
    result = await jwxt_adapter.get_empty_classrooms(
        session, "2025-2026-1", weekday=1, start_period=1, end_period=2
    )
    assert result["free_classrooms"] == ["教室B", "教室C"]
    assert result["free_count"] == 2
    assert result["occupied_count"] == 1
    assert result["message"] == ""


@pytest.mark.asyncio
async def test_occupancy_on_other_weekday_does_not_count() -> None:
    grid = ClassroomGrid(
        classrooms=("教室A",),
        entries=(_entry("教室A", weekday=2, period="0102"),),
    )
    session, _ = _session_with(grid)
    result = await jwxt_adapter.get_empty_classrooms(
        session, "2025-2026-1", weekday=1, start_period=1, end_period=2
    )
    assert result["free_classrooms"] == ["教室A"]


@pytest.mark.asyncio
async def test_period_range_overlap_detection() -> None:
    # 教室A 占用 0304（第3-4节），查询第4节应判定占用；查询第1-2节则空闲
    grid = ClassroomGrid(
        classrooms=("教室A",),
        entries=(_entry("教室A", weekday=1, period="0304"),),
    )
    session, _ = _session_with(grid)
    overlap = await jwxt_adapter.get_empty_classrooms(
        session, "2025-2026-1", weekday=1, start_period=4, end_period=4
    )
    assert overlap["free_classrooms"] == []
    assert overlap["message"]  # 无空闲时返回友好提示
    free = await jwxt_adapter.get_empty_classrooms(
        session, "2025-2026-1", weekday=1, start_period=1, end_period=2
    )
    assert free["free_classrooms"] == ["教室A"]


@pytest.mark.asyncio
async def test_week_param_is_forwarded_to_client() -> None:
    grid = ClassroomGrid(classrooms=(), entries=())
    session, client = _session_with(grid)
    await jwxt_adapter.get_empty_classrooms(
        session, "2025-2026-1", weekday=3, week=5, start_period=1, end_period=2
    )
    assert client.calls[0]["start_week"] == 5
    assert client.calls[0]["end_week"] == 5
