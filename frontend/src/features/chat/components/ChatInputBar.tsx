import { Button, Input, Space } from "antd";
import { HistoryOutlined, SendOutlined } from "@ant-design/icons";

interface ChatInputBarProps {
  input: string;
  loading: boolean;
  isMobile: boolean;
  onChange: (value: string) => void;
  onSend: () => void;
  onOpenHistory: () => void;
}

export function ChatInputBar({
  input,
  loading,
  isMobile,
  onChange,
  onSend,
  onOpenHistory,
}: ChatInputBarProps) {
  return (
    <div
      className="chat-input-bar"
      style={{ paddingTop: 12, borderTop: "1px solid #f0f0f0" }}
    >
      <Space.Compact style={{ width: "100%" }}>
        {isMobile && (
          <Button
            size="large"
            icon={<HistoryOutlined />}
            onClick={onOpenHistory}
            disabled={loading}
            aria-label="打开历史对话"
          />
        )}
        <Input
          size="large"
          value={input}
          onChange={(e) => onChange(e.target.value)}
          onPressEnter={onSend}
          placeholder="输入你的问题，例如：明天上午有什么课？"
          disabled={loading}
        />
        <Button
          type="primary"
          size="large"
          icon={<SendOutlined />}
          loading={loading}
          onClick={onSend}
        >
          发送
        </Button>
      </Space.Compact>
    </div>
  );
}
