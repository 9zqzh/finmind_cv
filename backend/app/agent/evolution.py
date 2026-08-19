"""操作手册半自动进化流水线：高频问题发现 → 模型总结最优路径 → 草稿待审。

完整闭环（半自动模式）：
1. analyze：从 conversation_turns 表取时间窗口内的用户提问，剔除已被现有
   手册覆盖的，按字符二元组 Jaccard 相似度聚类计数；
   达到 EVOLUTION_MIN_COUNT 或进入未覆盖 Top EVOLUTION_TOP_N 的簇视为高频，
   且与最近 EVOLUTION_COOLDOWN_DAYS 天内已生成的草稿重复的簇会被跳过。
2. generate：从高频簇采样 EVOLUTION_SAMPLE_SIZE 组"提问 + 工具调用轨迹 +
   回答摘要"，让模型按固定模板归纳出操作手册草稿（结构化输出），
   经约束校验后以 source=draft 落盘到草稿目录，等待管理员审核。
3. approve / reject：管理员通过后草稿转成 source=auto 的正式手册并立即
   参与关键词匹配；拒绝则直接删除草稿。

草稿目录与正式手册目录隔离，保证未审核内容绝不会注入线上对话。
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.model_client import build_model
from app.agent.playbook import PlaybookEntry, PlaybookStore, get_playbook_store
from app.agent.tools import RESULT_TYPES
from app.config import Settings, get_settings
from app.models import ConversationTurn as ConversationTurnModel

logger = logging.getLogger(__name__)

# 聚类相似度阈值（字符二元组 Jaccard）：问法不同但主题相近的中文短句经验值
CLUSTER_SIMILARITY_THRESHOLD = 0.25
# 单条草稿正文长度上限，防止模型输出失控
MAX_INSTRUCTIONS_CHARS = 2000
# 正文中允许的最多步骤行数（超出仅告警，不拒绝）
MAX_STEP_LINES = 8
# 已注册工具名集合，用于校验模型是否引用了不存在的工具
KNOWN_TOOLS = set(RESULT_TYPES)

_PUNCT_RE = re.compile(r"[\s\.,!?;:'\"，。！？；：、（）()\[\]【】…—~\-]+")
_TOOL_TOKEN_RE = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+")


@dataclass
class QuestionCluster:
    """一个高频问题簇：相似提问的聚合结果。"""

    representative: str  # 簇代表问句（首个成员），用于冷却期去重
    messages: list[str] = field(default_factory=list)
    samples: list[dict] = field(default_factory=list)  # 采样的完整对话轨迹

    @property
    def count(self) -> int:
        return len(self.messages)


def normalize_message(text: str) -> str:
    """归一化问句：去空白标点、转小写，便于聚类比较。"""
    return _PUNCT_RE.sub("", text.strip().lower())


def _char_bigrams(text: str) -> set[str]:
    if len(text) < 2:
        return {text} if text else set()
    return {text[i : i + 2] for i in range(len(text) - 1)}


def similarity(a: str, b: str) -> float:
    """两段归一化文本的字符二元组 Jaccard 相似度。"""
    ga, gb = _char_bigrams(a), _char_bigrams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def cluster_messages(turns: list[dict], threshold: float = CLUSTER_SIMILARITY_THRESHOLD) -> list[QuestionCluster]:
    """把 (user_message, response_json) 序列聚类。

    贪心合并：与已有簇的代表问句相似度达到阈值即归入该簇，
    否则开新簇。返回按簇大小降序的列表。
    """
    clusters: list[QuestionCluster] = []
    for turn in turns:
        message = normalize_message(turn.get("user_message", ""))
        if not message:
            continue
        target = None
        for cluster in clusters:
            if similarity(message, cluster.representative) >= threshold:
                target = cluster
                break
        if target is None:
            target = QuestionCluster(representative=message)
            clusters.append(target)
        target.messages.append(turn.get("user_message", ""))
        target.samples.append(turn)
    clusters.sort(key=lambda c: c.count, reverse=True)
    return clusters


def select_high_frequency(
    clusters: list[QuestionCluster],
    min_count: int,
    top_n: int,
) -> list[QuestionCluster]:
    """高频判定：达到绝对阈值，或进入未覆盖问题 Top N（两者并集）。"""
    qualified = [c for c in clusters if c.count >= min_count]
    for cluster in clusters[:top_n]:
        if cluster not in qualified:
            qualified.append(cluster)
    return qualified


def validate_draft(
    title: str, keywords: list[str], instructions: str
) -> list[str]:
    """约束校验：返回警告列表；正文超长等硬性问题直接抛 ValueError。"""
    warnings: list[str] = []
    if not title.strip():
        raise ValueError("草稿标题为空")
    if len(keywords) < 2:
        raise ValueError("草稿关键词少于 2 个，触发面过窄")
    if not instructions.strip():
        raise ValueError("草稿正文为空")
    if len(instructions) > MAX_INSTRUCTIONS_CHARS:
        raise ValueError(f"草稿正文超过 {MAX_INSTRUCTIONS_CHARS} 字符")

    unknown = {
        token
        for token in _TOOL_TOKEN_RE.findall(instructions)
        if token not in KNOWN_TOOLS
    }
    if unknown:
        warnings.append(f"正文引用了未注册的工具名：{sorted(unknown)}")
    step_lines = sum(1 for line in instructions.splitlines() if re.match(r"^\s*\d+[\.、)]", line))
    if step_lines > MAX_STEP_LINES:
        warnings.append(f"步骤数 {step_lines} 超过建议上限 {MAX_STEP_LINES}")
    return warnings


class DraftOutput(BaseModel):
    """总结模型的结构化输出格式。"""

    title: str = Field(description="手册标题，不超过 20 字")
    keywords: list[str] = Field(description="2-8 个触发关键词，覆盖该簇的主要问法")
    instructions: str = Field(description="固定最优路径正文，分步骤描述")


_SUMMARIZER_PROMPT = """你是学院教学小助手的路径沉淀专家。下面给出同一类高频学生问题的多组真实对话记录，
每组包含：用户原话、当时实际调用的工具序列、最终回答摘要。
请归纳这类问题的固定最优处理路径，产出可直接注入模型的操作手册。

