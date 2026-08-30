import { useCallback, useEffect, useState, type Dispatch, type SetStateAction } from "react";
import { Modal } from "antd";
import { api } from "../../../api/client";
import type { ConversationSummary, StoredTurn } from "../../../api/types";
import {
  createAssistantMessage,
  createUserMessage,
  type ChatMessage,
} from "../model/chatStream";

function turnsToMessages(turns: StoredTurn[]): ChatMessage[] {
  return turns.flatMap((turn) => [
    createUserMessage(`${turn.id}-user`, turn.user_message),
    {
      ...createAssistantMessage(`${turn.id}-assistant`),
      text: turn.response.answer,
      chat: turn.response,
      toolCalls: turn.response.tool_calls.map((call) => ({
        tool_name: call.tool,
        status: "done" as const,
      })),
    },
  ]);
}

interface UseConversationHistoryArgs {
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>;
  isStreaming: boolean;
  scrollToBottom: () => void;
}

export function useConversationHistory({
  setMessages,
  isStreaming,
  scrollToBottom,
}: UseConversationHistoryArgs) {
  const [historyLoading, setHistoryLoading] = useState(false);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [hasMoreTurns, setHasMoreTurns] = useState(false);
  const [oldestPosition, setOldestPosition] = useState<number | null>(null);

  const openConversation = useCallback(
    async (id: string) => {
      if (isStreaming) return;
      setHistoryLoading(true);
      try {
        const data = await api.conversation(id);
        setMessages(turnsToMessages(data.turns));
        setActiveConversationId(id);
        setHasMoreTurns(data.has_more);
        setOldestPosition(data.turns[0]?.position ?? null);
        setHistoryOpen(false);
        scrollToBottom();
      } finally {
        setHistoryLoading(false);
      }
    },
    [isStreaming, setMessages, scrollToBottom],
  );

  const refreshConversations = useCallback(async () => {
    const data = await api.conversations();
    setConversations(data.items);
    return data.items;
  }, []);

  const startNewConversation = useCallback(() => {
    if (isStreaming) return;
    setActiveConversationId(null);
    setMessages([]);
    setHasMoreTurns(false);
    setOldestPosition(null);
    setHistoryOpen(false);
  }, [isStreaming, setMessages]);

  const loadOlderTurns = useCallback(async () => {
    if (!activeConversationId || !oldestPosition || historyLoading) return;
    setHistoryLoading(true);
    try {
      const data = await api.conversation(activeConversationId, oldestPosition);
      setMessages((current) => [...turnsToMessages(data.turns), ...current]);
      setHasMoreTurns(data.has_more);
      setOldestPosition(data.turns[0]?.position ?? oldestPosition);
    } finally {
      setHistoryLoading(false);
    }
  }, [activeConversationId, oldestPosition, historyLoading, setMessages]);

  const confirmDelete = useCallback(
    (item: ConversationSummary) => {
      if (isStreaming) return;
      Modal.confirm({
        title: "删除这段对话？",
        content: "删除后无法恢复。",
        okText: "删除",
        okButtonProps: { danger: true },
        cancelText: "取消",
        onOk: async () => {
          await api.deleteConversation(item.id);
          const remaining = conversations.filter(
            (conversation) => conversation.id !== item.id,
          );
          setConversations(remaining);
          if (activeConversationId === item.id) {
            if (remaining[0]) await openConversation(remaining[0].id);
            else startNewConversation();
          }
        },
      });
    },
    [isStreaming, conversations, activeConversationId, openConversation, startNewConversation],
  );

  // 页面挂载时加载最近会话并打开第一条
  useEffect(() => {
    let active = true;
    setHistoryLoading(true);
    api
      .conversations()
      .then(async (data) => {
        if (!active) return;
        setConversations(data.items);
        if (data.items[0]) await openConversation(data.items[0].id);
      })
      .catch(() => {
        if (active) setConversations([]);
      })
      .finally(() => active && setHistoryLoading(false));
    return () => {
      active = false;
    };
    // 仅挂载时加载一次历史记录
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    conversations,
    historyLoading,
    activeConversationId,
    historyOpen,
    hasMoreTurns,
    oldestPosition,
    setActiveConversationId,
    setHistoryOpen,
    openConversation,
    startNewConversation,
    loadOlderTurns,
    confirmDelete,
    refreshConversations,
  };
}
