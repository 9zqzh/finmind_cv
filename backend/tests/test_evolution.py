"""半自动进化流水线测试：聚类、高频判定、约束校验、草稿审核生命周期。"""

import time

import pytest

from app.agent.evolution import (
    EvolutionService,
    _read_frontmatter,
    cluster_messages,
    normalize_message,
    select_high_frequency,
    similarity,
    validate_draft,
)
from app.agent.playbook import PlaybookEntry, PlaybookStore
from app.config import get_settings


def _turn(message: str, tools: list[str] | None = None) -> dict:
    return {
        "user_message": message,
        "response_json": {
            "answer": "回答摘要",
            "tool_calls": [{"tool": t} for t in (tools or [])],
        },
    }


# ---------- 归一化与相似度 ----------


def test_normalize_message():
    assert normalize_message(" 重修，怎么办理？ ") == "重修怎么办理"
    assert normalize_message("Retake HOW") == "retakehow"
    assert normalize_message("") == ""


def test_similarity():
    assert similarity("重修怎么办理", "重修怎么办理") == pytest.approx(1.0)
    assert similarity("重修怎么办理", "重修报名怎么搞") > 0.1
    assert similarity("重修怎么办理", "图书馆几点开门") == pytest.approx(0.0)


# ---------- 聚类 ----------


def test_cluster_messages_groups_similar_questions():
    turns = [
        _turn("重修怎么办理"),
        _turn("重修怎么报名啊"),
        _turn("怎么申请重修"),
        _turn("图书馆几点开门"),
    ]
    clusters = cluster_messages(turns)
    # 三条重修类问句归为一簇，图书馆单独一簇
    assert len(clusters) == 2
    biggest = clusters[0]
    assert biggest.count == 3
    assert all("重修" in m for m in biggest.messages)


def test_cluster_skips_empty_messages():
    clusters = cluster_messages([_turn(""), _turn("   "), _turn("重修怎么办")])
    assert len(clusters) == 1 and clusters[0].count == 1


# ---------- 高频判定 ----------


def _clusters_of_sizes(*sizes: int):
    from app.agent.evolution import QuestionCluster

    result = []
    for i, size in enumerate(sizes):
        cluster = QuestionCluster(representative=f"问题{i}")
        cluster.messages = [f"问题{i}"] * size
        result.append(cluster)
    return result


def test_select_high_frequency_by_min_count_and_top_n():
    clusters = _clusters_of_sizes(10, 5, 2, 1)  # 已按大小降序
    selected = select_high_frequency(clusters, min_count=8, top_n=2)
    sizes = sorted(c.count for c in selected)
    # 10 达到绝对阈值；5 靠 Top2 入选；2 和 1 既未达标也不在 Top2，被淘汰
    assert sizes == [5, 10]


def test_select_high_frequency_no_duplicates():
    clusters = _clusters_of_sizes(12, 9)
    selected = select_high_frequency(clusters, min_count=8, top_n=3)
    assert len(selected) == 2


# ---------- 约束校验 ----------


def test_validate_draft_passes_clean_path():
    warnings = validate_draft(
        "缓考申请指南",
        ["缓考", "缓考申请"],
        "1. 调用 search_knowledge 检索缓考流程。\n2. 按结构作答。",
    )
    assert warnings == []


def test_validate_draft_warns_unknown_tool():
    warnings = validate_draft(
        "x", ["a", "b"], "1. 调用 query_fake_tool 获取数据。"
    )
    assert any("query_fake_tool" in w for w in warnings)


def test_validate_draft_warns_too_many_steps():
    body = "\n".join(f"{i}. 步骤" for i in range(1, 11))
    warnings = validate_draft("x", ["a", "b"], body)
    assert any("步骤数" in w for w in warnings)


def test_validate_draft_hard_errors():
    with pytest.raises(ValueError):
        validate_draft("", ["a", "b"], "正文")
    with pytest.raises(ValueError):
        validate_draft("t", ["只有一个"], "正文")
    with pytest.raises(ValueError):
        validate_draft("t", ["a", "b"], "")
    with pytest.raises(ValueError):
        validate_draft("t", ["a", "b"], "字" * 2001)


# ---------- frontmatter 解析 ----------


def test_read_frontmatter():
    meta, body = _read_frontmatter("---\ntitle: 测试\nkeywords: a, b\n---\n正文内容")
    assert meta == {"title": "测试", "keywords": "a, b"}
    assert body == "正文内容"
    meta, body = _read_frontmatter("没有头部的文本")
    assert meta == {} and body == "没有头部的文本"


# ---------- 草稿生命周期 ----------


@pytest.fixture()
def service(tmp_path):
    store = PlaybookStore(tmp_path / "playbooks")
    return EvolutionService(
        db=None,
        store=store,
        drafts_dir=tmp_path / "drafts",
        settings=get_settings(),
    )


def _write_draft(service: EvolutionService, draft_id: str, title: str = "重修快速指南"):
    service.drafts_dir.mkdir(parents=True, exist_ok=True)
    content = (
        "---\n"
        f"title: {title}\n"
        "keywords: 重修, 重修快速\n"
        "source: draft\n"
        "cluster_sample: 重修怎么办理\n"
        "cluster_count: 9\n"
        "warnings: 无\n"
        "---\n"
        "1. 调用 search_knowledge 检索重修。\n"
    )
    (service.drafts_dir / f"{draft_id}.md").write_text(content, encoding="utf-8")


def test_list_drafts(service):
    _write_draft(service, "draft-001")
    drafts = service.list_drafts()
    assert len(drafts) == 1
    assert drafts[0]["id"] == "draft-001"
    assert drafts[0]["cluster_count"] == 9
    assert drafts[0]["keywords"] == ["重修", "重修快速"]


def test_approve_draft_activates_entry(service):
    _write_draft(service, "draft-002")
    entry = service.approve_draft("draft-002")
    assert entry.source == "auto"
    # 草稿文件已删除，正式手册立即参与匹配
    assert not (service.drafts_dir / "draft-002.md").exists()
    assert service.store.match("请问重修怎么弄").title == "重修快速指南"
    # 再次审核同一草稿报不存在
    with pytest.raises(FileNotFoundError):
        service.approve_draft("draft-002")


def test_approve_draft_avoids_id_collision(service):
    # 预置同标题的人工手册
    service.store.save_entry(
        PlaybookEntry(
            id="重修快速指南",
            title="重修快速指南",
            keywords=["旧关键词"],
            instructions="旧内容",
            source="manual",
        )
    )
    _write_draft(service, "draft-003")
    entry = service.approve_draft("draft-003")
    # 不覆盖人工手册，id 追加序号
    assert entry.id == "重修快速指南_2"
    assert len(service.store.entries) == 2


def test_reject_draft(service):
    _write_draft(service, "draft-004")
    service.reject_draft("draft-004")
    assert service.list_drafts() == []
    with pytest.raises(FileNotFoundError):
        service.reject_draft("draft-004")


def test_cooldown_skips_recent_similar_draft(service):
    _write_draft(service, "draft-005")
    assert service._in_cooldown("重修怎么办理啊") is True
    assert service._in_cooldown("图书馆几点开门") is False
    # 把草稿改成过期时间后不再冷却
    path = service.drafts_dir / "draft-005.md"
    old = time.time() - (service.settings.evolution_cooldown_days + 1) * 86400
    import os

    os.utime(path, (old, old))
    assert service._in_cooldown("重修怎么办理啊") is False
