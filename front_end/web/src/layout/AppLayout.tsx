import { useLocation, useNavigate, Outlet } from "react-router-dom";
import { Button, Layout, Menu, Space, Tag, Typography } from "antd";
import {
  BookOutlined,
  CalendarOutlined,
  HomeOutlined,
  LogoutOutlined,
  ReadOutlined,
  ScheduleOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { useAuth } from "../context/AuthContext";

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: "/", icon: <HomeOutlined />, label: "AI 对话" },
  { key: "/schedule", icon: <CalendarOutlined />, label: "我的课表" },
  { key: "/grades", icon: <ScheduleOutlined />, label: "成绩查询" },
  { key: "/training-plan", icon: <ReadOutlined />, label: "培养方案" },
  { key: "/classroom-schedule", icon: <BookOutlined />, label: "教室课表" },
  { key: "/knowledge", icon: <SearchOutlined />, label: "知识与资讯" },
];

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { username, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "#001529",
          padding: "0 24px",
        }}
      >
        <Typography.Title level={4} style={{ color: "#fff", margin: 0 }}>
          🎓 学院教学小助手
        </Typography.Title>
        <Space>
          <Tag color="blue">{username ?? "未登录"}</Tag>
          <Button
            type="text"
            style={{ color: "#fff" }}
            icon={<LogoutOutlined />}
            onClick={handleLogout}
          >
            退出登录
          </Button>
        </Space>
      </Header>
      <Layout>
        <Sider width={200} theme="light">
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            items={menuItems}
            style={{ height: "100%", borderRight: 0 }}
            onClick={({ key }) => navigate(key)}
          />
        </Sider>
        <Content style={{ padding: 24, overflow: "auto" }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