硬性要求：
1. 只能使用这些已注册工具：%s；严禁编造不存在的工具或接口。
2. 每一步必须指明：调用哪个工具、用什么关键词/参数、如何组织回答。
3. 步骤不超过 6 步，用编号列表；回答结构要固定（便于学生快速定位信息）。
4. 若记录中存在绕远或失败的调用路径，归纳时避开，只沉淀最短最稳的路径。
5. keywords 从这些问句中出现频率高的词提取，2-8 个。"""


def _format_samples(samples: list[dict], limit: int) -> str:
    """把采样对话格式化为总结模型的输入文本。"""
    blocks = []
    for i, sample in enumerate(samples[:limit], 1):
        response = sample.get("response_json") or {}
        tools = [tc.get("tool", "?") for tc in response.get("tool_calls", [])]
        answer = str(response.get("answer", ""))[:200]
        blocks.append(
            f"【记录{i}】\n用户问：{sample.get('user_message', '')}\n"
            f"工具调用：{' → '.join(tools) if tools else '无（纯对话回答）'}\n"
            f"回答摘要：{answer}"
        )
    return "\n\n".join(blocks)


def _read_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """解析 Markdown frontmatter，返回 (meta, body)；无头部时 meta 为空。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta: dict[str, str] = {}
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return meta, "\n".join(lines[i + 1 :]).strip()
        if ":" in lines[i]:
            key, _, value = lines[i].partition(":")
            meta[key.strip().lower()] = value.strip()
    return {}, text


