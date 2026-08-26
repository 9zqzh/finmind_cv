import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Alert, Button, Card, Descriptions, Drawer, Empty, Input, List, message,
  Popconfirm, Select, Space, Spin, Table, Tabs, Tag, Typography,
} from "antd";
import {
  ArrowLeftOutlined, CheckOutlined, CloseOutlined, ReloadOutlined,
  DownloadOutlined, ThunderboltOutlined, UserAddOutlined,
} from "@ant-design/icons";
import { adminApi } from "../api/adminApi";
import { ApiBizError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type {
  AdminConversationDetail, AdminConversationList, AdminDraft, AdminEvolveResult,
  AdminGrantItem, AdminPlaybookList, AdminUserItem, AuditLogItem, PagedData,
} from "../api/types";

const PAGE_SIZE = 20;

function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiBizError ? error.message : fallback;
}

function time(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "—";
}

const EVENT_LABELS: Record<string, string> = {
  "auth.login": "用户登录",
  "auth.logout": "用户退出",
  "admin.grant": "添加管理员",
  "admin.revoke": "取消管理员",
  "admin.conversation.view": "查看对话",
  "admin.users.export": "导出用户数据",
  "playbook.evolve": "触发进化",
  "playbook.approve": "通过草稿",
  "playbook.reject": "拒绝草稿",
};

