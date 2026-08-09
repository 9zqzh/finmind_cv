"""仅在当前进程内存中保存短期 AI 对话上下文。"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from app.config import Settings


@dataclass
class ConversationTurn:
    """单轮对话新增的 PydanticAI 模型消息。"""

    model_messages_json: str
    created_at: float = field(default_factory=time.time)


@dataclass
class ConversationMemory:
    """一个浏览器页面生命周期内的临时对话记忆。"""

    conversation_id: str
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    chat_history: list[ConversationTurn] = field(default_factory=list)


class ConversationManager:
    """临时对话记忆管理器，不会写入数据库或文件。"""

    def __init__(self, settings: Settings) -> None:
        self._ttl_seconds = settings.session_ttl_minutes * 60
        self._conversations: dict[str, ConversationMemory] = {}
        self._lock = threading.Lock()

    def get_or_create(self, conversation_id: str | None) -> ConversationMemory | None:
        """按浏览器提供的标识获取临时记忆；缺失时保持无记忆兼容。"""
        if not conversation_id or len(conversation_id) > 128:
            return None

        now = time.time()
        with self._lock:
            expired = [
                key
                for key, conversation in self._conversations.items()
                if now - conversation.last_active > self._ttl_seconds
            ]
            for key in expired:
                self._conversations.pop(key, None)

            conversation = self._conversations.get(conversation_id)
            if conversation is None:
                conversation = ConversationMemory(conversation_id=conversation_id)
                self._conversations[conversation_id] = conversation
            conversation.last_active = now
            return conversation