class EvolutionService:
    """半自动进化流水线：查库分析、生成草稿、审核上下线。"""

    def __init__(
        self,
        db: AsyncSession,
        store: PlaybookStore,
        drafts_dir: Path,
        settings: Settings | None = None,
    ):
        self.db = db
        self.store = store
        self.drafts_dir = drafts_dir
        self.settings = settings or get_settings()

    async def fetch_recent_turns(self) -> list[dict]:
        """取时间窗口内的对话轮次（问句 + 完整响应轨迹）。"""
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=self.settings.evolution_window_days
        )
        rows = await self.db.execute(
            select(
                ConversationTurnModel.user_message,
                ConversationTurnModel.response_json,
            ).where(ConversationTurnModel.created_at >= cutoff)
        )
        return [
            {"user_message": message, "response_json": response}
            for message, response in rows.all()
        ]

    def _in_cooldown(self, representative: str) -> bool:
        """该簇是否在冷却期内（近期已生成过相似草稿）。"""
        if not self.drafts_dir.is_dir():
            return False
        cutoff = time.time() - self.settings.evolution_cooldown_days * 86400
        for path in self.drafts_dir.glob("*.md"):
            if path.stat().st_mtime < cutoff:
                continue
            meta, _ = _read_frontmatter(path.read_text(encoding="utf-8-sig"))
            sample = normalize_message(meta.get("cluster_sample", ""))
            if sample and similarity(normalize_message(representative), sample) >= CLUSTER_SIMILARITY_THRESHOLD:
                return True
        return False

    async def analyze(self) -> list[QuestionCluster]:
        """发现高频问题簇：剔除已覆盖与冷却期内的，返回达标簇。"""
        turns = await self.fetch_recent_turns()
        uncovered = [t for t in turns if self.store.match(t.get("user_message", "")) is None]
        clusters = cluster_messages(uncovered)
        qualified = select_high_frequency(
            clusters, self.settings.evolution_min_count, self.settings.evolution_top_n
        )
        return [c for c in qualified if not self._in_cooldown(c.representative)]

    async def generate_draft(self, cluster: QuestionCluster) -> dict:
        """让模型总结最优路径并落盘为草稿，返回草稿信息与校验警告。"""
        prompt = _SUMMARIZER_PROMPT % ", ".join(sorted(KNOWN_TOOLS))
        agent = Agent(build_model(self.settings), output_type=DraftOutput)
        result = await agent.run(
            _format_samples(cluster.samples, self.settings.evolution_sample_size),
            system_prompt=prompt,
        )
        draft: DraftOutput = result.output
        warnings = validate_draft(draft.title, draft.keywords, draft.instructions)

        draft_id = f"draft-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        content = (
            "---\n"
            f"title: {draft.title}\n"
            f"keywords: {', '.join(draft.keywords)}\n"
            "source: draft\n"
            f"cluster_sample: {cluster.messages[0]}\n"
            f"cluster_count: {cluster.count}\n"
            f"warnings: {'; '.join(warnings) if warnings else '无'}\n"
            "---\n"
            f"{draft.instructions.strip()}\n"
        )
        (self.drafts_dir / f"{draft_id}.md").write_text(content, encoding="utf-8")
        logger.info("生成操作手册草稿 %s（簇大小 %d）", draft_id, cluster.count)
        return {"id": draft_id, "title": draft.title, "warnings": warnings}

    async def run(self) -> dict:
        """一键流水线：分析高频簇并逐个生成草稿。"""
        clusters = await self.analyze()
        drafts = []
        for cluster in clusters:
            try:
                drafts.append(await self.generate_draft(cluster))
            except ValueError as exc:
                logger.warning("簇 %s 草稿校验失败：%s", cluster.representative, exc)
                drafts.append(
                    {"id": None, "title": cluster.representative, "error": str(exc)}
                )
            except Exception as exc:  # 模型调用失败不阻断其他簇
                logger.warning("簇 %s 草稿生成失败：%s", cluster.representative, exc)
                drafts.append(
                    {"id": None, "title": cluster.representative, "error": str(exc)}
                )
        return {"clusters_found": len(clusters), "drafts": drafts}

    def list_drafts(self) -> list[dict]:
        """列出全部待审草稿。"""
        drafts = []
        if not self.drafts_dir.is_dir():
            return drafts
        for path in sorted(self.drafts_dir.glob("*.md")):
            meta, body = _read_frontmatter(path.read_text(encoding="utf-8-sig"))
            drafts.append(
                {
                    "id": path.stem,
                    "title": meta.get("title", path.stem),
                    "keywords": [k.strip() for k in meta.get("keywords", "").split(",") if k.strip()],
                    "cluster_count": int(meta.get("cluster_count", "0") or 0),
                    "warnings": meta.get("warnings", ""),
                    "instructions": body,
                }
            )
        return drafts

    def approve_draft(self, draft_id: str) -> PlaybookEntry:
        """审核通过：草稿转为 source=auto 的正式手册并立即生效。"""
        path = self.drafts_dir / f"{draft_id}.md"
        if not path.exists():
            raise FileNotFoundError(f"草稿不存在：{draft_id}")
        meta, body = _read_frontmatter(path.read_text(encoding="utf-8-sig"))
        title = meta.get("title", draft_id)
        keywords = [k.strip() for k in meta.get("keywords", "").split(",") if k.strip()]

        # 正式手册 id 取标题净化值；与现有条目冲突时追加序号，避免覆盖人工手册
        base_id = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", title).strip("_") or draft_id
        entry_id = base_id
        suffix = 2
        while any(e.id == entry_id for e in self.store.entries):
            entry_id = f"{base_id}_{suffix}"
            suffix += 1

        entry = PlaybookEntry(
            id=entry_id,
            title=title,
            keywords=keywords,
            instructions=body,
            source="auto",
        )
        self.store.save_entry(entry)
        path.unlink()
        logger.info("草稿 %s 审核通过，生效为手册 %s", draft_id, entry_id)
        return entry

    def reject_draft(self, draft_id: str) -> None:
        """审核拒绝：删除草稿。"""
        path = self.drafts_dir / f"{draft_id}.md"
        if not path.exists():
            raise FileNotFoundError(f"草稿不存在：{draft_id}")
        path.unlink()
        logger.info("草稿 %s 已拒绝删除", draft_id)


def build_evolution_service(db: AsyncSession) -> EvolutionService:
    """按全局配置组装进化服务；正式手册库用全局单例，审核通过即时对线上对话生效。"""
    settings = get_settings()
    base_dir = Path(__file__).resolve().parents[2]
    return EvolutionService(
        db=db,
        store=get_playbook_store(),
        drafts_dir=base_dir / settings.playbook_draft_dir,
        settings=settings,
    )
