import { useState } from "react";
import { Button, Card, Input, List, message, Space, Tag, Typography } from "antd";
import { api, ApiBizError } from "../api/client";
import type { SearchData } from "../api/types";

export default function InformationPage() {
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
      setResult(await api.informationSearch(q));
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
    <Card title="学院资讯（通知）">
      <Space direction="vertical" style={{ width: "100%" }}>
        <Space.Compact style={{ width: "100%" }}>
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onPressEnter={search}
            placeholder="如：竞赛、讲座通知"
          />
          <Button type="primary" loading={loading} onClick={search}>
            搜索
          </Button>
        </Space.Compact>
        {result && result.results.length === 0 && (
          <Typography.Text type="secondary">
            未找到相关内容，换个关键词试试。
          </Typography.Text>
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
