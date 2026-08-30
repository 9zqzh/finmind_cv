import type { Ref } from "react";
import { Button, Card, Space, Typography } from "antd";
import type { ChatMessage } from "../model/chatStream";
import { MessageBubble } from "./MessageBubble";

const QUICK_QUESTIONS = [
  "我今天有什么课？",
  "我这学期的成绩怎么样？",
  "我们专业培养方案要修多少学分？",
  "缓考应该怎么申请？",
  "最近有什么竞赛可以参加？",
  "学校周边有什么好吃的？",
];

interface MessageListProps {
  listRef: Ref<HTMLDivElement>;
  messages: ChatMessage[];
  hasMoreTurns: boolean;
  historyLoading: boolean;
  loading: boolean;
  onAsk: (question: string) => void;
  onLoadOlder: () => void;
  onThinkingToggle: (assistantId: string) => void;
}

export function MessageList({
  listRef,
  messages,
  hasMoreTurns,
  historyLoading,
  loading,
  onAsk,
  onLoadOlder,
  onThinkingToggle,
}: MessageListProps) {
  return (
    <div
      ref={listRef}
      className="chat-list"
      style={{ flex: 1, overflowY: "auto", padding: "8px 4px" }}
    >
      {hasMoreTurns && (
        <div style={{ textAlign: "center", marginBottom: 12 }}>
          <Button size="small" loading={historyLoading} onClick={onLoadOlder}>
            加载更早记录
          </Button>
        </div>
      )}
      {messages.length === 0 && (
        <Card className="chat-welcome" style={{ textAlign: "center", marginTop: 40 }}>
          <Typography.Title level={4}>👋 你好，我是数智金院 FinMind</Typography.Title>
          <Typography.Paragraph type="secondary">
            可以问我课表、成绩、培养方案、学院制度、竞赛信息等任何问题
          </Typography.Paragraph>
          <Space wrap>
            {QUICK_QUESTIONS.map((q) => (
              <Button key={q} size="small" onClick={() => onAsk(q)}>
                {q}
              </Button>
            ))}
          </Space>
        </Card>
      )}
      {messages.map((msg) => (
        <MessageBubble
          key={msg.id}
          msg={msg}
          loading={loading}
          onThinkingToggle={onThinkingToggle}
        />
      ))}
    </div>
  );
}
