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
  EnvironmentOutlined,
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
import type {
  ChatData,
  CitationInfo,
  ConversationSummary,
  StoredTurn,
} from "../api/types";
import { hasResolvedCitation, parseCitationSegments } from "./citationParser";
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
  "学校周边有什么好吃的？",
];

/** 出行方式中文名 */
const MODE_LABELS: Record<string, string> = {
  walking: "步行",
  driving: "驾车",
  bicycling: "骑行",
  transit: "公交",
};

/** 按评分高低着色 */
function ratingTag(rating: number) {
  if (!rating) return <Tag>暂无评分</Tag>;
  const color =
    rating >= 4.5 ? "green" : rating >= 4.0 ? "blue" : rating >= 3.5 ? "orange" : "default";
  return <Tag color={color}>⭐ {rating.toFixed(1)}</Tag>;
}

/** 距离展示：不足 1 公里用米 */
function formatDistance(distance: number | null | undefined) {
  if (!distance) return null;
  return distance >= 1000 ? `${(distance / 1000).toFixed(1)} 公里` : `${Math.round(distance)} 米`;
}

/** 生成高德 URI 导航链接（步行） */
function amapNavigationUrl(location: string, name?: string) {
  const [lng, lat] = String(location ?? "").split(",");
  if (!lng || !lat) return null;
  const label = name ? `,${encodeURIComponent(name)}` : "";
  return `https://uri.amap.com/navigation?to=${lng},${lat}${label}&mode=walk&coordinate=gaode`;
}

/** 只允许打开后端登记的高德 HTTPS URI，拒绝模型文本或异常载荷注入链接。 */
function trustedAmapUrl(value: string | null | undefined) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.hostname === "uri.amap.com" ? url.href : null;
  } catch {
    return null;
  }
}

function trustedImageUrl(value: unknown) {
  if (typeof value !== "string" || !value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

function PlaceCover({ imageUrl, name }: { imageUrl: unknown; name: string }) {
  const url = trustedImageUrl(imageUrl);
  if (!url) return null;
  return (
    <div className="map-place-cover">
      <img
        src={url}
        alt={`${name}门店图片`}
        loading="lazy"
        referrerPolicy="no-referrer"
        onError={(event) => {
          event.currentTarget.style.display = "none";
        }}
      />
    </div>
  );
}

function MapCitationCard({ citation }: { citation: CitationInfo }) {
  const data = citation.data as Record<string, any>;
  const url = trustedAmapUrl(citation.url);
  const isPlace = citation.type === "map_place";
  const content = (
    <Card className="map-citation-card" size="small" bordered>
      {isPlace && <PlaceCover imageUrl={data.image_url} name={citation.title} />}
      <div className="map-citation-card__content">
        <div className="map-citation-card__header">
          <EnvironmentOutlined className="map-citation-card__pin" />
          <Typography.Text strong className="map-citation-card__title">
            {citation.title}
          </Typography.Text>
          <span className="map-citation-card__action">
            {isPlace ? "查看位置" : "打开导航"} ↗
          </span>
        </div>
        {isPlace ? (
          <>
            <Space size={[4, 4]} wrap className="map-citation-card__tags">
              {ratingTag(Number(data.rating))}
              {Number(data.cost) > 0 && <Tag color="gold">人均 ¥{data.cost}</Tag>}
              {Number(data.comment_num) > 0 && <Tag>{data.comment_num} 条点评</Tag>}
              {formatDistance(Number(data.distance)) && (
                <Tag color="blue">距中心 {formatDistance(Number(data.distance))}</Tag>
              )}
            </Space>
            {data.address && (
              <Typography.Text type="secondary" className="map-citation-card__meta">
                {String(data.address)}
              </Typography.Text>
            )}
          </>
        ) : (
          <div className="map-citation-card__route">
            <Tag color="geekblue">{MODE_LABELS[String(data.mode)] ?? data.mode ?? "路线"}</Tag>
            <Typography.Text type="secondary">
              {data.distance_text ?? "距离未知"} · {data.duration_text ?? "耗时未知"}
            </Typography.Text>
          </div>
        )}
      </div>
    </Card>
  );

  return url ? (
    <a
      className="map-citation-link"
      href={url}
      target="_blank"
      rel="noreferrer"
      aria-label={`${citation.title}，${isPlace ? "查看位置" : "打开导航"}`}
    >
      {content}
    </a>
  ) : (
    <div className="map-citation-link map-citation-link--disabled">{content}</div>
  );
}

function CitationMarkdown({ text, citations }: { text: string; citations: CitationInfo[] }) {
  const segments = parseCitationSegments(text, citations);
  return (
    <>
      {segments.map((segment, index) =>
        segment.kind === "citation" ? (
          <MapCitationCard key={`${segment.citation.ref}-${index}`} citation={segment.citation} />
        ) : (
          <ReactMarkdown key={`markdown-${index}`} remarkPlugins={[remarkGfm]}>
            {segment.text}
          </ReactMarkdown>
        ),
      )}
    </>
  );
}

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
    case "map_places": {
      const places = (data.places ?? []) as any[];
      return (
        <List
          size="small"
          dataSource={places}
          renderItem={(item) => {
            const url = amapNavigationUrl(item.location, item.name);
            return (
              <List.Item style={{ paddingInline: 0 }}>
                <div style={{ width: "100%" }}>
                  <PlaceCover imageUrl={item.image_url} name={item.name ?? "地点"} />
                  <Space wrap>
                    <Typography.Text strong>{item.name}</Typography.Text>
                    {ratingTag(Number(item.rating))}
                    {Number(item.cost) > 0 && (
                      <Tag color="gold">人均 ¥{item.cost}</Tag>
                    )}
                    {Number(item.comment_num) > 0 && (
                      <Tag>{item.comment_num} 条点评</Tag>
                    )}
                  </Space>
                  <div style={{ marginTop: 4 }}>
                    {item.distance ? (
                      <Typography.Text type="secondary" style={{ marginRight: 8 }}>
                        📍 距中心 {formatDistance(item.distance)}
                      </Typography.Text>
                    ) : null}
                    {item.address ? (
                      <Typography.Text type="secondary">{item.address}</Typography.Text>
                    ) : null}
                  </div>
                  {item.tel ? (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      📞 {item.tel}
                    </Typography.Text>
                  ) : null}
                  {url && (
                    <div style={{ marginTop: 4 }}>
                      <a href={url} target="_blank" rel="noreferrer">
                        查看位置与导航 ↗
                      </a>
                    </div>
                  )}
                </div>
              </List.Item>
            );
          }}
        />
      );
    }
    case "map_route": {
      const modeLabel = MODE_LABELS[data.mode] ?? data.mode ?? "步行";
      const steps = (data.steps ?? []) as string[];
      return (
        <Space direction="vertical" style={{ width: "100%" }}>
          <Descriptions size="small" column={{ xs: 1, sm: 3 }} bordered>
            <Descriptions.Item label="出行方式">{modeLabel}</Descriptions.Item>
            <Descriptions.Item label="距离">
              {data.distance_text ?? "-"}
            </Descriptions.Item>
            <Descriptions.Item label="预计耗时">
              {data.duration_text ?? "-"}
            </Descriptions.Item>
          </Descriptions>
          {steps.length > 0 && (
            <Typography.Paragraph
              style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}
              type="secondary"
            >
              {steps.map((step, i) => `${i + 1}. ${step}`).join("\n")}
            </Typography.Paragraph>
          )}
          {data.navigation_url && (
            <Button
              type="primary"
              size="small"
              href={data.navigation_url}
              target="_blank"
            >
              打开高德导航
            </Button>
          )}
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
