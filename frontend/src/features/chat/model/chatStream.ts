import type { ChatData } from "../../../api/types";

export interface ToolCallStep {
  tool_name: string;
  status: "calling" | "done";
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  chat?: ChatData;
  thinkingContent?: string;
  thinkingExpanded?: boolean;
  toolCalls?: ToolCallStep[];
}

export interface StreamSnapshot {
  text: string;
  thinkingContent: string;
  thinkingExpanded: boolean;
  toolCalls: ToolCallStep[];
}

export interface SSEEvent {
  event: string;
  data: string;
}

export interface SSEParserState {
  buffer: string;
  currentEvent: string;
}

export function createMessageId() {
  return crypto.randomUUID();
}

export function createUserMessage(id: string, text: string): ChatMessage {
  return { id, role: "user", text };
}

export function createAssistantMessage(id: string): ChatMessage {
  return {
    id,
    role: "assistant",
    text: "",
    thinkingContent: "",
    thinkingExpanded: false,
    toolCalls: [],
  };
}

export function applyStreamSnapshot(
  message: ChatMessage,
  snapshot: StreamSnapshot,
): ChatMessage {
  return {
    ...message,
    text: snapshot.text,
    thinkingContent: snapshot.thinkingContent,
    thinkingExpanded: snapshot.thinkingExpanded,
    toolCalls: [...snapshot.toolCalls],
  };
}

export function completeAssistantMessage(
  message: ChatMessage,
  chat: ChatData,
  thinkingContent: string,
  toolCalls: ToolCallStep[],
): ChatMessage {
  return {
    ...message,
    text: chat.answer,
    chat,
    thinkingContent,
    thinkingExpanded: false,
    toolCalls: [...toolCalls],
  };
}

export function failAssistantMessage(
  message: ChatMessage,
  errorMessage: string,
  thinkingContent: string,
  toolCalls: ToolCallStep[],
): ChatMessage {
  return {
    ...message,
    text: `⚠️ ${errorMessage}`,
    thinkingContent,
    thinkingExpanded: false,
    toolCalls: [...toolCalls],
  };
}

export function collapseThinking(message: ChatMessage): ChatMessage {
  return { ...message, thinkingExpanded: false };
}

export function toggleThinking(message: ChatMessage): ChatMessage {
  return { ...message, thinkingExpanded: !message.thinkingExpanded };
}

export function parseSSEChunk(
  state: SSEParserState,
  chunk: string,
): { state: SSEParserState; events: SSEEvent[] } {
  const lines = `${state.buffer}${chunk}`.split(/\r?\n/);
  const buffer = lines.pop() ?? "";
  let currentEvent = state.currentEvent;
  const events: SSEEvent[] = [];

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      currentEvent = "";
      continue;
    }
    if (line.startsWith("event:")) {
      currentEvent = line.slice(6).trim();
      continue;
    }
    if (line.startsWith("data:") && currentEvent) {
      events.push({ event: currentEvent, data: line.slice(5).trimStart() });
    }
  }

  return {
    state: { buffer, currentEvent },
    events,
  };
}
