import { useEffect, useRef, useState } from "react";
import {
  Avatar,
  Button,
  Card,
  Drawer,
  Empty,
  Grid,
  Descriptions,
  Input,
  List,
  Modal,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from "antd";
import {
  BulbOutlined,
  DeleteOutlined,
  HistoryOutlined,
  LoadingOutlined,
  RobotOutlined,
  SendOutlined,
  PlusOutlined,
  UserOutlined,
} from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, ApiBizError, getToken, handleAuthExpired } from "../api/client";
import type { ChatData, ConversationSummary, StoredTurn } from "../api/types";
import {
  applyStreamSnapshot,
  collapseThinking,
  completeAssistantMessage,
  createAssistantMessage,
  createMessageId,
  createUserMessage,
  failAssistantMessage,
  parseSSEChunk,
  toggleThinking,
  type ChatMessage,
  type SSEEvent,
  type ToolCallStep,
} from "./chatStream";

/** 根据 result_type 推荐相关问题 */
const QUICK_QUESTIONS = [
  "我今天有什么课？",
  "我这学期的成绩怎么样？",
  "我们专业培养方案要修多少学分？",
  "缓考应该怎么申请？",
  "最近有什么竞赛可以参加？",
];

/** 根据后端 result_type 渲染结构化卡片 */
function ResultCard({ chat }: { chat: ChatData }) {
  const data = chat.data as Record<string, any> | null;
  if (!chat.tool_calls.length || !data) {
    return null;
  }

  switch (chat.result_type) {
    case "schedule": {
      const items = (data.items ?? []) as any[];
      return (
        <Table
          size="small"
          rowKey={(row) => `${row.course_name}-${row.weekday}-${row.period}`}
          dataSource={items}
          pagination={false}
          scroll={{ x: 720 }}
          columns={[
            { title: "课程", dataIndex: "course_name" },
            { title: "星期", dataIndex: "weekday", width: 70 },
            { title: "节次", dataIndex: "period_name", width: 110 },
            { title: "教室", dataIndex: "classroom", width: 130 },
            { title: "教师", dataIndex: "teacher", width: 100 },
            { title: "周次", dataIndex: "weeks_text", width: 110 },
          ]}
        />
      );
    }
    case "grades":
    case "training_plan": {
      const items = (data.items ?? []) as any[];
      return (
        <>
          {chat.result_type === "grades" && (
            <Descriptions
              size="small"
              column={{ xs: 1, sm: 2, md: 4 }}
              bordered
              style={{ marginBottom: 12 }}
            >
              <Descriptions.Item label="已获学分">
                {data.earned_credits ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="要求学分">
                {data.required_credits ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="主修绩点">
                {data.major_gpa ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="辅修绩点">
                {data.minor_gpa ?? "-"}
              </Descriptions.Item>
            </Descriptions>
          )}
          <Table
            size="small"
            rowKey="index"
            dataSource={items}
            pagination={{ pageSize: 10, hideOnSinglePage: true }}
            scroll={{ x: 760 }}
            columns={[
              { title: "课程", dataIndex: "course_name" },
              { title: "学期", dataIndex: "term", width: 120 },
              { title: "分数", dataIndex: "score", width: 80 },
              { title: "学分", dataIndex: "credit", width: 70 },
              { title: "绩点", dataIndex: "grade_point", width: 70 },
              { title: "属性", dataIndex: "course_attribute", width: 110 },
            ].filter(
              (col) => chat.result_type === "grades" || col.dataIndex !== "score",
            )}
          />
        </>
      );
    }
    case "classroom_schedule": {
      const items = (data.items ?? []) as any[];
      return (
        <Table
          size="small"
          rowKey={(row) => `${row.classroom}-${row.weekday}-${row.period}`}
          dataSource={items}
          pagination={{ pageSize: 10, hideOnSinglePage: true }}
          scroll={{ x: 640 }}
          columns={[
            { title: "教室", dataIndex: "classroom", width: 140 },
            { title: "星期", dataIndex: "weekday", width: 70 },
            { title: "节次", dataIndex: "period", width: 100 },
            { title: "课程", dataIndex: "course_name" },
            { title: "教师", dataIndex: "teacher", width: 100 },
          ]}
        />
      );
    }
    case "knowledge":
    case "information": {
      const results = (data.results ?? []) as any[];
      return (
        <Space direction="vertical" style={{ width: "100%" }}>
          {results.map((item, i) => (
            <Card key={i} size="small" title={item.title} extra={item.source}>
              <Typography.Paragraph
                style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}
                ellipsis={{ rows: 4, expandable: true }}
              >
                {item.text}
              </Typography.Paragraph>
            </Card>
          ))}
        </Space>
      );
    }
    default:
      return (
        <pre style={{ fontSize: 12, maxHeight: 260, overflow: "auto" }}>
          {JSON.stringify(data, null, 2)}
        </pre>
      );
  }
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [hasMoreTurns, setHasMoreTurns] = useState(false);
  const [oldestPosition, setOldestPosition] = useState<number | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.md;

  const turnsToMessages = (turns: StoredTurn[]): ChatMessage[] =>
    turns.flatMap((turn) => [
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

  const refreshConversations = async () => {
    const data = await api.conversations();
    setConversations(data.items);
    return data.items;
  };

  const openConversation = async (id: string) => {
    if (loading) return;
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
  };

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
    // Only load persisted history when the chat page is mounted.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startNewConversation = () => {
    if (loading) return;
    setActiveConversationId(null);
    setMessages([]);
    setHasMoreTurns(false);
    setOldestPosition(null);
    setHistoryOpen(false);
  };

  const loadOlderTurns = async () => {
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
  };

  const confirmDelete = (item: ConversationSummary) => {
    if (loading) return;
    Modal.confirm({
      title: "删除这段对话？",
      content: "删除后无法恢复。",
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        await api.deleteConversation(item.id);
        const remaining = conversations.filter((conversation) => conversation.id !== item.id);
        setConversations(remaining);
        if (activeConversationId === item.id) {
          if (remaining[0]) await openConversation(remaining[0].id);
          else startNewConversation();
        }
      },
    });
  };

  const updateAssistant = (
    assistantId: string,
    update: (message: ChatMessage) => ChatMessage,
  ) => {
    setMessages((prev) =>
      prev.map((message) => (message.id === assistantId ? update(message) : message)),
    );
  };

  const handleThinkingToggle = (assistantId: string) => {
    updateAssistant(assistantId, toggleThinking);
  };

  const scrollToBottom = () => {
    setTimeout(() => {
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
    }, 50);
  };

  const ask = async (question: string) => {
    if (!question.trim() || loading) return;
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
            case "error":
              throw new Error(JSON.parse(data));
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
      const msg = error instanceof Error ? error.message : "对话请求失败";
      updateAssistant(assistantId, (message) =>
        failAssistantMessage(message, msg, accumulatedThinking, toolCalls),
      );
    } finally {
      updateAssistant(assistantId, collapseThinking);
      setLoading(false);
      scrollToBottom();
    }
  };

  const historyContent = (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <Button
        type="primary"
        icon={<PlusOutlined />}
        onClick={startNewConversation}
        disabled={loading}
        style={{ marginBottom: 12 }}
      >
        新对话
      </Button>
      <div style={{ flex: 1, overflowY: "auto" }}>
        {conversations.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无历史对话" />
        ) : (
          <List
            size="small"
            loading={historyLoading}
            dataSource={conversations}
            renderItem={(item) => (
              <List.Item
                onClick={() => openConversation(item.id)}
                style={{
                  cursor: loading ? "not-allowed" : "pointer",
                  padding: "10px 8px",
                  borderRadius: 8,
                  background: activeConversationId === item.id ? "#e6f4ff" : undefined,
                }}
                actions={[
                  <Button
                    key="delete"
                    type="text"
                    danger
                    size="small"
                    aria-label="删除对话"
                    icon={<DeleteOutlined />}
                    disabled={loading}
                    onClick={(event) => {
                      event.stopPropagation();
                      confirmDelete(item);
                    }}
                  />,
                ]}
              >
                <Typography.Text ellipsis style={{ maxWidth: 150 }}>
                  {item.title}
                </Typography.Text>
              </List.Item>
            )}
          />
        )}
      </div>
    </div>
  );

  return (
    <div
      className="chat-page"
      style={{ display: "flex", height: "calc(100dvh - 112px)", gap: 16 }}
    >
      {!isMobile && (
        <Card
          size="small"
          title={<><HistoryOutlined /> 历史对话</>}
          style={{ width: 240, flexShrink: 0 }}
          styles={{ body: { height: "calc(100% - 46px)", padding: 12 } }}
        >
          {historyContent}
        </Card>
      )}
      <Drawer
        title="历史对话"
        placement="left"
        width="82%"
        open={isMobile && historyOpen}
        onClose={() => setHistoryOpen(false)}
      >
        {historyContent}
      </Drawer>
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
      <div
        ref={listRef}
        className="chat-list"
        style={{ flex: 1, overflowY: "auto", padding: "8px 4px" }}
      >
          {hasMoreTurns && (
            <div style={{ textAlign: "center", marginBottom: 12 }}>
              <Button size="small" loading={historyLoading} onClick={loadOlderTurns}>
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
                  <Button key={q} size="small" onClick={() => ask(q)}>
                    {q}
                  </Button>
                ))}
              </Space>
            </Card>
          )}
          {messages.map((msg) => (
            <div
              key={msg.id}
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
                    onClick={() => handleThinkingToggle(msg.id)}
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
                    <span style={{ fontSize: 12, color: "#8c8c8c", transform: msg.thinkingExpanded ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }}>
                      ▼
                    </span>
                  </div>
                  {msg.thinkingExpanded && (
                    <div style={{ padding: "0 14px 10px" }}>
                      <div style={{ whiteSpace: "pre-wrap" }}>{msg.thinkingContent}</div>
                      {msg.toolCalls && msg.toolCalls.length > 0 && (
                        <div style={{ marginTop: 8, borderTop: "1px dashed #d6e4ff", paddingTop: 6 }}>
                          {msg.toolCalls.map((step, j) => (
                            <div key={j} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
                              {step.status === "calling" ? (
                                <LoadingOutlined style={{ color: "#1677ff" }} />
                              ) : (
                                <span style={{ color: "#52c41a" }}>✅</span>
                              )}
                              <span style={{ color: step.status === "calling" ? "#1d2939" : "#5b6270" }}>
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
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.text}
                    </ReactMarkdown>
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
                  <ResultCard chat={msg.chat} />
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
        ))}
      </div>
      <div
        className="chat-input-bar"
        style={{ paddingTop: 12, borderTop: "1px solid #f0f0f0" }}
      >
        <Space.Compact style={{ width: "100%" }}>
          {isMobile && (
            <Button
              size="large"
              icon={<HistoryOutlined />}
              onClick={() => setHistoryOpen(true)}
              disabled={loading}
              aria-label="打开历史对话"
            />
          )}
          <Input
            size="large"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={() => ask(input)}
            placeholder="输入你的问题，例如：明天上午有什么课？"
            disabled={loading}
          />
          <Button
            type="primary"
            size="large"
            icon={<SendOutlined />}
            loading={loading}
            onClick={() => ask(input)}
          >
            发送
          </Button>
        </Space.Compact>
      </div>
      </div>
    </div>
  );
}
