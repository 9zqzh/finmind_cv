import { useRef, useState } from "react";
import { Button, Card, Drawer } from "antd";
import { DoubleLeftOutlined, DoubleRightOutlined, HistoryOutlined } from "@ant-design/icons";
import { toggleThinking, type ChatMessage } from "../features/chat/model/chatStream";
import { ChatInputBar } from "../features/chat/components/ChatInputBar";
import { ConversationPanel } from "../features/chat/components/ConversationPanel";
import { MessageList } from "../features/chat/components/MessageList";
import { useIsMobile } from "../hooks/useIsMobile";
import { useAutoScroll } from "../features/chat/hooks/useAutoScroll";
import { useChatStream } from "../features/chat/hooks/useChatStream";
import { useConversationHistory } from "../features/chat/hooks/useConversationHistory";

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyCollapsed, setHistoryCollapsed] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const isMobile = useIsMobile();

  const scrollToBottom = useAutoScroll(listRef);
  const {
    conversations,
    historyLoading,
    activeConversationId,
    historyOpen,
    hasMoreTurns,
    setActiveConversationId,
    setHistoryOpen,
    openConversation,
    startNewConversation,
    loadOlderTurns,
    confirmDelete,
    refreshConversations,
  } = useConversationHistory({
    setMessages,
    isStreaming: loading,
    scrollToBottom,
  });

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

  const { ask } = useChatStream({
    setMessages,
    setInput,
    setLoading,
    scrollToBottom,
    updateAssistant,
    activeConversationId,
    setActiveConversationId,
    refreshConversations,
    loading,
  });

  const conversationPanel = (
    <ConversationPanel
      conversations={conversations}
      historyLoading={historyLoading}
      loading={loading}
      activeConversationId={activeConversationId}
      onStartNew={startNewConversation}
      onOpen={openConversation}
      onDelete={confirmDelete}
    />
  );

  return (
    <div
      className="chat-page"
      style={{ display: "flex", height: "calc(100dvh - 112px)", gap: 16 }}
    >
      {!isMobile &&
        (historyCollapsed ? (
          <Button
            type="text"
            icon={<DoubleRightOutlined />}
            onClick={() => setHistoryCollapsed(false)}
            aria-label="展开历史对话"
            title="展开历史对话"
            style={{ flexShrink: 0, alignSelf: "flex-start" }}
          />
        ) : (
          <Card
            size="small"
            title={
              <>
                <HistoryOutlined /> 历史对话
              </>
            }
            extra={
              <Button
                type="text"
                size="small"
                icon={<DoubleLeftOutlined />}
                onClick={() => setHistoryCollapsed(true)}
                aria-label="收起历史对话"
                title="收起历史对话"
              />
            }
            style={{ width: 240, flexShrink: 0 }}
            styles={{ body: { height: "calc(100% - 46px)", padding: 12 } }}
          >
            {conversationPanel}
          </Card>
        ))}
      <Drawer
        title="历史对话"
        placement="left"
        width="82%"
        open={isMobile && historyOpen}
        onClose={() => setHistoryOpen(false)}
      >
        {conversationPanel}
      </Drawer>
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        <MessageList
          listRef={listRef}
          messages={messages}
          hasMoreTurns={hasMoreTurns}
          historyLoading={historyLoading}
          loading={loading}
          onAsk={ask}
          onLoadOlder={loadOlderTurns}
          onThinkingToggle={handleThinkingToggle}
        />
        <ChatInputBar
          input={input}
          loading={loading}
          isMobile={isMobile}
          onChange={setInput}
          onSend={() => ask(input)}
          onOpenHistory={() => setHistoryOpen(true)}
        />
      </div>
    </div>
  );
}
