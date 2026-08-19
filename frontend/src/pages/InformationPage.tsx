import { useEffect } from "react";
import { Card, List, Typography, Spin, Tabs, Empty } from "antd";
import {
  BellOutlined,
  ExperimentOutlined,
  ReadOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import {
  getInformationStore,
  subscribeToInformationStore,
  preloadInformationData,
} from "../stores/informationStore";
import { useSyncExternalStore } from "react";

const CATEGORY_LABELS: Record<string, string> = {
  xyxw: "学院新闻",
  xshuhd: "学术活动",
  xshenghd: "学生活动",
  tzgg: "公告通知",
};

const SECTION_ICONS: Record<string, React.ReactNode> = {
  xyxw: <ReadOutlined />,
  xshuhd: <ExperimentOutlined />,
  xshenghd: <TeamOutlined />,
  tzgg: <BellOutlined />,
};

function ArticleList({ items, category }: { items: { title: string; url: string; published_at: string | null; summary: string; image_url: string | null }[]; category: string }) {
  if (items.length === 0) {
    return <Empty description={`暂无${CATEGORY_LABELS[category] || category}`} />;
  }

  const simple = category === "xyxw";

  return (
    <List
      itemLayout="vertical"
      dataSource={items}
      renderItem={(item) => (
        <List.Item
          className="article-list-item"
          key={item.url}
          extra={
            item.image_url ? (
              <img
                className="article-list-image"
                width={140}
                alt={item.title}
                src={item.image_url}
                style={{ objectFit: "cover", borderRadius: 6 }}
              />
            ) : null
          }
        >
          <List.Item.Meta
            title={
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: 15, fontWeight: 500 }}
              >
                {item.title}
              </a>
            }
            description={
              item.published_at ? (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {item.published_at}
                </Typography.Text>
              ) : null
            }
          />
          {!simple && item.summary && (
            <Typography.Paragraph
              style={{ fontSize: 13, color: "#475467", margin: "8px 0 0" }}
              ellipsis={{ rows: 3 }}
            >
              {item.summary}
            </Typography.Paragraph>
          )}
        </List.Item>
      )}
    />
  );
}

export default function InformationPage() {
  const store = useSyncExternalStore(subscribeToInformationStore, getInformationStore);

  useEffect(() => {
    if (!store.loaded && !store.loading) {
      preloadInformationData();
    }
  }, [store.loaded, store.loading]);

  const sections = [
    { key: "xyxw", label: "xyxw", icon: SECTION_ICONS.xyxw },
    { key: "xshuhd", label: "xshuhd", icon: SECTION_ICONS.xshuhd },
    { key: "xshenghd", label: "xshenghd", icon: SECTION_ICONS.xshenghd },
    { key: "tzgg", label: "tzgg", icon: SECTION_ICONS.tzgg },
  ];

  if (store.loading && !store.loaded) {
    return (
      <Card title="学院资讯">
        <div style={{ textAlign: "center", padding: "60px 0" }}>
          <Spin size="large" tip="正在加载资讯..." />
        </div>
      </Card>
    );
  }

  return (
    <Card title="学院资讯">
      <Tabs
        defaultActiveKey="xyxw"
        items={sections.map((sec) => {
          const items = (store as any)[sec.key] ?? [];
          return {
            key: sec.key,
            label: (
              <span>
                {sec.icon} {CATEGORY_LABELS[sec.key] || sec.key}（{items.length}）
              </span>
            ),
            children: (
              <ArticleList
                items={items}
                category={sec.key}
              />
            ),
          };
        })}
      />
    </Card>
  );
}
