import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Card, Empty, message, Select, Space, Table, Typography } from "antd";
import { api, ApiBizError } from "../api/client";
import type { ClassroomEntry, ClassroomSchedule } from "../api/types";
import { useAuth } from "../context/AuthContext";
import { getDefaultTerm, getTermOptions } from "../utils/terms";

const WEEKDAY_NAMES = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"];

function MobileClassroomTable({ result }: { result: ClassroomSchedule }) {
  if (result.items.length === 0) {
    return <Empty className="mobile-only" description="当前条件下未查询到占用课程" />;
  }

  return (
    <Table<ClassroomEntry>
      className="mobile-grade-table mobile-classroom-table"
      rowKey={(r, idx) => `${r.classroom}-${r.weekday}-${r.period}-${idx}`}
      dataSource={result.items}
      size="small"
      pagination={false}
      bordered
      columns={[
        { title: "星期", dataIndex: "weekday", width: 36, align: "center", render: (v: number) => WEEKDAY_NAMES[v] ?? v },
        { title: "节次", dataIndex: "period", width: 48, align: "center" },
        { title: "课程", dataIndex: "course_name" },
        { title: "班级", dataIndex: "class_name", width: 128, align: "center", render: (v: string | null) => v ?? "-" },
      ]}
    />
  );
}

export function ClassroomScheduleContent() {
  const { username } = useAuth();
  const termOptions = useMemo(() => getTermOptions(username), [username]);
  const [term, setTerm] = useState("");
  const [campus, setCampus] = useState("");
  const [building, setBuilding] = useState("");
  const [buildingOptions, setBuildingOptions] = useState<{ label: string; value: string }[]>([]);
  const [buildingsLoading, setBuildingsLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ClassroomSchedule | null>(null);

  useEffect(() => {
    if (!termOptions.some((option) => option.value === term)) {
      setTerm(getDefaultTerm(username));
    }
  }, [term, termOptions, username]);

  const QY_KEEP = new Set(["清远北教", "清远南教", "清远敏学楼（实验楼）", "笃行楼（清远））"]);

  const fetchBuildings = useCallback(async (campusCode: string) => {
    if (!campusCode) {
      setBuildingOptions([]);
      setBuilding("");
      return;
    }
    setBuildingsLoading(true);
    try {
      const options = await api.classroomBuildings(campusCode);
      const filtered = campusCode === "r0"
        ? options.filter((o) => QY_KEEP.has(o.label))
        : options;
      setBuildingOptions(filtered);
      setBuilding("");
    } catch {
      setBuildingOptions([]);
    } finally {
      setBuildingsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBuildings(campus);
  }, [campus, fetchBuildings]);

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
    <>
      <Typography.Text type="secondary">
        按校区/教学楼查询某学期该教学楼内所有教室的上课安排（参数可留空查全部）。
      </Typography.Text>
      <Space className="query-toolbar" wrap>
        <Select
          value={term}
          options={termOptions}
          onChange={setTerm}
          placeholder="选择学期"
          className="query-toolbar__control"
          style={{ width: 180 }}
        />
        <Select
          value={campus || undefined}
          onChange={setCampus}
          placeholder="选择校区"
          allowClear
          className="query-toolbar__control"
          style={{ width: 160 }}
          options={[
            { label: "广州校区", value: "1" },
            { label: "肇庆校区", value: "2" },
            { label: "清远校区", value: "r0" },
          ]}
        />
        <Select
          value={building}
          onChange={setBuilding}
          placeholder="选择教学楼"
          allowClear
          loading={buildingsLoading}
          disabled={!campus}
          className="query-toolbar__control"
          style={{ width: 160 }}
          options={buildingOptions}
        />
        <Button type="primary" loading={loading} onClick={query}>
          查询
        </Button>
      </Space>
      {result && (
        <>
          <Table<ClassroomEntry>
            className="desktop-table"
            rowKey={(r, idx) => `${r.classroom}-${r.weekday}-${r.period}-${idx}`}
            columns={columns}
            dataSource={result.items}
            size="small"
            pagination={{ pageSize: 20 }}
            bordered
            scroll={{ x: 800 }}
          />
          <MobileClassroomTable result={result} />
        </>
      )}
    </>
  );
}

export default function ClassroomSchedulePage() {
  return (
    <Card title="教室课表查询">
      <ClassroomScheduleContent />
    </Card>
  );
}
