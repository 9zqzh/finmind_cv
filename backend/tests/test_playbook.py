"""操作手册（Playbook）模块测试：文件解析、关键词匹配、命中统计与自进化落盘。"""

from app.agent.playbook import (
    PlaybookEntry,
    PlaybookStore,
    build_playbook_instructions,
    parse_entry_file,
)

ENTRY_TEXT = """---
title: 测试手册
keywords: 重修, 挂科, retake
source: manual
---
1. 先检索知识库。
2. 按固定结构作答。
"""

SECOND_TEXT = """---
title: 选课手册
keywords: 选课, 选课时间
source: manual
---
1. 检索选课安排。
"""


def _write(tmp_path, name: str, text: str):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_parse_entry_file(tmp_path):
    path = _write(tmp_path, "重修指南.md", ENTRY_TEXT)
    entry = parse_entry_file(path)
    assert entry is not None
    assert entry.id == "重修指南"
    assert entry.title == "测试手册"
    assert entry.keywords == ["重修", "挂科", "retake"]
    assert entry.source == "manual"
    assert "先检索知识库" in entry.instructions


def test_parse_skips_invalid_files(tmp_path):
    # 无 frontmatter
    assert parse_entry_file(_write(tmp_path, "a.md", "正文没有头部")) is None
    # 缺 keywords
    no_kw = _write(tmp_path, "b.md", "---\ntitle: x\n---\n正文")
    assert parse_entry_file(no_kw) is None
    # 正文为空
    empty = _write(tmp_path, "c.md", "---\ntitle: x\nkeywords: a\n---\n   ")
    assert parse_entry_file(empty) is None


def test_store_load_and_match(tmp_path):
    _write(tmp_path, "01.md", ENTRY_TEXT)
    _write(tmp_path, "02.md", SECOND_TEXT)
    store = PlaybookStore(tmp_path)
    assert len(store.entries) == 2

    assert store.match("我想问一下重修怎么办理").title == "测试手册"
    assert store.match("什么时候选课").title == "选课手册"
    # 英文关键词忽略大小写
    assert store.match("how about RETAKE?").title == "测试手册"
    # 未命中与空消息
    assert store.match("今天天气怎么样") is None
    assert store.match("") is None


def test_match_prefers_more_keyword_hits(tmp_path):
    _write(tmp_path, "01.md", ENTRY_TEXT)
    _write(tmp_path, "02.md", SECOND_TEXT)
    store = PlaybookStore(tmp_path)
    # 同时出现两个手册的关键词时，命中数多者优先
    entry = store.match("挂科了要重修，顺便问下选课")
    assert entry is not None and entry.title == "测试手册"


def test_record_hit_and_stats(tmp_path):
    _write(tmp_path, "01.md", ENTRY_TEXT)
    store = PlaybookStore(tmp_path)
    entry = store.match("挂科了怎么办")
    assert entry is not None
    store.record_hit(entry)
    store.record_hit(entry)
    assert store.hit_stats() == {entry.id: 2}


def test_save_entry_takes_effect_immediately(tmp_path):
    store = PlaybookStore(tmp_path)
    assert store.match("综测加分怎么算") is None

    auto = PlaybookEntry(
        id="综测加分指南",
        title="综测加分指南",
        keywords=["综测", "综测加分"],
        instructions="1. 检索综合测评实施细则。",
        source="auto",
    )
    path = store.save_entry(auto)
    assert path.exists()

    # 内存即时生效
    assert store.match("综测加分怎么算").id == "综测加分指南"
    # 重新加载后仍然存在且标记为自动生成
    reloaded = PlaybookStore(tmp_path)
    entry = reloaded.match("综测怎么算")
    assert entry is not None and entry.source == "auto"


def test_save_entry_overwrites_same_id(tmp_path):
    store = PlaybookStore(tmp_path)
    base = PlaybookEntry(
        id="x", title="旧版", keywords=["关键词"], instructions="旧内容", source="auto"
    )
    store.save_entry(base)
    store.save_entry(
        PlaybookEntry(
            id="x", title="新版", keywords=["关键词"], instructions="新内容", source="auto"
        )
    )
    assert len(store.entries) == 1
    assert store.entries[0].title == "新版"


def test_missing_directory_gives_empty_store(tmp_path):
    store = PlaybookStore(tmp_path / "not_exist")
    assert store.entries == []
    assert store.match("任意消息") is None


def test_build_playbook_instructions(tmp_path):
    _write(tmp_path, "01.md", ENTRY_TEXT)
    store = PlaybookStore(tmp_path)
    entry = store.match("挂科了")
    text = build_playbook_instructions(entry)
    assert entry.title in text
    assert "固定最优路径" in text
    assert "先检索知识库" in text
