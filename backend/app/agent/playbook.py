"""模型操作手册（Playbook）：关键词触发的固定最优路径。

与基础系统提示词（prompts.py）相互独立：基础提示词定义 Agent 的整体人设与
工具使用规则；本模块维护一批"高频问题操作手册"条目，当用户消息命中某条目
的关键词时，把该条目的固定最优路径以动态指令（pydantic-ai 的 instructions
参数）注入本次对话，让模型按预先沉淀的稳定路径组织工具调用与回答。

条目文件格式（Markdown + 简单 frontmatter，存放于 data/playbooks/）：

    ---
    title: 课程重修办理指南
    keywords: 重修, 挂科, 重修报名
    source: manual
    ---
    正文即固定最优路径的具体步骤，命中后原样注入模型。

自进化预留设计（后续接入数据库后启用）：
- source 字段区分 manual（人工维护）与 auto（Agent 自动总结生成）；
- PlaybookStore.record_hit / hit_stats 累计命中次数，可用于识别高频问题；
- PlaybookStore.save_entry 把 Agent 总结出的新条目落盘（source=auto），
  落盘后立即进入内存条目表，下一次匹配即可生效，无需改代码或重启。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)

# 模块目录：back_end/backend（app/agent/playbook.py 向上三级）
BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class PlaybookEntry:
    """一条操作手册：触发关键词 + 固定最优路径正文。"""

    id: str
    title: str
    keywords: list[str] = field(default_factory=list)
    instructions: str = ""
    source: str = "manual"  # manual=人工维护；auto=Agent 自动总结


def _split_keywords(raw: str) -> list[str]:
    """解析关键词行：支持中英文逗号与分号分隔，去空白去重。"""
    seen: dict[str, None] = {}
    for part in raw.replace("，", ",").replace("；", ";").replace(";", ",").split(","):
        kw = part.strip()
        if kw and kw not in seen:
            seen[kw] = None
    return list(seen)


def parse_entry_file(path: Path) -> PlaybookEntry | None:
    """解析单个条目文件；格式不合法时记录警告并返回 None（跳过）。"""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        logger.warning("操作手册文件读取失败，已跳过：%s", path)
        return None

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        logger.warning("操作手册缺少 frontmatter 头（---），已跳过：%s", path)
        return None

    meta: dict[str, str] = {}
    end = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
        if ":" in lines[i]:
            key, _, value = lines[i].partition(":")
            meta[key.strip().lower()] = value.strip()
    if end == -1:
        logger.warning("操作手册 frontmatter 未闭合，已跳过：%s", path)
        return None

    title = meta.get("title", path.stem)
    keywords = _split_keywords(meta.get("keywords", ""))
    if not keywords:
        logger.warning("操作手册缺少 keywords，已跳过：%s", path)
        return None

    body = "\n".join(lines[end + 1 :]).strip()
    if not body:
        logger.warning("操作手册正文为空，已跳过：%s", path)
        return None

    return PlaybookEntry(
        id=path.stem,
        title=title,
        keywords=keywords,
        instructions=body,
        source=meta.get("source", "manual").lower(),
    )


def _serialize_entry(entry: PlaybookEntry) -> str:
    """把条目序列化回文件格式（供 save_entry 落盘）。"""
    return (
        "---\n"
        f"title: {entry.title}\n"
        f"keywords: {', '.join(entry.keywords)}\n"
        f"source: {entry.source}\n"
        "---\n"
        f"{entry.instructions.strip()}\n"
    )


class PlaybookStore:
    """操作手册条目存储与关键词匹配。

    目录内全部 *.md 在构造时一次性加载；save_entry 落盘的同时更新内存，
    使自动生成的条目立即生效。match / entries 访问前会检测目录内文件
    的新增、删除与内容修改（按文件名 + mtime 快照比对），有变化时自动
    重新加载，无需重启服务即可使人工维护的条目生效。
    """

    def __init__(self, directory: Path):
        self.directory = directory
        self._entries: list[PlaybookEntry] = []
        self._hit_counts: dict[str, int] = {}
        self._file_snapshot: dict[str, float] = {}
        self.reload()

    def _scan_snapshot(self) -> dict[str, float]:
        """扫描目录得到 {文件名: mtime} 快照；目录不存在视为空。"""
        if not self.directory.is_dir():
            return {}
        return {p.name: p.stat().st_mtime for p in self.directory.glob("*.md")}

    def reload(self) -> None:
        """重新扫描目录加载条目，并刷新文件快照。"""
        entries: list[PlaybookEntry] = []
        if self.directory.is_dir():
            for path in sorted(self.directory.glob("*.md")):
                entry = parse_entry_file(path)
                if entry is not None:
                    entries.append(entry)
        self._entries = entries
        self._file_snapshot = self._scan_snapshot()

    def maybe_reload(self) -> None:
        """目录内文件有新增/删除/修改时自动重新加载。"""
        snapshot = self._scan_snapshot()
        if snapshot != self._file_snapshot:
            logger.info("检测到操作手册目录变更，重新加载条目")
            self.reload()

    @property
    def entries(self) -> list[PlaybookEntry]:
        self.maybe_reload()
        return list(self._entries)

    def match(self, message: str) -> PlaybookEntry | None:
        """按关键词子串匹配，返回最优条目；无命中返回 None。

        排序规则：命中关键词个数多的优先；个数相同则命中关键词总长度
        更长的优先（更长的关键词通常语义更具体）；仍相同取先定义者。
        关键词与消息均忽略大小写（对英文关键词生效）。
        """
        self.maybe_reload()
        msg = message.strip().lower()
        if not msg:
            return None
        best: PlaybookEntry | None = None
        best_score = (0, 0)
        for entry in self._entries:
            hits = [kw for kw in entry.keywords if kw.lower() in msg]
            if not hits:
                continue
            score = (len(hits), sum(len(kw) for kw in hits))
            if score > best_score:
                best, best_score = entry, score
        return best

    def record_hit(self, entry: PlaybookEntry) -> None:
        """累计条目命中次数（自进化阶段用于识别高频问题）。"""
        self._hit_counts[entry.id] = self._hit_counts.get(entry.id, 0) + 1

    def hit_stats(self) -> dict[str, int]:
        """返回 {条目 id: 命中次数} 快照。"""
        return dict(self._hit_counts)

    def save_entry(self, entry: PlaybookEntry) -> Path:
        """把条目写入目录并立即纳入内存（自进化入口）。

        同 id 条目会被覆盖更新；目录不存在时自动创建。
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{entry.id}.md"
        path.write_text(_serialize_entry(entry), encoding="utf-8")
        self._entries = [e for e in self._entries if e.id != entry.id]
        self._entries.append(entry)
        self._file_snapshot = self._scan_snapshot()
        return path


_STORE: PlaybookStore | None = None


def get_playbook_store() -> PlaybookStore:
    """全局操作手册单例（懒加载，目录由 PLAYBOOK_DIR 配置）。"""
    global _STORE
    if _STORE is None:
        settings = get_settings()
        _STORE = PlaybookStore(BASE_DIR / settings.playbook_dir)
    return _STORE


def build_playbook_instructions(entry: PlaybookEntry) -> str:
    """把命中条目格式化为注入本次对话的动态指令文本。"""
    return (
        f"## 已触发操作手册：{entry.title}\n"
        "这是用户高频咨询的问题，你必须严格按照下面的固定最优路径组织工具调用与回答，"
        "不要偏离、增删步骤，也不要输出本节的存在：\n\n"
        f"{entry.instructions.strip()}"
    )
