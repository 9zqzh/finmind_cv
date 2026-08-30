import { useEffect, useState, useSyncExternalStore } from "react";
import { Card, Col, Modal, Row, Tag, Typography, Spin, Space, Empty, Tabs } from "antd";
import {
  ClockCircleOutlined,
  TeamOutlined,
  TrophyOutlined,
  LinkOutlined,
  WechatOutlined,
  CalendarOutlined,
  BellOutlined,
  BulbOutlined,
} from "@ant-design/icons";
import {
  getCompetitionStore,
  subscribeToCompetitionStore,
  preloadCompetitionData,
} from "../stores/competitionStore";
import type { CompetitionItem, NoticeItem, ClubItem } from "../stores/competitionStore";
import { useIsMobile } from "../hooks/useIsMobile";

// 类型从 competitionStore 导入





// ---- 状态映射 ----
const STATUS_LABELS: Record<string, string> = {
  in_progress: "进行中",
  registration_open: "报名中",
  upcoming: "即将开始",
  finished: "已结束",
  previous_recording: "往届回顾",
};

const STATUS_COLORS: Record<string, string> = {
  in_progress: "green",
  registration_open: "blue",
  upcoming: "cyan",
  finished: "default",
  previous_recording: "purple",
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  in_progress: <TrophyOutlined />,
  registration_open: <ClockCircleOutlined />,
};

const RECOGNITION_LABELS: Record<string, string> = {
  school_and_national: "校赛/国赛",
  unlisted: "未定级",
};

const RECOGNITION_COLORS: Record<string, string> = {
  school_and_national: "orange",
  unlisted: "default",
};

const PRIORITY_LABELS: Record<string, string> = {
  urgent: "紧急",
  high: "重要",
  normal: "普通",
  low: "低",
};

const PRIORITY_COLORS: Record<string, string> = {
  urgent: "red",
  high: "orange",
  normal: "blue",
  low: "default",
};

// ---- 工具函数 ----
const formatDate = (iso: string | null) => {
  if (!iso) return "待定";
  return iso.slice(0, 10);
};

const formatDateTime = (iso: string | null) => {
  if (!iso) return "待定";
  return iso.slice(0, 16).replace("T", " ");
};

