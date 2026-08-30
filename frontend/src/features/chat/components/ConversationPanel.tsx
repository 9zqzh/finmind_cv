import { Button, Empty, List, Typography } from "antd";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import type { ConversationSummary } from "../../../api/types";

interface ConversationPanelProps {
  conversations: ConversationSummary[];
  historyLoading: boolean;
  loading: boolean;
  activeConversationId: string | null;
  onStartNew: () => void;
  onOpen: (id: string) => void;
  onDelete: (item: ConversationSummary) => void;
}

export function ConversationPanel({
  conversations,
  historyLoading,
  loading,
  activeConversationId,
  onStartNew,
  onOpen,
  onDelete,
}: ConversationPanelProps) {
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <Button
        type="primary"
        icon={<PlusOutlined />}
        onClick={onStartNew}
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
                onClick={() => onOpen(item.id)}
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
                      onDelete(item);
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
}