export default function AdminPage() {
  const { isSuperAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState("users");
  const [loading, setLoading] = useState(false);

  const [users, setUsers] = useState<PagedData<AdminUserItem> | null>(null);
  const [userPage, setUserPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [userQuery, setUserQuery] = useState("");
  const [exportingUsers, setExportingUsers] = useState(false);

  const [admins, setAdmins] = useState<AdminGrantItem[]>([]);
  const [newAdmin, setNewAdmin] = useState("");
  const [adminActing, setAdminActing] = useState(false);

  const [logs, setLogs] = useState<PagedData<AuditLogItem> | null>(null);
  const [logPage, setLogPage] = useState(1);
  const [logEvent, setLogEvent] = useState<string | undefined>();
  const [logStudent, setLogStudent] = useState("");

  const [conversationList, setConversationList] = useState<AdminConversationList | null>(null);
  const [conversationDetail, setConversationDetail] = useState<AdminConversationDetail | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const [drafts, setDrafts] = useState<AdminDraft[]>([]);
  const [playbooks, setPlaybooks] = useState<AdminPlaybookList | null>(null);
  const [actingId, setActingId] = useState<string | null>(null);
  const [evolving, setEvolving] = useState(false);
  const [evolveResult, setEvolveResult] = useState<AdminEvolveResult | null>(null);

  const loadUsers = useCallback(async (page = userPage, q = userQuery) => {
    setLoading(true);
    try { setUsers(await adminApi.users(page, PAGE_SIZE, q)); }
    catch (error) { message.error(errorMessage(error, "获取用户列表失败")); }
    finally { setLoading(false); }
  }, [userPage, userQuery]);

  const loadAdmins = useCallback(async () => {
    setLoading(true);
    try { setAdmins((await adminApi.admins()).items); }
    catch (error) { message.error(errorMessage(error, "获取管理员列表失败")); }
    finally { setLoading(false); }
  }, []);

  const loadLogs = useCallback(async (page = logPage) => {
    setLoading(true);
    try {
      setLogs(await adminApi.auditLogs({
        page, page_size: PAGE_SIZE,
        ...(logEvent ? { event_type: logEvent } : {}),
        ...(logStudent.trim() ? { student_number: logStudent.trim() } : {}),
      }));
    } catch (error) { message.error(errorMessage(error, "获取审计日志失败")); }
    finally { setLoading(false); }
  }, [logEvent, logPage, logStudent]);

  const loadPlaybooks = useCallback(async () => {
    setLoading(true);
    try {
      const [draftData, playbookData] = await Promise.all([adminApi.drafts(), adminApi.playbooks()]);
      setDrafts(draftData.drafts);
      setPlaybooks(playbookData);
    } catch (error) { message.error(errorMessage(error, "获取操作手册数据失败")); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadUsers(1, ""); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const selectTab = (key: string) => {
    setActiveTab(key);
    if (key === "users") loadUsers();
    else if (key === "admins") loadAdmins();
    else if (key === "logs") loadLogs();
    else if (["drafts", "playbooks", "evolve"].includes(key)) loadPlaybooks();
  };

  const openUser = async (user: AdminUserItem) => {
    setLoading(true);
    setConversationDetail(null);
    try {
      setConversationList(await adminApi.userConversations(user.id));
      setDrawerOpen(true);
    } catch (error) { message.error(errorMessage(error, "获取用户对话失败")); }
    finally { setLoading(false); }
  };

  const exportUsers = async () => {
    setExportingUsers(true);
    try {
      const response = await adminApi.exportUsers(userQuery);
      const disposition = response.headers["content-disposition"] as string | undefined;
      const filename = disposition?.match(/filename="?([^";]+)"?/)?.[1] ?? "users.csv";
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      message.success(`已导出 ${users?.total ?? 0} 条用户数据`);
    } catch (error) { message.error(errorMessage(error, "导出用户数据失败")); }
    finally { setExportingUsers(false); }
  };

  const openConversation = async (id: string) => {
    setLoading(true);
    try { setConversationDetail(await adminApi.conversation(id)); }
    catch (error) { message.error(errorMessage(error, "获取对话详情失败")); }
    finally { setLoading(false); }
  };

  const loadEarlierTurns = async () => {
    if (!conversationDetail?.turns.length) return;
    setLoading(true);
    try {
      const older = await adminApi.conversation(
        conversationDetail.conversation.id,
        conversationDetail.turns[0].position,
      );
      setConversationDetail({
        ...conversationDetail,
        turns: [...older.turns, ...conversationDetail.turns],
        has_more: older.has_more,
      });
    } catch (error) { message.error(errorMessage(error, "获取更早对话失败")); }
    finally { setLoading(false); }
  };

  const grantAdmin = async () => {
    if (!/^\d{4,64}$/.test(newAdmin.trim())) {
      message.warning("请输入 4 至 64 位数字学号"); return;
    }
    setAdminActing(true);
    try {
      await adminApi.grantAdmin(newAdmin.trim());
      setNewAdmin(""); message.success("管理员授权已添加"); await loadAdmins();
    } catch (error) { message.error(errorMessage(error, "添加管理员失败")); }
    finally { setAdminActing(false); }
  };

  const revokeAdmin = async (studentNumber: string) => {
    setAdminActing(true);
    try {
      await adminApi.revokeAdmin(studentNumber);
      message.success("管理员授权已取消"); await loadAdmins();
    } catch (error) { message.error(errorMessage(error, "取消管理员失败")); }
    finally { setAdminActing(false); }
  };

  const reviewDraft = async (draft: AdminDraft, approve: boolean) => {
    setActingId(draft.id);
    try {
      if (approve) await adminApi.approve(draft.id); else await adminApi.reject(draft.id);
      message.success(approve ? "草稿已通过并立即生效" : "草稿已拒绝删除");
      await loadPlaybooks();
    } catch (error) { message.error(errorMessage(error, "审核失败")); }
    finally { setActingId(null); }
  };

  const usersPanel = <Table
    rowKey="id" loading={loading} dataSource={users?.items ?? []}
    title={() => <Space wrap>
      <Input.Search placeholder="按学号搜索" value={searchInput} allowClear
        onChange={(e) => setSearchInput(e.target.value)}
        onSearch={(q) => { setUserQuery(q.trim()); setUserPage(1); loadUsers(1, q.trim()); }} />
      <Button icon={<ReloadOutlined />} onClick={() => loadUsers()}>刷新</Button>
      <Button icon={<DownloadOutlined />} loading={exportingUsers} onClick={exportUsers}>导出数据</Button>
    </Space>}
    pagination={{ current: userPage, pageSize: PAGE_SIZE, total: users?.total ?? 0,
      showSizeChanger: false, onChange: (page) => { setUserPage(page); loadUsers(page); } }}
    columns={[
      { title: "学号", dataIndex: "student_number" },
      { title: "最近登录", dataIndex: "last_login_at", render: time },
      { title: "最近活跃", dataIndex: "last_active_at", render: time },
      { title: "访问次数", dataIndex: "visit_count", width: 100 },
      { title: "会话状态", dataIndex: "has_active_session", render: (active: boolean) => active ? <Tag color="green">有效</Tag> : <Tag>离线</Tag> },
      { title: "对话数", dataIndex: "conversation_count", width: 90 },
      { title: "操作", render: (_: unknown, row: AdminUserItem) => <Button type="link" onClick={() => openUser(row)}>查看对话</Button> },
    ]}
  />;

  const adminsPanel = <Space direction="vertical" style={{ width: "100%" }} size="middle">
    {isSuperAdmin && <Card size="small" title="预授权管理员">
      <Space.Compact style={{ maxWidth: 440, width: "100%" }}>
        <Input value={newAdmin} onChange={(e) => setNewAdmin(e.target.value.trim())} placeholder="输入学号，可在首次登录前授权" />
        <Button type="primary" icon={<UserAddOutlined />} loading={adminActing} onClick={grantAdmin}>添加</Button>
      </Space.Compact>
    </Card>}
    {!isSuperAdmin && <Alert showIcon type="info" message="只有配置中的初始管理员可以增删管理员。" />}
    <Table rowKey="student_number" loading={loading} dataSource={admins} pagination={false} columns={[
      { title: "学号", dataIndex: "student_number" },
      { title: "角色", dataIndex: "is_super_admin", render: (superAdmin: boolean) => <Tag color={superAdmin ? "gold" : "blue"}>{superAdmin ? "初始管理员" : "管理员"}</Tag> },
      { title: "授权人", dataIndex: "granted_by_student_number", render: (v: string | null) => v ?? "配置文件" },
      { title: "授权时间", dataIndex: "created_at", render: time },
      ...(isSuperAdmin ? [{ title: "操作", render: (_: unknown, row: AdminGrantItem) => row.is_super_admin ? null : <Popconfirm title={`取消 ${row.student_number} 的管理员权限？`} onConfirm={() => revokeAdmin(row.student_number)}><Button danger type="link" loading={adminActing}>取消授权</Button></Popconfirm> }] : []),
    ]} />
  </Space>;

  const logsPanel = <Table
    rowKey="id" loading={loading} dataSource={logs?.items ?? []}
    title={() => <Space wrap>
      <Select allowClear placeholder="事件类型" style={{ width: 160 }} value={logEvent} onChange={setLogEvent}
        options={Object.entries(EVENT_LABELS).map(([value, label]) => ({ value, label }))} />
      <Input placeholder="操作者或目标学号" value={logStudent} onChange={(e) => setLogStudent(e.target.value)} style={{ width: 190 }} />
      <Button type="primary" onClick={() => { setLogPage(1); loadLogs(1); }}>筛选</Button>
    </Space>}
    expandable={{ expandedRowRender: (row) => <Descriptions size="small" column={1} bordered items={[
      { key: "ip", label: "IP", children: row.ip_address ?? "—" },
      { key: "ua", label: "User-Agent", children: row.user_agent ?? "—" },
      { key: "target", label: "目标", children: `${row.target_type ?? "—"} / ${row.target_id ?? "—"}` },
      { key: "details", label: "详情", children: <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{JSON.stringify(row.details, null, 2)}</pre> },
    ]} /> }}
    pagination={{ current: logPage, pageSize: PAGE_SIZE, total: logs?.total ?? 0,
      showSizeChanger: false, onChange: (page) => { setLogPage(page); loadLogs(page); } }}
    columns={[
      { title: "时间", dataIndex: "created_at", render: time },
      { title: "事件", dataIndex: "event_type", render: (v: string) => EVENT_LABELS[v] ?? v },
      { title: "结果", dataIndex: "success", render: (v: boolean) => <Tag color={v ? "green" : "red"}>{v ? "成功" : "失败"}</Tag> },
      { title: "操作者", dataIndex: "actor_student_number", render: (v: string | null) => v ?? "—" },
      { title: "目标学号", dataIndex: "target_student_number", render: (v: string | null) => v ?? "—" },
      { title: "错误码", dataIndex: "error_code", render: (v: string | null) => v ?? "—" },
    ]}
  />;

  const draftsPanel = <Spin spinning={loading}>{drafts.length ? <List dataSource={drafts} renderItem={(draft) => <List.Item><Card style={{ width: "100%" }} title={draft.title} extra={<Space>
    <Button type="primary" icon={<CheckOutlined />} loading={actingId === draft.id} onClick={() => reviewDraft(draft, true)}>通过</Button>
    <Popconfirm title="拒绝并删除该草稿？" onConfirm={() => reviewDraft(draft, false)}><Button danger icon={<CloseOutlined />} loading={actingId === draft.id}>拒绝</Button></Popconfirm>
  </Space>}><Space wrap>{draft.keywords.map((k) => <Tag key={k}>{k}</Tag>)}<Tag color="purple">提问簇 {draft.cluster_count}</Tag></Space>
  {draft.warnings && draft.warnings !== "无" && <Alert type="warning" message={draft.warnings} style={{ marginTop: 8 }} />}
  <pre style={{ whiteSpace: "pre-wrap", maxHeight: 320, overflow: "auto" }}>{draft.instructions}</pre></Card></List.Item>} /> : <Empty description="暂无待审草稿" />}</Spin>;

  const playbooksPanel = <Table rowKey="id" loading={loading} dataSource={playbooks?.entries ?? []} pagination={false}
    expandable={{ expandedRowRender: (row) => <pre style={{ whiteSpace: "pre-wrap" }}>{row.instructions}</pre> }} columns={[
      { title: "标题", dataIndex: "title" },
      { title: "来源", dataIndex: "source", render: (v: string) => <Tag color={v === "auto" ? "green" : "blue"}>{v === "auto" ? "自动生成" : "人工维护"}</Tag> },
      { title: "关键词", dataIndex: "keywords", render: (values: string[]) => <Space wrap>{values.map((v) => <Tag key={v}>{v}</Tag>)}</Space> },
      { title: "命中", render: (_: unknown, row) => playbooks?.hit_stats[row.id] ?? 0 },
    ]} />;

  const evolvePanel = <Space direction="vertical" size="middle">
    <Typography.Paragraph type="secondary">分析近期高频问题并生成待审操作手册草稿，过程可能持续数分钟。</Typography.Paragraph>
    <Button type="primary" size="large" icon={<ThunderboltOutlined />} loading={evolving} onClick={async () => {
      setEvolving(true); setEvolveResult(null);
      try { const result = await adminApi.evolve(); setEvolveResult(result); message.success("进化任务已完成"); await loadPlaybooks(); }
      catch (error) { message.error(errorMessage(error, "进化失败")); }
      finally { setEvolving(false); }
    }}>立即触发一次进化</Button>
    {evolveResult && <Alert type="success" showIcon message={`发现 ${evolveResult.clusters_found} 个问题簇，生成 ${evolveResult.drafts.filter((d) => d.id).length} 个草稿`} />}
  </Space>;

  return <div style={{ minHeight: "100vh", background: "#f0f2f5", padding: "24px 16px" }}>
    <div style={{ maxWidth: 1200, margin: "0 auto" }}>
      <Card style={{ marginBottom: 16 }}><Space style={{ width: "100%", justifyContent: "space-between" }} wrap>
        <Typography.Title level={4} style={{ margin: 0 }}>FinMind 管理后台</Typography.Title>
        <Link to="/"><Button icon={<ArrowLeftOutlined />}>返回助手</Button></Link>
      </Space></Card>
      <Card><Tabs activeKey={activeTab} onChange={selectTab} items={[
        { key: "users", label: "最近登录用户", children: usersPanel },
        { key: "admins", label: "管理员", children: adminsPanel },
        { key: "logs", label: "审计日志", children: logsPanel },
        { key: "drafts", label: `待审草稿（${drafts.length}）`, children: draftsPanel },
        { key: "playbooks", label: "手册列表", children: playbooksPanel },
        { key: "evolve", label: "触发进化", children: evolvePanel },
      ]} /></Card>
    </div>
    <Drawer width={760} open={drawerOpen} onClose={() => setDrawerOpen(false)} title={conversationDetail ? `对话详情：${conversationDetail.conversation.title}` : `用户 ${conversationList?.user.student_number ?? ""} 的对话`}>
      <Spin spinning={loading}>
        {conversationDetail ? <Space direction="vertical" style={{ width: "100%" }}>
          <Button onClick={() => setConversationDetail(null)}>返回对话列表</Button>
          {conversationDetail.has_more && <Button onClick={loadEarlierTurns}>加载更早轮次</Button>}
          {conversationDetail.turns.map((turn) => <Card key={turn.id} size="small" title={`第 ${turn.position} 轮 · ${time(turn.created_at)}`}>
            <Typography.Text strong>用户</Typography.Text><Typography.Paragraph style={{ whiteSpace: "pre-wrap" }}>{turn.user_message}</Typography.Paragraph>
            <Typography.Text strong>助手</Typography.Text><Typography.Paragraph style={{ whiteSpace: "pre-wrap" }}>{turn.response.answer}</Typography.Paragraph>
          </Card>)}
        </Space> : <List dataSource={conversationList?.items ?? []} locale={{ emptyText: "该用户暂无对话" }} renderItem={(item) => <List.Item actions={[<Button type="link" onClick={() => openConversation(item.id)}>查看详情</Button>]}><List.Item.Meta title={item.title} description={`创建：${time(item.created_at)}　更新：${time(item.updated_at)}`} /></List.Item>} />}
      </Spin>
    </Drawer>
  </div>;
}
