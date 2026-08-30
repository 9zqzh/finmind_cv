import { Button, Card, Descriptions, List, Space, Table, Tag, Typography } from "antd";
import type {
  ChatData,
  ClassroomScheduleResult,
  GradeItem,
  GradeReport,
  MapPlacesResult,
  MapRoute,
  ScheduleResult,
  SearchResultPayload,
  TrainingPlanCourse,
  TrainingPlanResult,
} from "../../../api/types";
import { MODE_LABELS } from "../constants";
import { formatDistance } from "../utils/format";
import { amapNavigationUrl } from "../utils/url";
import { PlaceCover } from "./PlaceCover";
import { ratingTag } from "./RatingTag";

/** 根据后端 result_type 渲染结构化卡片 */
export function ResultCard({ chat }: { chat: ChatData }) {
  if (!chat.tool_calls.length || chat.data == null) {
    return null;
  }

  switch (chat.result_type) {
    case "schedule": {
      const { items = [] } = chat.data as ScheduleResult;
      return (
        <Table
          size="small"
          rowKey={(row) => `${row.course_name}-${row.weekday}-${row.period}`}
          dataSource={items}
          pagination={false}
          scroll={{ x: 720 }}
          columns={[
            { title: "课程", dataIndex: "course_name" },
            { title: "星期", dataIndex: "weekday", width: 70 },
            { title: "节次", dataIndex: "period_name", width: 110 },
            { title: "教室", dataIndex: "classroom", width: 130 },
            { title: "教师", dataIndex: "teacher", width: 100 },
            { title: "周次", dataIndex: "weeks_text", width: 110 },
          ]}
        />
      );
    }
    case "grades":
    case "training_plan": {
      const isGrades = chat.result_type === "grades";
      const report = chat.data as GradeReport;
      const plan = chat.data as TrainingPlanResult;
      const items: GradeItem[] | TrainingPlanCourse[] = isGrades
        ? report.items
        : plan.items;
      return (
        <>
          {isGrades && (
            <Descriptions
              size="small"
              column={{ xs: 1, sm: 2, md: 4 }}
              bordered
              style={{ marginBottom: 12 }}
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
          )}
          <Table<GradeItem | TrainingPlanCourse>
            size="small"
            rowKey="index"
            dataSource={items}
            pagination={{ pageSize: 10, hideOnSinglePage: true }}
            scroll={{ x: 760 }}
            columns={[
              { title: "课程", dataIndex: "course_name" },
              { title: "学期", dataIndex: "term", width: 120 },
              { title: "分数", dataIndex: "score", width: 80 },
              { title: "学分", dataIndex: "credit", width: 70 },
              { title: "绩点", dataIndex: "grade_point", width: 70 },
              { title: "属性", dataIndex: "course_attribute", width: 110 },
            ].filter(
              (col) => isGrades || col.dataIndex !== "score",
            )}
          />
        </>
      );
    }
    case "classroom_schedule": {
      const { items = [] } = chat.data as ClassroomScheduleResult;
      return (
        <Table
          size="small"
          rowKey={(row) => `${row.classroom}-${row.weekday}-${row.period}`}
          dataSource={items}
          pagination={{ pageSize: 10, hideOnSinglePage: true }}
          scroll={{ x: 640 }}
          columns={[
            { title: "教室", dataIndex: "classroom", width: 140 },
            { title: "星期", dataIndex: "weekday", width: 70 },
            { title: "节次", dataIndex: "period", width: 100 },
            { title: "课程", dataIndex: "course_name" },
            { title: "教师", dataIndex: "teacher", width: 100 },
          ]}
        />
      );
    }
    case "knowledge":
    case "information": {
      const { results = [] } = chat.data as SearchResultPayload;
      return (
        <Space direction="vertical" style={{ width: "100%" }}>
          {results.map((item, i) => (
            <Card key={i} size="small" title={item.title} extra={item.source}>
              <Typography.Paragraph
                style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}
                ellipsis={{ rows: 4, expandable: true }}
              >
                {item.text}
              </Typography.Paragraph>
            </Card>
          ))}
        </Space>
      );
    }
    case "map_places": {
      const { places = [] } = chat.data as MapPlacesResult;
      return (
        <List
          className={`map-place-results${places.length === 1 ? " map-place-results--single" : ""}`}
          size="small"
          dataSource={places}
          renderItem={(item) => {
            const url = amapNavigationUrl(item.location, item.name);
            return (
              <List.Item style={{ paddingInline: 0 }}>
                <div style={{ width: "100%" }}>
                  <PlaceCover imageUrl={item.image_url} name={item.name ?? "地点"} />
                  <Space wrap>
                    <Typography.Text strong>{item.name}</Typography.Text>
                    {ratingTag(Number(item.rating))}
                    {Number(item.cost) > 0 && (
                      <Tag color="gold">人均 ¥{item.cost}</Tag>
                    )}
                    {Number(item.comment_num) > 0 && (
                      <Tag>{item.comment_num} 条点评</Tag>
                    )}
                  </Space>
                  <div style={{ marginTop: 4 }}>
                    {item.distance ? (
                      <Typography.Text type="secondary" style={{ marginRight: 8 }}>
                        📍 距中心 {formatDistance(item.distance)}
                      </Typography.Text>
                    ) : null}
                    {item.address ? (
                      <Typography.Text type="secondary">{item.address}</Typography.Text>
                    ) : null}
                  </div>
                  {item.tel ? (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      📞 {item.tel}
                    </Typography.Text>
                  ) : null}
                  {url && (
                    <div style={{ marginTop: 4 }}>
                      <a href={url} target="_blank" rel="noreferrer">
                        查看位置与导航 ↗
                      </a>
                    </div>
                  )}
                </div>
              </List.Item>
            );
          }}
        />
      );
    }
    case "map_route": {
      const route = chat.data as MapRoute;
      const modeLabel = MODE_LABELS[route.mode ?? ""] ?? route.mode ?? "步行";
      const steps = route.steps ?? [];
      return (
        <Space direction="vertical" style={{ width: "100%" }}>
          <Descriptions size="small" column={{ xs: 1, sm: 3 }} bordered>
            <Descriptions.Item label="出行方式">{modeLabel}</Descriptions.Item>
            <Descriptions.Item label="距离">
              {route.distance_text ?? "-"}
            </Descriptions.Item>
            <Descriptions.Item label="预计耗时">
              {route.duration_text ?? "-"}
            </Descriptions.Item>
          </Descriptions>
          {steps.length > 0 && (
            <Typography.Paragraph
              style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}
              type="secondary"
            >
              {steps.map((step, i) => `${i + 1}. ${step}`).join("\n")}
            </Typography.Paragraph>
          )}
          {route.navigation_url && (
            <Button
              type="primary"
              size="small"
              href={route.navigation_url}
              target="_blank"
            >
              打开高德导航
            </Button>
          )}
        </Space>
      );
    }
    default:
      return (
        <pre style={{ fontSize: 12, maxHeight: 260, overflow: "auto" }}>
          {JSON.stringify(chat.data, null, 2)}
        </pre>
      );
  }
}
