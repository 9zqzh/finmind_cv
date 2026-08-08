import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Spin } from "antd";
import { AuthProvider, useAuth } from "./context/AuthContext";
import AppLayout from "./layout/AppLayout";
import LoginPage from "./pages/LoginPage";
import ChatPage from "./pages/ChatPage";
import SchedulePage from "./pages/SchedulePage";
import GradesPage from "./pages/GradesPage";
import TrainingPlanPage from "./pages/TrainingPlanPage";
import ClassroomSchedulePage from "./pages/ClassroomSchedulePage";
import KnowledgePage from "./pages/KnowledgePage";
import CompetitionPage from "./pages/CompetitionPage";
import InformationPage from "./pages/InformationPage";

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

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedLayout />}>
            <Route path="/" element={<ChatPage />} />
            <Route path="/schedule" element={<SchedulePage />} />
            <Route path="/grades" element={<GradesPage />} />
            <Route path="/training-plan" element={<TrainingPlanPage />} />
            <Route path="/classroom-schedule" element={<ClassroomSchedulePage />} />
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
