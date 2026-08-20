import { describe, expect, it } from "vitest";
import type { ChatData } from "../api/types";
import {
  applyStreamSnapshot,
  completeAssistantMessage,
  createAssistantMessage,
  failAssistantMessage,
  parseSSEChunk,
  toggleThinking,
} from "./chatStream";

const completedChat: ChatData = {
  answer: "查询完成",
  intent: "chat",
  tool_calls: [],
  result_type: "text",
  data: null,
  sources: [],
  citations: [],
  conversation_id: "page-1",
};

describe("chat stream state", () => {
  it("collapses thinking when done arrives without text chunks", () => {
    const thinking = applyStreamSnapshot(createAssistantMessage("assistant-1"), {
      text: "",
      thinkingContent: "正在分析问题",
      thinkingExpanded: true,
      toolCalls: [],
    });

    const completed = completeAssistantMessage(
      thinking,
      completedChat,
      thinking.thinkingContent ?? "",
      thinking.toolCalls ?? [],
    );

    expect(completed.thinkingExpanded).toBe(false);
    expect(completed.text).toBe("查询完成");
  });

  it("collapses thinking after tool work ends with an error", () => {
    const thinking = applyStreamSnapshot(createAssistantMessage("assistant-2"), {
      text: "",
      thinkingContent: "正在查询教务系统",
      thinkingExpanded: true,
      toolCalls: [{ tool_name: "query_schedule", status: "calling" }],
    });

    const failed = failAssistantMessage(
      thinking,
      "教务系统暂时不可用",
      thinking.thinkingContent ?? "",
      thinking.toolCalls ?? [],
    );

    expect(failed.thinkingExpanded).toBe(false);
    expect(failed.text).toBe("⚠️ 教务系统暂时不可用");
  });

  it("allows a completed thinking panel to be manually reopened", () => {
    const completed = completeAssistantMessage(
      createAssistantMessage("assistant-3"),
      completedChat,
      "完成推理",
      [],
    );

    expect(toggleThinking(completed).thinkingExpanded).toBe(true);
  });
});

describe("SSE parsing", () => {
  it("does not reuse an event type after the SSE frame ends", () => {
    const first = parseSSEChunk(
      { buffer: "", currentEvent: "" },
      'event: thinking\ndata: "分析中"\n\n',
    );
    const second = parseSSEChunk(first.state, 'data: "不应沿用事件"\n\n');

    expect(first.events).toEqual([{ event: "thinking", data: '"分析中"' }]);
    expect(second.events).toEqual([]);
  });
});