// ---- 组件 ----
function CompetitionCard({ item }: { item: CompetitionItem }) {
  const [open, setOpen] = useState(false);
  const isMobile = useIsMobile();

  return (
    <>
      <Card
        hoverable
        size="small"
        className="competition-card"
        style={{ height: "100%" }}
        onClick={() => setOpen(true)}
        actions={[
          ...(item.official_url
            ? [
                <a
                  href={item.official_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                >
                  <LinkOutlined /> 官网
                </a>,
              ]
            : []),
          ...(item.wechat_article_url
            ? [
                <a
                  href={item.wechat_article_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                >
                  <WechatOutlined /> 推文
                </a>,
              ]
            : []),
        ]}
      >
        <Space direction="vertical" size={6} style={{ width: "100%" }}>
          <Typography.Text strong style={{ fontSize: 14, lineHeight: 1.4 }}>
            {item.title}
          </Typography.Text>

          <Space size={4} wrap>
            <Tag
              color={STATUS_COLORS[item.status] || "default"}
              icon={STATUS_ICONS[item.status]}
            >
              {STATUS_LABELS[item.status] || item.status}
            </Tag>
            {item.category && <Tag>{item.category}</Tag>}
            {item.recognition && (
              <Tag color={RECOGNITION_COLORS[item.recognition] || "default"}>
                {RECOGNITION_LABELS[item.recognition] || item.recognition}
              </Tag>
            )}
            {item.year && <Tag>{item.year}</Tag>}
          </Space>

          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            <TeamOutlined style={{ marginRight: 4 }} />
            {item.department || "全校"}
            {item.registration_mode === "team" && (
              <>
                {" · "}组队参赛（最多{item.max_team_size}人，{item.max_advisors}位指导老师）
              </>
            )}
            {item.registration_mode === "individual" && (
              <> · 个人参赛</>
            )}
          </Typography.Text>

          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            <CalendarOutlined style={{ marginRight: 4 }} />
            报名：{formatDate(item.registration_start_at)} ~ {formatDate(item.registration_end_at)}
          </Typography.Text>

          {(item.event_start_at || item.event_end_at) && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              <ClockCircleOutlined style={{ marginRight: 4 }} />
              比赛：{formatDate(item.event_start_at)} ~ {formatDate(item.event_end_at)}
            </Typography.Text>
          )}

          {item.cta_label && (
            <Typography.Text style={{ fontSize: 12, color: "#1677ff" }}>
              <BulbOutlined style={{ marginRight: 4 }} />
              {item.cta_label}
            </Typography.Text>
          )}


        </Space>
      </Card>

      <Modal
        title={item.title}
        open={open}
        onCancel={() => setOpen(false)}
        footer={null}
        width={isMobile ? "calc(100vw - 32px)" : 700}
        style={{ top: isMobile ? 16 : 40 }}
      >
        <div
          className="competition-modal-content"
          style={{ maxHeight: "65vh", overflowY: "auto", paddingRight: 8 }}
        >
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Space size={4} wrap>
              <Tag
                color={STATUS_COLORS[item.status] || "default"}
                icon={STATUS_ICONS[item.status]}
              >
                {STATUS_LABELS[item.status] || item.status}
              </Tag>
              {item.category && <Tag>{item.category}</Tag>}
              {item.recognition && (
                <Tag color={RECOGNITION_COLORS[item.recognition] || "default"}>
                  {RECOGNITION_LABELS[item.recognition] || item.recognition}
                </Tag>
              )}
              {item.year && <Tag>{item.year}</Tag>}
            </Space>

            <Typography.Text type="secondary" style={{ fontSize: 13 }}>
              <TeamOutlined style={{ marginRight: 6 }} />
              {item.department || "全校"}
              {item.registration_mode === "team" && (
                <> · 组队参赛（最多{item.max_team_size}人，{item.max_advisors}位指导老师）</>
              )}
              {item.registration_mode === "individual" && (
                <> · 个人参赛</>
              )}
            </Typography.Text>

            <Typography.Text type="secondary" style={{ fontSize: 13 }}>
              <CalendarOutlined style={{ marginRight: 6 }} />
              报名时间：{formatDate(item.registration_start_at)} ~ {formatDate(item.registration_end_at)}
            </Typography.Text>

            {(item.event_start_at || item.event_end_at) && (
              <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                <ClockCircleOutlined style={{ marginRight: 6 }} />
                比赛时间：{formatDate(item.event_start_at)} ~ {formatDate(item.event_end_at)}
              </Typography.Text>
            )}

            {item.cta_label && (
              <Typography.Text style={{ fontSize: 13, color: "#1677ff" }}>
                <BulbOutlined style={{ marginRight: 6 }} />
                {item.cta_label}
              </Typography.Text>
            )}

            {item.summary && (
              <Typography.Paragraph
                style={{ fontSize: 14, margin: 0, color: "#344054", lineHeight: 1.6, whiteSpace: "pre-wrap" }}
              >
                {item.summary}
              </Typography.Paragraph>
            )}

            {item.official_url && (
              <Typography.Text className="competition-link">
                <LinkOutlined style={{ marginRight: 6 }} />
                官网：<a href={item.official_url} target="_blank" rel="noopener noreferrer">{item.official_url}</a>
              </Typography.Text>
            )}

            {item.wechat_article_url && (
              <Typography.Text className="competition-link">
                <WechatOutlined style={{ marginRight: 6 }} />
                推文：<a href={item.wechat_article_url} target="_blank" rel="noopener noreferrer">{item.wechat_article_url}</a>
              </Typography.Text>
            )}

            <div style={{ textAlign: "right", marginTop: 8 }}>
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: 14 }}
              >
                <LinkOutlined /> 跳转学院竞赛中心 →
              </a>
            </div>
          </Space>
        </div>
      </Modal>
    </>
  );
}

