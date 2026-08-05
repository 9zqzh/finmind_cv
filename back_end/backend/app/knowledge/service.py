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
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_SUPPORTED_SUFFIXES = {".md", ".txt", ".json"}
# 无实义的语气助词：包含这些字的二元组不作为检索词，减少噪声命中
_STOP_CHARS = set("的了吗呢吧啊哦嗯")

CHUNK_MAX_CHARS = 400
# 命中得分低于最高分该比例的视为噪声，不返回
MIN_SCORE_RATIO = 0.3
# 弱命中（命中单元数不足）且得分远低于最佳结果的切片视为噪声
MIN_MATCHED_TERMS = 2
STRONG_SCORE_RATIO = 0.8
# 绝对门槛：最佳命中得分或命中单元数太低时视为未检索到（避免偶然撞词）
MIN_ABSOLUTE_SCORE = 4.0
# 命中 2 个及以上分词单元时的额外加权：多词命中比单词频繁出现更能说明相关
MULTI_MATCH_BONUS = 5.0


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
        # 去掉 HTML 注释（如转换工具插入的页码锚点），避免污染检索内容
        raw = _HTML_COMMENT_RE.sub("", raw)
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
            # 元信息行（如来源文件标注）不进入检索内容，避免路径文字干扰命中
            if stripped.startswith(">"):
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
        # 按空行分段落切片：段落是自然的语义单元，比固定长度硬切更完整
        paragraphs: list[str] = []
        current: list[str] = []
        for line in buffer:
            if line.strip():
                current.append(line)
            elif current:
                paragraphs.append("\n".join(current))
                current = []
        if current:
            paragraphs.append("\n".join(current))
        buffer.clear()
        for paragraph in paragraphs:
            # 段落过长时再按固定长度二次切分
            for start in range(0, len(paragraph), CHUNK_MAX_CHARS):
                piece = paragraph[start : start + CHUNK_MAX_CHARS].strip()
                if piece:
                    self.chunks.append(Chunk(text=piece, source=source, title=title))

    # ---- 检索 ----

    def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        tokens = self._tokenize(query)
        if not tokens:
            return []
        candidates: list[tuple[Chunk, int, float]] = []
        for chunk in self.chunks:
            matched, score = self._score(chunk.text, tokens)
            if score > 0:
                candidates.append((chunk, matched, score))
        if not candidates:
            return []
        best = max(score for _, _, score in candidates)
        best_matched = max(matched for _, matched, _ in candidates)
        # 绝对门槛（仅对多词查询生效）：最佳命中太弱时视为未检索到，避免偶然撞词
        # 单词查询（如“缓考”）本身词数少，不适用该门槛
        if len(tokens) >= 4 and best < MIN_ABSOLUTE_SCORE and best_matched < MIN_MATCHED_TERMS:
            return []
        results: list[SearchResult] = []
        for chunk, matched, score in candidates:
            if score < best * MIN_SCORE_RATIO:
                continue
            # 只命中个别通用词且得分远低于最佳结果的，判为无关（避免凑数）
            if matched < MIN_MATCHED_TERMS and score < best * STRONG_SCORE_RATIO:
                continue
            results.append(
                SearchResult(
                    text=chunk.text,
                    source=chunk.source,
                    title=chunk.title,
                    score=score,
                )
            )
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]

    @staticmethod
    def _tokenize(query: str) -> set[str]:
        tokens: set[str] = set()
        for word in _WORD_RE.findall(query):
            if len(word) >= 2:
                tokens.add(word.lower())
        cjk_chars = _CJK_RE.findall(query)
        for i in range(len(cjk_chars) - 1):
            bigram = cjk_chars[i] + cjk_chars[i + 1]
            # 过滤含虚词的无效二元组（如“请告”“诉我”“校的”“的流”）
            if bigram[0] in _STOP_CHARS or bigram[1] in _STOP_CHARS:
                continue
            tokens.add(bigram)
        if len(cjk_chars) == 1:
            tokens.add(cjk_chars[0])
        return tokens

    @staticmethod
    def _score(text: str, tokens: set[str]) -> tuple[int, float]:
        """返回（命中的分词单元数，加权得分）。"""
        lower = text.lower()
        score = 0.0
        matched = 0
        for token in tokens:
            count = lower.count(token)
            if count:
                matched += 1
                # 长词权重更高，避免单字噪声主导排序
                score += count * len(token)
        # 命中多个不同关键词时额外加权：同时命中“缓考+申请”应强于只高频命中“申请”
        if matched >= 2:
            score += MULTI_MATCH_BONUS
        return matched, score
