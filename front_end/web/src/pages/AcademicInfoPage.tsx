import { useEffect, useMemo, useState } from "react";
import { Card, Tabs } from "antd";
import {
  BookOutlined,
  CalendarOutlined,
  ReadOutlined,
  ScheduleOutlined,
} from "@ant-design/icons";
import { useLocation } from "react-router-dom";
import { ClassroomScheduleContent } from "./ClassroomSchedulePage";
import { GradesContent } from "./GradesPage";
import { ScheduleContent } from "./SchedulePage";
import { TrainingPlanContent } from "./TrainingPlanPage";

const sections = [
  { key: "schedule", label: "我的课表", icon: <CalendarOutlined />, content: <ScheduleContent /> },
  { key: "grades", label: "成绩查询", icon: <ScheduleOutlined />, content: <GradesContent /> },
  { key: "training-plan", label: "培养方案", icon: <ReadOutlined />, content: <TrainingPlanContent /> },
  { key: "classroom-schedule", label: "教室课表", icon: <BookOutlined />, content: <ClassroomScheduleContent /> },
];

export default function AcademicInfoPage() {
  const location = useLocation();
  const initialKey = location.hash.replace("#", "");
  const [activeKey, setActiveKey] = useState(
    sections.some((section) => section.key === initialKey) ? initialKey : "schedule",
  );

  useEffect(() => {
    const key = location.hash.replace("#", "");
    if (sections.some((section) => section.key === key)) {
      setActiveKey(key);
    }
  }, [location.hash]);

  const items = useMemo(
    () =>
      sections.map((section) => ({
        key: section.key,
        label: (
          <span>
            {section.icon} {section.label}
          </span>
        ),
        children: section.content,
      })),
    [],
  );

  return (
    <Card title="教务信息">
      <Tabs
        activeKey={activeKey}
        onChange={setActiveKey}
        items={items}
      />
    </Card>
  );
}
