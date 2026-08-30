import { useMemo, useState } from "react";
import {
  Button,
  Card,
  Descriptions,
  message,
  Select,
  Space,
  Table,
  Tag,
} from "antd";
import { api, ApiBizError } from "../api/client";
import { useIsMobile } from "../hooks/useIsMobile";
import type { GradeReport } from "../api/types";
import { useAuth } from "../context/AuthContext";
import { getTermOptions } from "../utils/terms";

function MobileGradeTable({ report }: { report: GradeReport }) {
  return (
    <Table
      className="mobile-grade-table"
      size="small"
      rowKey="index"
      dataSource={report.items}
      pagination={false}
      bordered
      columns={[
        { title: "课程", dataIndex: "course_name", ellipsis: true },
        {
          title: "分数",
          dataIndex: "score",
          width: 56,
          align: "center",
          render: (v: string) => <Tag color="blue">{v}</Tag>,
        },
        { title: "学分", dataIndex: "credit", width: 46, align: "center" },
        { title: "绩点", dataIndex: "grade_point", width: 46, align: "center" },
        { title: "考核", dataIndex: "assessment_method", width: 58, align: "center" },
      ]}
    />
  );
}

export function GradesContent() {
  const { username } = useAuth();
  const isMobile = useIsMobile();
  const termOptions = useMemo(() => getTermOptions(username), [username]);
  const [term, setTerm] = useState("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<GradeReport | null>(null);

  const query = async () => {
    setLoading(true);
    try {
      setReport(await api.grades(term || undefined));
    } catch (error) {
      const msg = error instanceof ApiBizError ? error.message : "查询失败";
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Space className="query-toolbar" style={{ marginBottom: 16 }}>
        <Select
          value={term}
          onChange={setTerm}
          options={[{ label: "全部学期", value: "" }, ...termOptions]}
          placeholder="按学期过滤（可选）"
          className="query-toolbar__control"
          style={{ width: 240 }}
        />
        <Button type="primary" onClick={query} loading={loading}>
          查询
        </Button>
      </Space>
      {report && (
        <>
          <Descriptions
            size="small"
            column={{ xs: 1, sm: 2, md: 4 }}
            bordered
            style={{ marginBottom: 16 }}
          >
            <Descriptions.Item label="已获学分">
              {report.earned_credits ?? "-"}
            </Descriptions.Item>
            <Descriptions.Item label="要求学分">
              {report.required_credits ?? "-"}
            </Descriptions.Item>
            <Descriptions.Item label="主修绩点">
              {report.major_gpa ?? "-"}
            </Descriptions.Item>
            <Descriptions.Item label="辅修绩点">
              {report.minor_gpa ?? "-"}
            </Descriptions.Item>
          </Descriptions>
          <Table
            className="desktop-table"
            size="small"
            rowKey="index"
            dataSource={report.items}
            pagination={{ pageSize: 15, hideOnSinglePage: true }}
            bordered
            scroll={{ x: 900 }}
            columns={[
              { title: "课程", dataIndex: "course_name" },
              { title: "学期", dataIndex: "term", width: 120 },
              {
                title: "分数",
                dataIndex: "score",
                width: 80,
                render: (v: string) => <Tag color="blue">{v}</Tag>,
              },
              { title: "学分", dataIndex: "credit", width: 70 },
              { title: "绩点", dataIndex: "grade_point", width: 70 },
              { title: "考核方式", dataIndex: "assessment_method", width: 90 },
              { title: "课程属性", dataIndex: "course_attribute", width: 120 },
              { title: "课程性质", dataIndex: "course_nature", width: 100 },
            ]}
          />
          {isMobile && <MobileGradeTable report={report} />}
        </>
      )}
    </>
  );
}

export default function GradesPage() {
  return (
    <Card title="成绩查询">
      <GradesContent />
    </Card>
  );
}
