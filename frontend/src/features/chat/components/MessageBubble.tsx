import { Avatar, Space, Spin, Tag, Typography } from "antd";
import {
  BulbOutlined,
  LoadingOutlined,
  RobotOutlined,
  UserOutlined,
} from "@ant-design/icons";
import type { ChatMessage } from "../model/chatStream";
import { hasResolvedCitation } from "../utils/citationParser";
import { CitationMarkdown } from "./CitationMarkdown";
import { ResultCard } from "./ResultCard";

interface MessageBubbleProps {
  msg: ChatMessage;
  loading: boolean;
  onThinkingToggle: (assistantId: string) => void;
}

export function MessageBubble({ msg, loading, onThinkingToggle }: MessageBubbleProps) {
  return (
    <div
      className="chat-message"
      style={{
        display: "flex",
        gap: 12,
        marginBottom: 16,
        flexDirection: msg.role === "user" ? "row-reverse" : "row",
      }}
    >
      <Avatar
        icon={msg.role === "user" ? <UserOutlined /> : <RobotOutlined />}
        style={{ background: msg.role === "user" ? "#1677ff" : "#52c41a" }}
      />
      <div className="chat-message__content" style={{ maxWidth: "78%" }}>
        {/* 思考过程 */}
        {msg.thinkingContent && (
          <div
            style={{
              background: "#f0f5ff",
              border: "1px solid #d6e4ff",
              borderRadius: 8,
              marginBottom: 8,
              fontSize: 13,
              lineHeight: 1.6,
              color: "#1d2939",
              overflow: "hidden",
            }}
          >
            <div
              onClick={() => onThinkingToggle(msg.id)}
              style={{
                padding: "8px 14px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                userSelect: "none",
              }}
            >
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                <BulbOutlined style={{ marginRight: 4 }} />
                AI 思考过程
                <span style={{ marginLeft: 6, color: "#8c8c8c" }}>
                  {msg.thinkingExpanded ? "（点击收起）" : "（点击展开）"}
                </span>
              </Typography.Text>
              <span
                style={{
                  fontSize: 12,
                  color: "#8c8c8c",
                  transform: msg.thinkingExpanded ? "rotate(180deg)" : "rotate(0deg)",
                  transition: "transform 0.2s",
                }}
              >
                ▼
              </span>
            </div>
            {msg.thinkingExpanded && (
              <div style={{ padding: "0 14px 10px" }}>
                <div style={{ whiteSpace: "pre-wrap" }}>{msg.thinkingContent}</div>
                {msg.toolCalls && msg.toolCalls.length > 0 && (
                  <div
                    style={{
                      marginTop: 8,
                      borderTop: "1px dashed #d6e4ff",
                      paddingTop: 6,
                    }}
                  >
                    {msg.toolCalls.map((step, j) => (
                      <div
                        key={j}
                        style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}
                      >
                        {step.status === "calling" ? (
                          <LoadingOutlined style={{ color: "#1677ff" }} />
                        ) : (
                          <span style={{ color: "#52c41a" }}>✅</span>
                        )}
                        <span
                          style={{
                            color: step.status === "calling" ? "#1d2939" : "#5b6270",
                          }}
                        >
                          {step.status === "calling" ? "正在调用：" : "已完成："}
                          {step.tool_name}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
        {/* 回答气泡 */}
        <div
          className="chat-bubble"
          style={{
            background: msg.role === "user" ? "#e6f4ff" : "#fff",
            padding: "10px 14px",
            borderRadius: 10,
            border: "1px solid #f0f0f0",
          }}
        >
          {msg.role === "user" ? (
            <span style={{ whiteSpace: "pre-wrap" }}>{msg.text}</span>
          ) : msg.text ? (
            <div className="markdown-body">
              <CitationMarkdown text={msg.text} citations={msg.chat?.citations ?? []} />
            </div>
          ) : loading && !msg.thinkingContent ? (
            <Spin indicator={<LoadingOutlined />} tip="FinMind 正在思考..." />
          ) : null}
        </div>
        {msg.chat && (
          <div style={{ marginTop: 8 }}>
            {msg.chat.tool_calls.length > 0 && (
              <Space size={4} style={{ marginBottom: 6 }}>
                {msg.chat.tool_calls.map((t, j) => (
                  <Tag key={j} color="geekblue">
                    🔧 {t.tool}
                  </Tag>
                ))}
              </Space>
            )}
            {!hasResolvedCitation(msg.text, msg.chat.citations ?? []) && (
              <ResultCard chat={msg.chat} />
            )}
            {msg.chat.sources.length > 0 && (
              <div style={{ marginTop: 6 }}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  来源：{msg.chat.sources.join("；")}
                </Typography.Text>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
