import { useLocation, useNavigate, Outlet } from "react-router-dom";
import { Button, Layout, Menu, Space, Tag, Typography } from "antd";
import {
  BookOutlined,
  CalendarOutlined,
  DatabaseOutlined,
  HomeOutlined,
  LogoutOutlined,
  NotificationOutlined,
  ReadOutlined,
  ScheduleOutlined,
} from "@ant-design/icons";
import { useAuth } from "../context/AuthContext";
import logo from "../assets/logo.jpg";

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: "/", icon: <HomeOutlined />, label: "AI 对话" },
  { key: "/schedule", icon: <CalendarOutlined />, label: "我的课表" },
  { key: "/grades", icon: <ScheduleOutlined />, label: "成绩查询" },
  { key: "/training-plan", icon: <ReadOutlined />, label: "培养方案" },
  { key: "/classroom-schedule", icon: <BookOutlined />, label: "教室课表" },
  { key: "/knowledge", icon: <DatabaseOutlined />, label: "知识库" },
  { key: "/information", icon: <NotificationOutlined />, label: "学院资讯" },
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
          background: "#ffffff",
          padding: "0 24px",
          borderBottom: "1px solid #e6eef8",
        }}
      >
        <Space size={12}>
          <img
            src={logo}
            alt="学院教学小助手 Logo"
            style={{
              width: 50,
              height: 50,
              objectFit: "contain",
              borderRadius: 20,
              transform: "translateY(12px)",
            }}
          />
          <Typography.Title level={4} style={{ color: "#101828", margin: 0 }}>
            学院教学小助手
          </Typography.Title>
        </Space>
        <Space>
          <Tag color="blue">{username ?? "未登录"}</Tag>
          <Button
            type="text"
            style={{ color: "#1d2939" }}
            icon={<LogoutOutlined />}
            onClick={handleLogout}
          >
            退出登录
          </Button>
        </Space>
      </Header>
      <Layout>
        <Sider
          width={200}
          theme="light"
          style={{ borderRight: "1px solid #e6eef8" }}
        >
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            items={menuItems}
            style={{ height: "100%", borderRight: 0 }}
            onClick={({ key }) => navigate(key)}
          />
        </Sider>
        <Content
          style={{
            padding: 24,
            overflow: "auto",
            background: "#f5f9ff",
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
