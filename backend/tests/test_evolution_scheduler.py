"""定时自进化调度器测试：触发时刻计算、运行时间落盘、任务启停。"""

import asyncio
from datetime import datetime

from app.agent import evolution_scheduler as sched


class _FakeSettings:
    def __init__(self, enabled: bool):
        self.evolution_schedule_enabled = enabled
        self.evolution_interval_days = 7
        self.evolution_run_hour = 3


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


# ---------- 触发时刻计算 ----------


def test_next_run_at_same_day():
    now = datetime(2026, 8, 20, 1, 30)
    assert sched.next_run_at(now, None, 7, 3) == datetime(2026, 8, 20, 3, 0)


def test_next_run_at_rolls_to_next_day():
    now = datetime(2026, 8, 20, 5, 0)
    assert sched.next_run_at(now, None, 7, 3) == datetime(2026, 8, 21, 3, 0)


def test_next_run_at_respects_interval():
    # 2 天前刚跑过，间隔 7 天：推到 last+7d 的 3 点
    now = datetime(2026, 8, 20, 5, 0)
    last = datetime(2026, 8, 18, 3, 0)
    assert sched.next_run_at(now, last, 7, 3) == datetime(2026, 8, 25, 3, 0)


def test_next_run_at_interval_expired():
    # 间隔早已满足：回落到下一个 3 点
    now = datetime(2026, 8, 20, 5, 0)
    last = datetime(2026, 8, 1, 3, 0)
    assert sched.next_run_at(now, last, 7, 3) == datetime(2026, 8, 21, 3, 0)


# ---------- 运行时间落盘 ----------


def test_last_run_roundtrip(tmp_path):
    path = tmp_path / "last.txt"
    assert sched.read_last_run(path) is None
    sched.write_last_run(datetime(2026, 8, 20, 3, 0, 5), path)
    assert sched.read_last_run(path) == datetime(2026, 8, 20, 3, 0, 5)


def test_read_last_run_corrupted(tmp_path):
    path = tmp_path / "last.txt"
    path.write_text("not-a-datetime", encoding="utf-8")
    assert sched.read_last_run(path) is None


# ---------- 执行与任务启停 ----------


def test_run_evolution_once(monkeypatch, tmp_path):
    monkeypatch.setattr(sched, "LAST_RUN_FILE", tmp_path / "last.txt")
    ran = []

    class _FakeService:
        async def run(self):
            ran.append(1)
            return {"clusters_found": 2, "drafts": []}

    result = asyncio.run(
        sched.run_evolution_once(
            lambda: _FakeSession(),
            build_service=lambda db: _FakeService(),
        )
    )
    assert result["clusters_found"] == 2
    assert ran == [1]
    assert sched.read_last_run(tmp_path / "last.txt") is not None


def test_start_scheduler_disabled(monkeypatch):
    monkeypatch.setattr(sched, "get_settings", lambda: _FakeSettings(enabled=False))
    assert sched.start_scheduler(lambda: None) is None


def test_start_and_stop_scheduler(monkeypatch, tmp_path):
    monkeypatch.setattr(sched, "LAST_RUN_FILE", tmp_path / "last.txt")
    monkeypatch.setattr(sched, "get_settings", lambda: _FakeSettings(enabled=True))

    async def scenario():
        task = sched.start_scheduler(lambda: None)
        assert task is not None
        await asyncio.sleep(0)  # 让循环启动并进入 sleep 等待
        await sched.stop_scheduler(task)
        assert task.cancelled()

    asyncio.run(scenario())
