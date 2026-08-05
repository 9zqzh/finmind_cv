import { useState } from "react";
import { Button, Card, Input, List, message, Space, Tabs, Tag, Typography } from "antd";
import { api, ApiBizError } from "../api/client";
import type { SearchData } from "../api/types";

type SearchKind = "knowledge" | "information";

export default function KnowledgePage() {
  const [kind, setKind] = useState<SearchKind>("knowledge");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SearchData | null>(null);

  const search = async () => {
    const q = query.trim();
    if (!q) {
      message.warning("请输入搜索关键词");
      return;
    }
    setLoading(true);
    try {
      const fn = kind === "knowledge" ? api.knowledgeSearch : api.informationSearch;
      setResult(await fn(q));
    } catch (error) {
      if (error instanceof ApiBizError && error.code === "KNOWLEDGE_NOT_FOUND") {
        setResult({ query: q, results: [], sources: [] });
      } else {
        const msg = error instanceof ApiBizError ? error.message : "搜索失败";
        message.error(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="知识与资讯检索">
      <Space direction="vertical" style={{ width: "100%" }}>
        <Tabs
          activeKey={kind}
          onChange={(k) => {
            setKind(k as SearchKind);
            setResult(null);
          }}
          items={[
            { key: "knowledge", label: "知识库（办事流程/规章制度）" },
            { key: "information", label: "学院资讯（通知/竞赛）" },
          ]}
        />
        <Space.Compact style={{ width: "100%" }}>
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onPressEnter={search}
            placeholder={
              kind === "knowledge" ? "如：缓考申请、补办学生证" : "如：竞赛、讲座通知"
            }
          />
          <Button type="primary" loading={loading} onClick={search}>
            搜索
          </Button>
        </Space.Compact>
        {result && result.results.length === 0 && (
          <Typography.Text type="secondary">未找到相关内容，换个关键词试试。</Typography.Text>
        )}
        <List
          itemLayout="vertical"
          dataSource={result?.results ?? []}
          renderItem={(item) => (
            <List.Item
              key={item.title + item.source}
              extra={item.score !== undefined && <Tag>相关度 {item.score.toFixed(1)}</Tag>}
            >
              <List.Item.Meta
                title={item.title}
                description={`来源：${item.source}`}
              />
              <Typography.Paragraph
                style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}
              >
                {item.text}
              </Typography.Paragraph>
            </List.Item>
          )}
        />
      </Space>
    </Card>
  );
}
