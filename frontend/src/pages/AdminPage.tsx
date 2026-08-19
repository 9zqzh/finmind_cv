import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Empty,
  Input,
  List,
  message,
  Popconfirm,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd";
import {
  ArrowLeftOutlined,
  CheckOutlined,
  CloseOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { AdminApiError, adminApi, getAdminToken, setAdminToken } from "../api/adminApi";
import type { AdminDraft, AdminEvolveResult, AdminPlaybookList } from "../api/types";

/** 统一错误文案；令牌无效时给出明确提示。 */
function errMsg(error: unknown, fallback: string): string {
  if (error instanceof AdminApiError) {
    if (error.code === "AUTH_REQUIRED") {
      return "管理员令牌无效，请核对页面顶部填写的令牌与服务器 ADMIN_TOKEN";
    }
    return error.message;
  }
  return fallback;
}

const SOURCE_TAG: Record<string, { label: string; color: string }> = {
  manual: { label: "人工维护", color: "blue" },
  auto: { label: "自动生成", color: "green" },
};

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState("drafts");
  const [drafts, setDrafts] = useState<AdminDraft[]>([]);
  const [draftsLoading, setDraftsLoading] = useState(false);
  const [playbooks, setPlaybooks] = useState<AdminPlaybookList | null>(null);
  const [playbooksLoading, setPlaybooksLoading] = useState(false);
  const [evolving, setEvolving] = useState(false);
  const [evolveResult, setEvolveResult] = useState<AdminEvolveResult | null>(null);
  const [actingId, setActingId] = useState<string | null>(null);

  const loadDrafts = useCallback(async () => {
    setDraftsLoading(true);
    try {
      const data = await adminApi.drafts();
      setDrafts(data.drafts);
    } catch (error) {
      message.error(errMsg(error, "获取草稿列表失败"));
    } finally {
      setDraftsLoading(false);
    }
  }, []);

  const loadPlaybooks = useCallback(async () => {
    setPlaybooksLoading(true);
    try {
      setPlaybooks(await adminApi.playbooks());
    } catch (error) {
      message.error(errMsg(error, "获取手册列表失败"));
    } finally {
      setPlaybooksLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDrafts();
    loadPlaybooks();
  }, [loadDrafts, loadPlaybooks]);

  const handleApprove = async (draft: AdminDraft) => {
    setActingId(draft.id);
    try {
      await adminApi.approve(draft.id);
      message.success(`《${draft.title}》已审核通过，立即对用户对话生效`);
      loadDrafts();
      loadPlaybooks();
    } catch (error) {
      message.error(errMsg(error, "审核失败"));
    } finally {
      setActingId(null);
    }
  };

  const handleReject = async (draft: AdminDraft) => {
    setActingId(draft.id);
    try {
      await adminApi.reject(draft.id);
      message.success(`《${draft.title}》已拒绝并删除`);
      loadDrafts();
    } catch (error) {
      message.error(errMsg(error, "审核失败"));
    } finally {
      setActingId(null);
    }
  };

  const handleEvolve = async () => {
    setEvolving(true);
    setEvolveResult(null);
    try {
      const result = await adminApi.evolve();
      setEvolveResult(result);
      message.success(`进化完成：发现 ${result.clusters_found} 个高频问题簇`);
      loadDrafts();
    } catch (error) {
      message.error(errMsg(error, "进化失败"));
    } finally {
      setEvolving(false);
    }
  };

  const draftsPanel = (
    <Spin spinning={draftsLoading}>
      {drafts.length === 0 && !draftsLoading ? (
        <Empty description="暂无待审草稿。可在“触发进化”页签手动跑一次进化流水线。" />
      ) : (
        <List
          grid={{ gutter: 16, column: 1 }}
          dataSource={drafts}
          renderItem={(draft) => (
            <List.Item>
              <Card
                title={draft.title}
                extra={
                  <Space>
                    <Button
                      type="primary"
                      icon={<CheckOutlined />}
                      loading={actingId === draft.id}
                      onClick={() => handleApprove(draft)}
                    >
                      通过
                    </Button>
                    <Popconfirm
                      title="拒绝该草稿？"
                      description="草稿将被删除，同簇问题冷却期内不会重复生成。"
                      onConfirm={() => handleReject(draft)}
                      okText="拒绝"
                      cancelText="取消"
                      okButtonProps={{ danger: true }}
                    >
                      <Button danger icon={<CloseOutlined />} loading={actingId === draft.id}>
                        拒绝
                      </Button>
                    </Popconfirm>
                  </Space>
                }
              >
                <Space wrap style={{ marginBottom: 8 }}>
                  <Tag color="purple">提问簇大小 {draft.cluster_count}</Tag>
                  {draft.keywords.map((k) => (
                    <Tag key={k}>{k}</Tag>
                  ))}
                </Space>
                {draft.warnings && draft.warnings !== "无" && (
                  <Alert
                    type="warning"
                    showIcon
                    message={`校验警告：${draft.warnings}`}
                    style={{ marginBottom: 8 }}
                  />
                )}
                <pre
                  style={{
                    background: "#f6f8fa",
                    borderRadius: 6,
                    padding: 12,
                    maxHeight: 320,
                    overflow: "auto",
                    whiteSpace: "pre-wrap",
                    fontSize: 13,
                    margin: 0,
                  }}
                >
                  {draft.instructions}
                </pre>
              </Card>
            </List.Item>
          )}
        />
      )}
    </Spin>
  );

  const playbooksPanel = (
    <Spin spinning={playbooksLoading}>
      <Table
        rowKey="id"
        dataSource={playbooks?.entries ?? []}
        pagination={false}
        expandable={{
          expandedRowRender: (entry) => (
            <pre
              style={{
                background: "#f6f8fa",
                borderRadius: 6,
                padding: 12,
                whiteSpace: "pre-wrap",
                fontSize: 13,
                margin: 0,
              }}
            >
              {entry.instructions}
            </pre>
          ),
        }}
        columns={[
          { title: "手册标题", dataIndex: "title", key: "title" },
          {
            title: "来源",
            dataIndex: "source",
            key: "source",
            width: 110,
            render: (source: string) => {
              const tag = SOURCE_TAG[source] ?? { label: source, color: "default" };
              return <Tag color={tag.color}>{tag.label}</Tag>;
            },
          },
          {
            title: "触发关键词",
            dataIndex: "keywords",
            key: "keywords",
            render: (keywords: string[]) => (
              <Space wrap size={[4, 4]}>
                {keywords.map((k) => (
                  <Tag key={k}>{k}</Tag>
                ))}
              </Space>
            ),
          },
          {
            title: "命中次数",
            key: "hits",
            width: 100,
            render: (_, entry) => playbooks?.hit_stats[entry.id] ?? 0,
          },
        ]}
      />
    </Spin>
  );

  const evolvePanel = (
    <div>
      <Typography.Paragraph type="secondary">
        立即分析最近窗口期（默认 7 天）内的高频提问，为达标问题簇生成待审手册草稿。
        整个过程需要调用大模型，可能耗时数分钟，请勿重复点击。
      </Typography.Paragraph>
      <Button
        type="primary"
        size="large"
        icon={<ThunderboltOutlined />}
        loading={evolving}
        onClick={handleEvolve}
      >
        {evolving ? "进化进行中，请耐心等待…" : "立即触发一次进化"}
      </Button>
      {evolveResult && (
        <Card style={{ marginTop: 16 }} title={`本次发现 ${evolveResult.clusters_found} 个高频问题簇`}>
          {evolveResult.drafts.length === 0 ? (
            <Typography.Text type="secondary">
              没有产生新草稿：可能近期提问均已被现有手册覆盖，或处于冷却期。
            </Typography.Text>
          ) : (
            <List
              dataSource={evolveResult.drafts}
              renderItem={(item) => (
                <List.Item>
                  {item.id ? (
                    <Space>
                      <CheckOutlined style={{ color: "#52c41a" }} />
                      <span>《{item.title}》草稿已生成</span>
                      {item.warnings && item.warnings.length > 0 && (
                        <Tag color="warning">警告：{item.warnings.join("；")}</Tag>
                      )}
                    </Space>
                  ) : (
                    <Space>
                      <CloseOutlined style={{ color: "#ff4d4f" }} />
                      <span>「{item.title}」生成失败：{item.error}</span>
                    </Space>
                  )}
                </List.Item>
              )}
            />
          )}
          <Button
            style={{ marginTop: 12 }}
            icon={<ReloadOutlined />}
            onClick={() => {
              setActiveTab("drafts");
              loadDrafts();
            }}
          >
            前往审核草稿
          </Button>
        </Card>
      )}
    </div>
  );

  return (
    <div style={{ minHeight: "100vh", background: "#f0f2f5", padding: "24px 16px" }}>
      <div style={{ maxWidth: 960, margin: "0 auto" }}>
        <Card style={{ marginBottom: 16 }}>
          <Space direction="vertical" style={{ width: "100%" }} size="middle">
            <Space style={{ width: "100%", justifyContent: "space-between" }} wrap>
              <Typography.Title level={4} style={{ margin: 0 }}>
                操作手册管理台
              </Typography.Title>
              <Link to="/">
                <Button icon={<ArrowLeftOutlined />}>返回助手</Button>
              </Link>
            </Space>
            <Input.Password
              placeholder="管理员令牌（对应服务器 .env 的 ADMIN_TOKEN）"
              defaultValue={getAdminToken()}
              onChange={(e) => setAdminToken(e.target.value.trim())}
              autoComplete="off"
              style={{ maxWidth: 480 }}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              令牌仅保存在当前浏览器标签页会话中；留空时仅当服务端未配置 ADMIN_TOKEN 才能访问。
            </Typography.Text>
          </Space>
        </Card>
        <Card>
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={[
              {
                key: "drafts",
                label: `待审草稿（${drafts.length}）`,
                children: draftsPanel,
              },
              { key: "playbooks", label: "手册列表", children: playbooksPanel },
              { key: "evolve", label: "触发进化", children: evolvePanel },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
