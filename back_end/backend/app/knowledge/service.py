"""轻量检索服务：文档加载 -> 切片 -> 关键词评分检索。

设计说明（对应技术文档 4.4 节）：
- 资料统一放 data/knowledge/ 与 data/information/，支持 .md / .txt / .json。
- 按空行段落切片，超长段落再按固定长度二次切分，保留文件名与标题元数据。
- 中文用字符二元组（bigram）匹配，英文/数字按单词匹配，无需额外依赖。
- 检索不到时返回空列表，由上层明确回答"当前知识库没有找到依据"。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-\.]*")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_SUPPORTED_SUFFIXES = {".md", ".txt", ".json"}

CHUNK_MAX_CHARS = 400


@dataclass
class Chunk:
    """一个检索切片。"""

    text: str
    source: str  # 来源文件名
    title: str = ""  # 所属标题（Markdown 一级/二级标题或文件名）


@dataclass
class SearchResult:
    """一条检索结果。"""

    text: str
    source: str
    title: str
    score: float


@dataclass
class KnowledgeService:
    """基于关键词评分的检索服务。"""

    chunks: list[Chunk] = field(default_factory=list)

    @classmethod
    def from_directory(cls, directory: str | Path) -> "KnowledgeService":
        service = cls()
        service.load_directory(Path(directory))
        return service

    # ---- 加载与切片 ----

    def load_directory(self, directory: Path) -> None:
        if not directory.exists():
            return
        for path in sorted(directory.rglob("*")):
            if path.is_file() and path.suffix.lower() in _SUPPORTED_SUFFIXES:
                try:
                    self.load_file(path)
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    # 单个文件损坏不影响整体加载
                    continue

    def load_file(self, path: Path) -> None:
        raw = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            self._load_json(path.name, raw)
        else:
            self._load_text(path.name, raw)

    def _load_text(self, source: str, raw: str) -> None:
        title = source
        current_title = title
        buffer: list[str] = []
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                # 标题行之前的缓冲先落盘
                self._flush_buffer(source, current_title, buffer)
                current_title = stripped.lstrip("#").strip() or title
                continue
            buffer.append(line)
        self._flush_buffer(source, current_title, buffer)

    def _load_json(self, source: str, raw: str) -> None:
        payload = json.loads(raw)
        records = payload if isinstance(payload, list) else [payload]
        for item in records:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or item.get("name") or source)
            parts = [str(value) for value in item.values() if value not in (None, "")]
            text = "\n".join(parts)
            if text.strip():
                self.chunks.append(Chunk(text=text, source=source, title=title))

    def _flush_buffer(self, source: str, title: str, buffer: list[str]) -> None:
        paragraph = "\n".join(buffer).strip()
        buffer.clear()
        if not paragraph:
            return
        # 段落过长时按固定长度二次切分
        for start in range(0, len(paragraph), CHUNK_MAX_CHARS):
            piece = paragraph[start : start + CHUNK_MAX_CHARS].strip()
            if piece:
                self.chunks.append(Chunk(text=piece, source=source, title=title))

    # ---- 检索 ----

    def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        tokens = self._tokenize(query)
        if not tokens:
            return []
        scored: list[SearchResult] = []
        for chunk in self.chunks:
            score = self._score(chunk.text, tokens)
            if score > 0:
                scored.append(
                    SearchResult(
                        text=chunk.text,
                        source=chunk.source,
                        title=chunk.title,
                        score=score,
                    )
                )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    @staticmethod
    def _tokenize(query: str) -> set[str]:
        tokens: set[str] = set()
        for word in _WORD_RE.findall(query):
            if len(word) >= 2:
                tokens.add(word.lower())
        cjk_chars = _CJK_RE.findall(query)
        for i in range(len(cjk_chars) - 1):
            tokens.add(cjk_chars[i] + cjk_chars[i + 1])
        if len(cjk_chars) == 1:
            tokens.add(cjk_chars[0])
        return tokens

    @staticmethod
    def _score(text: str, tokens: set[str]) -> float:
        lower = text.lower()
        score = 0.0
        for token in tokens:
            count = lower.count(token)
            if count:
                # 长词权重更高，避免单字噪声主导排序
                score += count * len(token)
        return score