function NoticeCard({ item }: { item: NoticeItem }) {
  return (
    <Card size="small" style={{ marginBottom: 12 }}>
      <Space direction="vertical" size={4} style={{ width: "100%" }}>
        <Space wrap size={4}>
          <Tag color={PRIORITY_COLORS[item.priority] || "default"}>
            {PRIORITY_LABELS[item.priority] || item.priority}
          </Tag>
          {item.competition_title && <Tag>{item.competition_title}</Tag>}
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {formatDateTime(item.published_at)}
          </Typography.Text>
        </Space>
        <Typography.Text strong>{item.title}</Typography.Text>
        <Typography.Paragraph
          style={{ fontSize: 13, margin: 0, color: "#475467", whiteSpace: "pre-wrap" }}
          ellipsis={{ rows: 4 }}
        >
          {item.content}
        </Typography.Paragraph>
      </Space>
    </Card>
  );
}

function ClubCard({ item }: { item: ClubItem }) {
  return (
    <Card
      hoverable
      size="small"
      style={{ height: "100%", borderTop: item.theme_color ? `3px solid ${item.theme_color}` : undefined }}
      onClick={() => window.open(item.url, "_blank", "noopener")}
    >
      <Space direction="vertical" size={6} style={{ width: "100%" }}>
        <Typography.Text strong style={{ fontSize: 15 }}>
          {item.name}
        </Typography.Text>
        {item.short_name && item.short_name !== item.name && (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {item.short_name}
          </Typography.Text>
        )}
        {item.slogan && (
          <Typography.Text
            style={{ fontSize: 13, color: "#475467", fontStyle: "italic" }}
          >
            "{item.slogan}"
          </Typography.Text>
        )}
        {item.focus_areas && item.focus_areas.length > 0 && (
          <Space size={4} wrap>
            {item.focus_areas.map((area) => (
              <Tag key={area} color="purple">{area}</Tag>
            ))}
          </Space>
        )}
      </Space>
    </Card>
  );
}

// ---- 主页面 ----
export default function CompetitionPage() {
  const store = useSyncExternalStore(subscribeToCompetitionStore, getCompetitionStore);

  useEffect(() => {
    if (!store.loaded && !store.loading) {
      preloadCompetitionData();
    }
  }, [store.loaded, store.loading]);

  const items = store.items as CompetitionItem[];
  const notices = store.notices as NoticeItem[];
  const clubs = store.clubs as ClubItem[];
  const loading = store.loading && !store.loaded;

  if (loading) {
    return (
      <Card title="竞赛信息">
        <div style={{ textAlign: "center", padding: "60px 0" }}>
          <Spin size="large" tip="正在加载竞赛信息..." />
        </div>
      </Card>
    );
  }

  return (
    <Card title="竞赛信息">
      <Tabs
        defaultActiveKey="competitions"
        items={[
          {
            key: "competitions",
            label: (
              <span>
                <TrophyOutlined /> 比赛列表（{items.length}）
              </span>
            ),
            children: items.length === 0 ? (
              <Empty description="暂无竞赛数据" />
            ) : (
              <Row gutter={[16, 16]}>
                {items.map((item) => (
                  <Col xs={12} sm={12} lg={8} xl={6} key={item.id}>
                    <CompetitionCard item={item} />
                  </Col>
                ))}
              </Row>
            ),
          },
          {
            key: "notices",
            label: (
              <span>
                <BellOutlined /> 公告通知（{notices.length}）
              </span>
            ),
            children: notices.length === 0 ? (
              <Empty description="暂无公告" />
            ) : (
              notices.map((item) => <NoticeCard key={item.id} item={item} />)
            ),
          },
          {
            key: "clubs",
            label: (
              <span>
                <TeamOutlined /> 竞赛社团（{clubs.length}）
              </span>
            ),
            children: clubs.length === 0 ? (
              <Empty description="暂无社团信息" />
            ) : (
              <Row gutter={[16, 16]}>
                {clubs.map((item) => (
                  <Col xs={24} sm={12} lg={8} key={item.slug}>
                    <ClubCard item={item} />
                  </Col>
                ))}
              </Row>
            ),
          },
        ]}
      />
    </Card>
  );
}
