import { useState } from "react";
import { Button, Card, message, Space, Table, Tag, Typography } from "antd";
import { api, ApiBizError } from "../api/client";
import type { TrainingPlan, TrainingPlanCourse } from "../api/types";

function MobileTrainingPlanTable({ plan }: { plan: TrainingPlan }) {
  return (
    <Table<TrainingPlanCourse>
      className="mobile-grade-table"
      rowKey={(r) => `${r.term}-${r.course_code}-${r.index}`}
      dataSource={plan.items}
      size="small"
      pagination={false}
      bordered
      columns={[
        { title: "课程", dataIndex: "course_name", ellipsis: true },
        { title: "学期", dataIndex: "term", width: 78 },
        { title: "学分", dataIndex: "credit", width: 40, align: "center" },
        { title: "学时", dataIndex: "total_hours", width: 40, align: "center" },
        { title: "考核", dataIndex: "assessment_method", width: 52, align: "center" },
      ]}
    />
  );
}

export function TrainingPlanContent() {
  const [loading, setLoading] = useState(false);
  const [plan, setPlan] = useState<TrainingPlan | null>(null);

  const query = async () => {
    setLoading(true);
    try {
      setPlan(await api.trainingPlan());
    } catch (error) {
      const msg = error instanceof ApiBizError ? error.message : "查询失败";
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { title: "学期", dataIndex: "term", key: "term", width: 110 },
    { title: "课程代码", dataIndex: "course_code", key: "course_code", width: 120 },
    { title: "课程名称", dataIndex: "course_name", key: "course_name" },
    { title: "开课单位", dataIndex: "department", key: "department", width: 140 },
    { title: "学分", dataIndex: "credit", key: "credit", width: 70 },
    { title: "学时", dataIndex: "total_hours", key: "total_hours", width: 70 },
    { title: "考核方式", dataIndex: "assessment_method", key: "assessment_method", width: 90 },
    {
      title: "课程属性",
      dataIndex: "course_attribute",
      key: "course_attribute",
      width: 100,
      render: (v: string) => (v ? <Tag color="blue">{v}</Tag> : "-"),
    },
    { title: "考试", dataIndex: "is_exam", key: "is_exam", width: 70 },
  ];

  return (
    <>
      <Space className="query-toolbar" wrap>
        <Button type="primary" loading={loading} onClick={query}>
          查询培养方案
        </Button>
      </Space>
      <Typography.Text type="secondary" style={{ marginLeft: 16 }}>
        展示当前登录学生的完整培养方案课程清单。
      </Typography.Text>
      {plan && (
        <>
          <Table<TrainingPlanCourse>
            className="desktop-table"
            rowKey={(r) => `${r.term}-${r.course_code}-${r.index}`}
            columns={columns}
            dataSource={plan.items}
            size="small"
            pagination={{ pageSize: 20 }}
            scroll={{ x: 900 }}
          />
          <MobileTrainingPlanTable plan={plan} />
        </>
      )}
    </>
  );
}

export default function TrainingPlanPage() {
  return (
    <Card title="培养方案">
      <TrainingPlanContent />
    </Card>
  );
}
