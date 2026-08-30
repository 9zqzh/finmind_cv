import { useState } from "react";
import { useLocation, useNavigate, Outlet } from "react-router-dom";
import { Button, Drawer, Layout, Menu, Space, Tag, Typography } from "antd";
import {
  BookOutlined,
  DatabaseOutlined,
  HomeOutlined,
  LogoutOutlined,
  MenuOutlined,
  NotificationOutlined,
  TrophyOutlined,
} from "@ant-design/icons";
import { useAuth } from "../context/AuthContext";
import { useIsMobile } from "../hooks/useIsMobile";
import logo from "../assets/logo.jpg";
import packageJson from "../../package.json";

const { Header, Sider, Content } = Layout;
const appVersion = `v${packageJson.version}`;

const menuItems = [
  { key: "/", icon: <HomeOutlined />, label: "AI 对话" },
  { key: "/academic-info", icon: <BookOutlined />, label: "教务信息" },
  { key: "/knowledge", icon: <DatabaseOutlined />, label: "知识库" },
  { key: "/information", icon: <NotificationOutlined />, label: "学院资讯" },
  { key: "/competition", icon: <TrophyOutlined />, label: "竞赛信息" },
];

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { username, logout } = useAuth();
  const isMobile = useIsMobile();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    setDrawerOpen(false);
    navigate("/login");
  };

  const handleNavigate = (key: string) => {
    navigate(key);
    setDrawerOpen(false);
  };

  const navigationMenu = (
    <Menu
      mode="inline"
      selectedKeys={[location.pathname]}
      items={menuItems}
      style={{ flex: 1, borderRight: 0 }}
      onClick={({ key }) => handleNavigate(key)}
    />
  );

  const versionLabel = (
    <Typography.Text
      type="secondary"
      style={{ display: "block", fontSize: 12, textAlign: "center" }}
    >
      当前版本 {appVersion}
    </Typography.Text>
  );

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Header
        className="app-header"
        style={{
          position: "relative",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "#ffffff",
          padding: "0 24px",
          borderBottom: "1px solid #e6eef8",
        }}
      >
        <div
          style={
            isMobile
              ? { flex: "0 0 44px", display: "flex", alignItems: "center" }
              : undefined
          }
        >
          {isMobile && (
            <Button
              type="text"
              icon={<MenuOutlined />}
              onClick={() => setDrawerOpen(true)}
              aria-label="打开导航菜单"
            />
          )}
        </div>
        <Space
          size={isMobile ? 8 : 12}
          className="app-header__brand"
          style={{
            flex: 1,
            justifyContent: isMobile ? "center" : "flex-start",
            minWidth: 0,
          }}
        >
          <img
            src={logo}
            alt="数智金院 FinMind Logo"
            className="app-header__logo"
            style={{
              width: 50,
              height: 50,
              objectFit: "contain",
              borderRadius: 20,
              transform: "translateY(12px)",
            }}
          />
          <Typography.Title
            level={4}
            className="app-header__title"
            style={{
              color: "transparent",
              margin: 0,
              background:
                "linear-gradient(120deg, #1e3a8a 0%, #3f5be0 35%, #5b6ee8 70%, #2a7fe0 100%)",
              WebkitBackgroundClip: "text",
              backgroundClip: "text",
              fontWeight: 700,
              letterSpacing: 2,
              filter: "drop-shadow(0 2px 6px rgba(79, 70, 229, 0.25))",
            }}
          >
            数智金院 FinMind
          </Typography.Title>
        </Space>
        {isMobile ? (
          <div style={{ flex: "0 0 44px" }} />
        ) : (
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
        )}
      </Header>
      <Drawer
        placement="left"
        width={isMobile ? "60%" : 280}
        closable={false}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        styles={{ body: { padding: 0, display: "flex", flexDirection: "column" } }}
      >
        <div
          style={{
            padding: "14px 16px",
            fontWeight: 700,
            fontSize: 15,
            letterSpacing: 1,
            color: "#1e3a8a",
            borderBottom: "1px solid #e6eef8",
            flexShrink: 0,
          }}
        >
          数智金院 FinMind
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          {navigationMenu}
        </div>
        <div
          style={{
            padding: 16,
            borderTop: "1px solid #e6eef8",
            background: "#ffffff",
          }}
        >
          <Space direction="vertical" style={{ width: "100%" }}>
            <Tag color="blue" style={{ width: "fit-content" }}>
              {username ?? "未登录"}
            </Tag>
            <Button block icon={<LogoutOutlined />} onClick={handleLogout}>
              退出登录
            </Button>
            {versionLabel}
          </Space>
        </div>
      </Drawer>
      <Layout>
        {!isMobile && (
          <Sider
            width={200}
            theme="light"
            style={{ borderRight: "1px solid #e6eef8" }}
          >
            <div
              style={{
                height: "100%",
                display: "flex",
                flexDirection: "column",
              }}
            >
              {navigationMenu}
              <div
                style={{
                  flexShrink: 0,
                  padding: "12px 16px",
                  borderTop: "1px solid #e6eef8",
                }}
              >
                {versionLabel}
              </div>
            </div>
          </Sider>
        )}
        <Content
          className="app-content"
          style={{
            padding: isMobile ? 12 : 24,
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
