import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Avatar,
  Button,
  Card,
  Descriptions,
  Input,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from "antd";
import { RobotOutlined, SendOutlined, UserOutlined } from "@ant-design/icons";
import { api, ApiBizError } from "../api/client";
import type { ChatData } from "../api/types";

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  chat?: ChatData;
}

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
            <Descriptions size="small" column={4} bordered style={{ marginBottom: 12 }}>
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
  const listRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    setTimeout(() => {
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
    }, 50);
  };

  const ask = async (question: string) => {
    if (!question.trim() || loading) return;
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setInput("");
    setLoading(true);
    scrollToBottom();
    try {
      const chat = await api.chat(question);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: chat.answer, chat },
      ]);
    } catch (error) {
      const msg = error instanceof ApiBizError ? error.message : "对话请求失败";
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: `⚠️ ${msg}` },
      ]);
    } finally {
      setLoading(false);
      scrollToBottom();
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 112px)" }}>
      <div ref={listRef} style={{ flex: 1, overflowY: "auto", padding: "8px 4px" }}>
        {messages.length === 0 && (
          <Card style={{ textAlign: "center", marginTop: 40 }}>
            <Typography.Title level={4}>👋 你好，我是学院教学小助手</Typography.Title>
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
        {messages.map((msg, i) => (
          <div
            key={i}
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
            <div style={{ maxWidth: "78%" }}>
              <div
                style={{
                  background: msg.role === "user" ? "#e6f4ff" : "#fff",
                  padding: "10px 14px",
                  borderRadius: 10,
                  border: "1px solid #f0f0f0",
                }}
              >
                {msg.role === "user" ? (
                  <span style={{ whiteSpace: "pre-wrap" }}>{msg.text}</span>
                ) : (
                  <div className="markdown-body">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.text}
                    </ReactMarkdown>
                  </div>
                )}
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
        {loading && (
          <div style={{ textAlign: "center", padding: 8 }}>
            <Spin tip="小助手正在思考..." />
          </div>
        )}
      </div>
      <div style={{ paddingTop: 12, borderTop: "1px solid #f0f0f0" }}>
        <Space.Compact style={{ width: "100%" }}>
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
  );
}
