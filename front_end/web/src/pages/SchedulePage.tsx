import { useState } from "react";
import { Button, Card, Input, InputNumber, message, Space, Table, Typography } from "antd";
import { api, ApiBizError } from "../api/client";
import type { Schedule } from "../api/types";

const WEEKDAY_NAMES = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"];

export default function SchedulePage() {
  const [term, setTerm] = useState("2025-2026-2");
  const [week, setWeek] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [schedule, setSchedule] = useState<Schedule | null>(null);

  const query = async () => {
    setLoading(true);
    try {
      setSchedule(await api.schedule(term, week ?? undefined));
    } catch (error) {
      const msg = error instanceof ApiBizError ? error.message : "查询失败";
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="我的课表">
      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          placeholder="学期，如 2025-2026-2"
          style={{ width: 180 }}
        />
        <InputNumber
          value={week}
          onChange={(v) => setWeek(v)}
          min={1}
          max={30}
          placeholder="周次（可选）"
        />
        <Button type="primary" onClick={query} loading={loading}>
          查询
        </Button>
      </Space>
      {schedule && (
        <>
          <Typography.Paragraph type="secondary">
            学期：{schedule.term}
            {schedule.week ? ` · 第 ${schedule.week} 周` : " · 整学期"}
            {schedule.remarks ? ` · ${schedule.remarks}` : ""}
          </Typography.Paragraph>
          <Table
            size="small"
            rowKey={(row) => `${row.course_name}-${row.weekday}-${row.period}`}
            dataSource={[...schedule.items].sort(
              (a, b) => a.weekday - b.weekday || a.period - b.period,
            )}
            pagination={false}
            columns={[
              {
                title: "星期",
                dataIndex: "weekday",
                width: 70,
                render: (v: number) => WEEKDAY_NAMES[v] ?? v,
              },
              { title: "节次", dataIndex: "period_name", width: 120 },
              { title: "课程", dataIndex: "course_name" },
              { title: "教室", dataIndex: "classroom", width: 140 },
              { title: "教师", dataIndex: "teacher", width: 100 },
              { title: "周次", dataIndex: "weeks_text", width: 120 },
            ]}
          />
        </>
      )}
    </Card>
  );
}
