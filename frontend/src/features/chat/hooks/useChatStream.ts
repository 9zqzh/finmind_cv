import { useEffect, useRef, type Dispatch, type SetStateAction } from "react";
import { ApiBizError, getToken, handleAuthExpired } from "../../../api/client";
import type { ChatData, ConversationSummary } from "../../../api/types";
import {
  applyStreamSnapshot,
  collapseThinking,
  completeAssistantMessage,
  createAssistantMessage,
  createMessageId,
  createUserMessage,
  failAssistantMessage,
  parseSSEChunk,
  type ChatMessage,
  type SSEEvent,
  type ToolCallStep,
} from "../model/chatStream";

interface UseChatStreamArgs {
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>;
  setInput: Dispatch<SetStateAction<string>>;
  setLoading: Dispatch<SetStateAction<boolean>>;
  scrollToBottom: () => void;
  updateAssistant: (assistantId: string, update: (message: ChatMessage) => ChatMessage) => void;
  activeConversationId: string | null;
  setActiveConversationId: Dispatch<SetStateAction<string | null>>;
  refreshConversations: () => Promise<ConversationSummary[]>;
  loading: boolean;
}

/** 流式请求整体超时时间：AI 回答含工具调用时可能较长，给足 2 分钟。 */
const STREAM_TIMEOUT_MS = 120_000;

/** 流式对话状态机：发起 SSE 请求、逐步更新助手消息、结束时刷新会话列表。 */
export function useChatStream({
  setMessages,
  setInput,
  setLoading,
  scrollToBottom,
  updateAssistant,
  activeConversationId,
  setActiveConversationId,
  refreshConversations,
  loading,
}: UseChatStreamArgs) {
  // 记录当前正在进行的请求：发起新请求或组件卸载时，中止上一个流。
  const abortRef = useRef<AbortController | null>(null);
  const activeRequestIdRef = useRef(0);

  // 组件卸载时取消进行中的流式请求，避免对已卸载组件 setState。
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const ask = async (question: string) => {
    if (!question.trim() || loading) return;

    const requestId = ++activeRequestIdRef.current;
    abortRef.current?.abort();

    const controller = new AbortController();
    abortRef.current = controller;
    let timedOut = false;
    const timeoutId = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, STREAM_TIMEOUT_MS);

    const assistantId = createMessageId();
    const userMessage = createUserMessage(createMessageId(), question);
    setMessages((prev) => [
      ...prev,
      userMessage,
      createAssistantMessage(assistantId),
    ]);
    setInput("");
    setLoading(true);
    scrollToBottom();

    let accumulatedText = "";
    let accumulatedThinking = "";
    const toolCalls: ToolCallStep[] = [];
    let thinkingExpanded = false;
    let finalChat: ChatData | null = null;
    let flushTimer: ReturnType<typeof setTimeout> | null = null;

    const flush = () => {
      if (flushTimer) {
        clearTimeout(flushTimer);
        flushTimer = null;
      }
      updateAssistant(assistantId, (message) =>
        applyStreamSnapshot(message, {
          text: accumulatedText,
          thinkingContent: accumulatedThinking,
          thinkingExpanded,
          toolCalls,
        }),
      );
      scrollToBottom();
    };

    const scheduleFlush = () => {
      if (flushTimer) return;
      flushTimer = setTimeout(() => {
        flushTimer = null;
        flush();
      }, 50);
    };

    const isCurrentRequest = () => requestId === activeRequestIdRef.current;

    try {
      const token = getToken();
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { "X-Session-Token": token } : {}),
        },
        body: JSON.stringify({
          message: question,
          conversation_id: activeConversationId,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        let code: string | undefined;
        let message = "请求失败";
        try {
          const body = await response.json();
          code = typeof body?.code === "string" ? body.code : undefined;
          message = typeof body?.message === "string" ? body.message : message;
        } catch {
          // 非 JSON 错误仍使用通用提示。
        }
        handleAuthExpired(code);
        throw new ApiBizError(code ?? "UNKNOWN", message);
      }
      if (!response.body) {
        throw new ApiBizError("EMPTY_RESPONSE", "服务器未返回对话内容");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let parserState = { buffer: "", currentEvent: "" };

      const handleEvents = (events: SSEEvent[]) => {
        for (const { event, data } of events) {
          switch (event) {
            case "thinking": {
              accumulatedThinking += JSON.parse(data);
              thinkingExpanded = true;
              scheduleFlush();
              break;
            }
            case "tool_call": {
              const info = JSON.parse(data);
              toolCalls.push({ tool_name: info.tool_name, status: "calling" });
              flush();
              break;
            }
            case "tool_result": {
              const info = JSON.parse(data);
              const index = toolCalls.findIndex(
                (step) => step.tool_name === info.tool_name && step.status === "calling",
              );
              if (index !== -1) {
                toolCalls[index] = { ...toolCalls[index], status: "done" };
                flush();
              }
              break;
            }
            case "text": {
              accumulatedText += JSON.parse(data);
              thinkingExpanded = false;
              scheduleFlush();
              break;
            }
            case "done": {
              if (flushTimer) {
                clearTimeout(flushTimer);
                flushTimer = null;
              }
              finalChat = JSON.parse(data) as ChatData;
              thinkingExpanded = false;
              break;
            }
            case "error": {
              const payload = JSON.parse(data) as string | { code?: string; message?: string };
              const code = typeof payload === "string" ? undefined : payload.code;
              const message =
                typeof payload === "string" ? payload : payload.message ?? "对话请求失败";
              handleAuthExpired(code);
              throw new ApiBizError(code ?? "UNKNOWN", message);
            }
          }
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const parsed = parseSSEChunk(parserState, decoder.decode(value, { stream: true }));
        parserState = parsed.state;
        handleEvents(parsed.events);
      }

      const finalChunk = parseSSEChunk(parserState, `${decoder.decode()}\n`);
      handleEvents(finalChunk.events);

      if (flushTimer) {
        clearTimeout(flushTimer);
        flushTimer = null;
      }

      const completedChat = finalChat as ChatData | null;
      if (completedChat) {
        if (completedChat.conversation_id) {
          setActiveConversationId(completedChat.conversation_id);
        }
        updateAssistant(assistantId, (message) =>
          completeAssistantMessage(message, completedChat, accumulatedThinking, toolCalls),
        );
        await refreshConversations();
      } else {
        thinkingExpanded = false;
        flush();
      }
    } catch (error) {
      // 主动中止（发起新请求或组件卸载）时静默退出，不弹错误。
      if ((error as Error)?.name === "AbortError" && !timedOut) {
        return;
      }
      const msg =
        timedOut
          ? "对话请求超时，请稍后重试"
          : error instanceof Error
            ? error.message
            : "对话请求失败";
      if (isCurrentRequest()) {
        updateAssistant(assistantId, (message) =>
          failAssistantMessage(message, msg, accumulatedThinking, toolCalls),
        );
      }
    } finally {
      clearTimeout(timeoutId);
      if (isCurrentRequest()) {
        updateAssistant(assistantId, collapseThinking);
        setLoading(false);
        scrollToBottom();
      }
    }
  };

  return { ask };
}
