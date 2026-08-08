import { useEffect, useState } from "react";
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
import { api } from "../api/client";

const COMPETITION_API = "/api/competitions/list";
const NOTICES_API = "/api/competitions/notices";
const CLUBS_API = "/api/competitions/clubs";

// ---- 类型定义 ----
interface CompetitionItem {
  id: string;
  title: string;
  url: string;
  category: string;
  year: number | null;
  recognition: string;
  status: string;
  department: string;
  registration_mode: string;
  max_team_size: number | null;
  max_advisors: number | null;
  registration_start_at: string | null;
  registration_end_at: string | null;
  event_start_at: string | null;
  event_end_at: string | null;
  official_url: string | null;
  wechat_article_url: string | null;
  cta_type: string;
  cta_label: string | null;
  summary: string;
}

interface NoticeItem {
  id: string;
  title: string;
  content: string;
  priority: string;
  published_at: string;
  competition_title: string | null;
  competition_id: string | null;
}

interface ClubItem {
  slug: string;
  name: string;
  short_name: string;
  slogan: string;
  cover_image: string | null;
  theme_color: string | null;
  focus_areas: string[];
  url: string;
}

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

  return (
    <>
      <Card
        hoverable
        size="small"
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

          {item.summary && (
            <Typography.Paragraph
              style={{ fontSize: 12, margin: 0, color: "#667085" }}
              ellipsis={{ rows: 3 }}
            >
              {item.summary}
            </Typography.Paragraph>
          )}
        </Space>
      </Card>

      <Modal
        title={item.title}
        open={open}
        onCancel={() => setOpen(false)}
        footer={null}
        width={700}
        style={{ top: 40 }}
      >
        <div style={{ maxHeight: "65vh", overflowY: "auto", paddingRight: 8 }}>
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
              <Typography.Text>
                <LinkOutlined style={{ marginRight: 6 }} />
                官网：<a href={item.official_url} target="_blank" rel="noopener noreferrer">{item.official_url}</a>
              </Typography.Text>
            )}

            {item.wechat_article_url && (
              <Typography.Text>
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
        <Space>
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
  const [items, setItems] = useState<CompetitionItem[]>([]);
  const [notices, setNotices] = useState<NoticeItem[]>([]);
  const [clubs, setClubs] = useState<ClubItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const [compRes, noticeRes, clubRes] = await Promise.all([
          api.getExternal(COMPETITION_API),
          api.getExternal(NOTICES_API),
          api.getExternal(CLUBS_API),
        ]);

        const mapped: CompetitionItem[] = ((compRes as any).competitions ?? []).map(
          (item: Record<string, unknown>) => ({
            id: String(item.id ?? ""),
            title: String(item.title ?? ""),
            url: `https://ai-data-competitions.cn/competitions/${item.id}`,
            category: String(item.category ?? ""),
            year: (item.competitionYear as number) ?? null,
            recognition: String(item.recognition ?? ""),
            status: String(item.status ?? ""),
            department: String(item.department ?? ""),
            registration_mode: String(item.registrationMode ?? ""),
            max_team_size: (item.maxTeamSize as number) ?? null,
            max_advisors: (item.maxAdvisors as number) ?? null,
            registration_start_at: (item.registrationStartAt as string) ?? null,
            registration_end_at: (item.registrationEndAt as string) ?? null,
            event_start_at: (item.eventStartAt as string) ?? null,
            event_end_at: (item.eventEndAt as string) ?? null,
            official_url: (item.officialUrl as string) ?? null,
            wechat_article_url: (item.wechatArticleUrl as string) ?? null,
            cta_type: String(item.ctaType ?? ""),
            cta_label: (item.ctaLabelOverride as string) ?? null,
            summary: String(item.summary ?? ""),
          })
        );
        setItems(mapped);

        const mappedNotices: NoticeItem[] = ((noticeRes as any).notices ?? []).map(
          (item: Record<string, unknown>) => ({
            id: String(item.id ?? ""),
            title: String(item.title ?? ""),
            content: String(item.content ?? ""),
            priority: String(item.priority ?? "normal"),
            published_at: (item.publishedAt as string) ?? "",
            competition_title: (item.competitionTitle as string) ?? null,
            competition_id: (item.competitionId as string) ?? null,
          })
        );
        setNotices(mappedNotices);

        const mappedClubs: ClubItem[] = ((clubRes as any).data ?? []).map(
          (item: Record<string, unknown>) => ({
            slug: String(item.slug ?? ""),
            name: String(item.name ?? ""),
            short_name: String(item.shortName ?? ""),
            slogan: String(item.slogan ?? ""),
            cover_image: (item.coverImage as string) ?? null,
            theme_color: (item.themeColor as string) ?? null,
            focus_areas: (item.focusAreas as string[]) ?? [],
            url: `https://ai-data-competitions.cn/clubs/${item.slug}`,
          })
        );
        setClubs(mappedClubs);
      } catch {
        setItems([]);
        setNotices([]);
        setClubs([]);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

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
                  <Col xs={24} sm={12} lg={8} xl={6} key={item.id}>
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