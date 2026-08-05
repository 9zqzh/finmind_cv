import { useEffect, useMemo, useState } from "react";
import { Button, Card, Input, message, Select, Space, Table, Typography } from "antd";
import { api, ApiBizError } from "../api/client";
import type { ClassroomEntry, ClassroomSchedule } from "../api/types";
import { useAuth } from "../context/AuthContext";
import { getDefaultTerm, getTermOptions } from "../utils/terms";

const WEEKDAY_NAMES = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"];

export default function ClassroomSchedulePage() {
  const { username } = useAuth();
  const termOptions = useMemo(() => getTermOptions(username), [username]);
  const [term, setTerm] = useState("");
  const [campus, setCampus] = useState("");
  const [building, setBuilding] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ClassroomSchedule | null>(null);

  useEffect(() => {
    if (!termOptions.some((option) => option.value === term)) {
      setTerm(getDefaultTerm(username));
    }
  }, [term, termOptions, username]);

  const query = async () => {
    if (!term.trim()) {
      message.warning("请填写学期");
      return;
    }
    setLoading(true);
    try {
      setResult(
        await api.classroomSchedule({
          term: term.trim(),
          campus: campus.trim() || undefined,
          building: building.trim() || undefined,
        }),
      );
    } catch (error) {
      const msg = error instanceof ApiBizError ? error.message : "查询失败";
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { title: "教室", dataIndex: "classroom", key: "classroom", width: 140 },
    {
      title: "星期",
      dataIndex: "weekday",
      key: "weekday",
      width: 80,
      render: (v: number) => WEEKDAY_NAMES[v] ?? v,
    },
    { title: "节次", dataIndex: "period", key: "period", width: 100 },
    { title: "课程", dataIndex: "course_name", key: "course_name" },
    {
      title: "教师",
      dataIndex: "teacher",
      key: "teacher",
      width: 100,
      render: (v: string | null) => v ?? "-",
    },
    {
      title: "周次",
      dataIndex: "weeks_text",
      key: "weeks_text",
      width: 130,
      render: (v: string | null) => v ?? "-",
    },
    {
      title: "班级",
      dataIndex: "class_name",
      key: "class_name",
      width: 160,
      render: (v: string | null) => v ?? "-",
    },
  ];

  return (
    <Card title="教室课表查询">
      <Space direction="vertical" style={{ width: "100%" }}>
        <Typography.Text type="secondary">
          按校区/教学楼查询某学期该教学楼内所有教室的上课安排（参数可留空查全部）。
        </Typography.Text>
        <Space wrap>
          <Select
            value={term}
            options={termOptions}
            onChange={setTerm}
            placeholder="选择学期"
            style={{ width: 180 }}
          />
          <Input
            value={campus}
            onChange={(e) => setCampus(e.target.value)}
            placeholder="校区（可留空）"
            style={{ width: 160 }}
          />
          <Input
            value={building}
            onChange={(e) => setBuilding(e.target.value)}
            placeholder="教学楼（可留空）"
            style={{ width: 160 }}
          />
          <Button type="primary" loading={loading} onClick={query}>
            查询
          </Button>
        </Space>
        {result && (
          <Table<ClassroomEntry>
            rowKey={(r, idx) => `${r.classroom}-${r.weekday}-${r.period}-${idx}`}
            columns={columns}
            dataSource={result.items}
            size="small"
            pagination={{ pageSize: 20 }}
            bordered
            scroll={{ x: 800 }}
          />
        )}
      </Space>
    </Card>
  );
}
