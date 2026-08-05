"""知识库检索测试。"""

from __future__ import annotations

import json

from app.knowledge import KnowledgeService


def _prepare(tmp_path):
    (tmp_path / "学院简介.md").write_text(
        "# 学院简介\n\n大数据与人工智能学院成立于 2018 年，设有计算机科学与技术专业。\n",
        encoding="utf-8",
    )
    (tmp_path / "缓考制度.md").write_text(
        "# 缓考申请\n\n学生因疾病无法参加期末考试的，可申请缓考。\n",
        encoding="utf-8",
    )
    (tmp_path / "竞赛.json").write_text(
        json.dumps(
            [
                {
                    "title": "数学建模竞赛",
                    "time": "每年 9 月",
                    "description": "三人一组完成建模论文",
                }
            ]
        ),
        encoding="utf-8",
    )
    return KnowledgeService.from_directory(tmp_path)


def test_load_chunks(tmp_path):
    service = _prepare(tmp_path)
    assert len(service.chunks) >= 3


def test_search_hit(tmp_path):
    service = _prepare(tmp_path)
    results = service.search("缓考怎么申请", top_k=3)
    assert results
    assert results[0].source == "缓考制度.md"


def test_search_json_record(tmp_path):
    service = _prepare(tmp_path)
    results = service.search("数学建模", top_k=3)
    assert results
    assert results[0].title == "数学建模竞赛"


def test_search_miss(tmp_path):
    service = _prepare(tmp_path)
    assert service.search("完全不相关的查询内容xyz", top_k=3) == []


def test_missing_directory(tmp_path):
    service = KnowledgeService.from_directory(tmp_path / "不存在")
    assert service.chunks == []
