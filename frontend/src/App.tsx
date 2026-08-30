import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Button, Result, Spin } from "antd";
import { AuthProvider, useAuth } from "./context/AuthContext";
import AppLayout from "./layout/AppLayout";
import LoginPage from "./pages/LoginPage";
import ChatPage from "./pages/ChatPage";
import AcademicInfoPage from "./pages/AcademicInfoPage";
import KnowledgePage from "./pages/KnowledgePage";
import CompetitionPage from "./pages/CompetitionPage";
import InformationPage from "./pages/InformationPage";
import AdminPage from "./pages/AdminPage";
import { preloadCompetitionData } from "./stores/competitionStore";
import { preloadInformationData } from "./stores/informationStore";

function ProtectedLayout() {
  const { loggedIn, loading } = useAuth();
  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", paddingTop: 120 }}>
        <Spin size="large" tip="正在检查登录状态..." />
      </div>
    );
  }
  if (!loggedIn) {
    return <Navigate to="/login" replace />;
  }
  return <AppLayout />;
}

function ProtectedAdmin() {
  const { loggedIn, isAdmin, loading } = useAuth();
  if (loading) {
    return <div style={{ display: "flex", justifyContent: "center", paddingTop: 120 }}><Spin /></div>;
  }
  if (!loggedIn) return <Navigate to="/login" replace />;
  if (!isAdmin) {
    return <Result status="403" title="无管理权限" subTitle="当前学号未被授权为管理员。" extra={<Button href="/">返回助手</Button>} />;
  }
  return <AdminPage />;
}

export default function App() {
  useEffect(() => {
    preloadCompetitionData();
    preloadInformationData();
  }, []);

  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/admin" element={<ProtectedAdmin />} />
          <Route element={<ProtectedLayout />}>
            <Route path="/" element={<ChatPage />} />
            <Route path="/academic-info" element={<AcademicInfoPage />} />
            <Route path="/schedule" element={<Navigate to="/academic-info#schedule" replace />} />
            <Route path="/grades" element={<Navigate to="/academic-info#grades" replace />} />
            <Route path="/training-plan" element={<Navigate to="/academic-info#training-plan" replace />} />
            <Route path="/classroom-schedule" element={<Navigate to="/academic-info#classroom-schedule" replace />} />
            <Route path="/knowledge" element={<KnowledgePage />} />
            <Route path="/information" element={<InformationPage />} />
            <Route path="/competition" element={<CompetitionPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
