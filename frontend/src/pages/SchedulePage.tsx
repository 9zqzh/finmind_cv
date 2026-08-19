import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  Empty,
  InputNumber,
  message,
  Select,
  Space,
  Typography,
} from "antd";
import { api, ApiBizError } from "../api/client";
import type { Schedule, ScheduleEntry } from "../api/types";
import { useAuth } from "../context/AuthContext";
import { getDefaultTerm, getTermOptions } from "../utils/terms";

const WEEKDAY_NAMES = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"];

function ScheduleGrid({
  schedule,
  selectedCourse,
  onCourseClick,
}: {
  schedule: Schedule;
  selectedCourse: ScheduleEntry | null;
  onCourseClick: (course: ScheduleEntry) => void;
}) {
  const periods = Array.from({ length: 7 }, (_, index) => index + 1);

  return (
    <div className="schedule-grid-scroll">
      <div className="schedule-grid" role="table" aria-label="我的课表">
        <div className="schedule-grid__cell schedule-grid__cell--corner" role="columnheader">
          节次
        </div>
        {WEEKDAY_NAMES.slice(1).map((weekday) => (
          <div
            key={weekday}
            className="schedule-grid__cell schedule-grid__cell--header"
            role="columnheader"
          >
            {weekday}
          </div>
        ))}
        {periods.map((period) => (
          <div key={period} className="schedule-grid__row" role="row">
            <div className="schedule-grid__cell schedule-grid__cell--period" role="rowheader">
              第 {period} 节
            </div>
            {WEEKDAY_NAMES.slice(1).map((_, weekdayIndex) => {
              const entries = schedule.items.filter(
                (item) => item.weekday === weekdayIndex + 1 && item.period === period,
              );
              return (
                <div
                  key={`${period}-${weekdayIndex}`}
                  className="schedule-grid__cell schedule-grid__cell--course"
                  role="cell"
                >
                  {entries.length ? (
                    entries.map((entry, index) => (
                      <div
                        key={`${entry.course_name}-${entry.teacher ?? ""}-${index}`}
                        className={`schedule-grid__course${
                          selectedCourse === entry ? " schedule-grid__course--selected" : ""
                        }`}
                        role="button"
                        tabIndex={0}
                        onClick={() => onCourseClick(entry)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            onCourseClick(entry);
                          }
                        }}
                      >
                        <Typography.Text strong className="schedule-grid__course-name">
                          {entry.course_name}
                        </Typography.Text>
                        <Typography.Text
                          type="secondary"
                          className="schedule-grid__course-meta"
                        >
                          {entry.teacher ?? "教师未安排"}
                        </Typography.Text>
                        <Typography.Text
                          type="secondary"
                          className="schedule-grid__course-meta"
                        >
                          {entry.classroom ?? "教室未安排"}
                        </Typography.Text>
                        <Typography.Text
                          type="secondary"
                          className="schedule-grid__course-meta"
                        >
                          {entry.weeks_text || "全学期"}
                        </Typography.Text>
                      </div>
                    ))
                  ) : (
                    <span className="schedule-grid__empty">-</span>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

function ScheduleMobileList({
  schedule,
  selectedCourse,
  onCourseClick,
}: {
  schedule: Schedule;
  selectedCourse: ScheduleEntry | null;
  onCourseClick: (course: ScheduleEntry) => void;
}) {
  const sortedItems = [...schedule.items].sort(
    (a, b) => a.weekday - b.weekday || a.period - b.period,
  );

  if (sortedItems.length === 0) {
    return <Empty className="mobile-only" description="当前筛选条件下没有课程" />;
  }

  return (
    <div className="schedule-mobile-list mobile-only">
      {WEEKDAY_NAMES.slice(1).map((weekday, index) => {
        const dayItems = sortedItems.filter((item) => item.weekday === index + 1);
        if (dayItems.length === 0) return null;

        return (
          <div key={weekday} className="schedule-mobile-day">
            <Typography.Text className="schedule-mobile-day__title">
              {weekday}
            </Typography.Text>
            {dayItems.map((entry, itemIndex) => (
              <div
                key={`${entry.course_name}-${entry.teacher ?? ""}-${itemIndex}`}
                className={`schedule-mobile-course${
                  selectedCourse === entry ? " schedule-mobile-course--selected" : ""
                }`}
                role="button"
                tabIndex={0}
                onClick={() => onCourseClick(entry)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onCourseClick(entry);
                  }
                }}
              >
                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                  <Typography.Text strong>{entry.course_name}</Typography.Text>
                  <Typography.Text type="secondary">
                    {entry.period_name} · {entry.teacher ?? "教师未安排"}
                  </Typography.Text>
                  <Typography.Text type="secondary">
                    {entry.classroom ?? "教室未安排"} · {entry.weeks_text || "全学期"}
                  </Typography.Text>
                </Space>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

export function ScheduleContent() {
  const { username } = useAuth();
  const termOptions = useMemo(() => getTermOptions(username), [username]);
  const [term, setTerm] = useState("");
  const [week, setWeek] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [selectedCourse, setSelectedCourse] = useState<ScheduleEntry | null>(null);

  useEffect(() => {
    if (!termOptions.some((option) => option.value === term)) {
      setTerm(getDefaultTerm(username));
    }
  }, [term, termOptions, username]);

  const query = async () => {
    setLoading(true);
    try {
      setSchedule(await api.schedule(term, week ?? undefined));
      setSelectedCourse(null);
    } catch (error) {
      const msg = error instanceof ApiBizError ? error.message : "查询失败";
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Space className="query-toolbar" style={{ marginBottom: 16 }} wrap>
        <Select
          value={term}
          options={termOptions}
          onChange={setTerm}
          placeholder="选择学期"
          className="query-toolbar__control"
          style={{ width: 180 }}
        />
        <InputNumber
          value={week}
          onChange={(v) => setWeek(v)}
          min={1}
          max={30}
          placeholder="周次（可选）"
          className="query-toolbar__control"
        />
        <Button type="primary" onClick={query} loading={loading}>
          查询
        </Button>
      </Space>
      {schedule && (
        <>
          <Typography.Paragraph>
            {selectedCourse ? (
              <>
                课程：{selectedCourse.course_name} ·{" "}
                {WEEKDAY_NAMES[selectedCourse.weekday] ?? "未知星期"} ·{" "}
                {selectedCourse.period_name} · 教师：
                {selectedCourse.teacher ?? "未安排"} · 教室：
                {selectedCourse.classroom ?? "未安排"} · 周次：
                {selectedCourse.weeks_text || "全学期"}
              </>
            ) : (
              <>
                学期：{schedule.term}
                {schedule.week ? ` · 第 ${schedule.week} 周` : " · 整学期"}
                {schedule.remarks ? ` · ${schedule.remarks}` : ""}
              </>
            )}
          </Typography.Paragraph>
          <ScheduleGrid
            schedule={schedule}
            selectedCourse={selectedCourse}
            onCourseClick={setSelectedCourse}
          />
          <ScheduleMobileList
            schedule={schedule}
            selectedCourse={selectedCourse}
            onCourseClick={setSelectedCourse}
          />
        </>
      )}
    </>
  );
}

export default function SchedulePage() {
  return (
    <Card title="我的课表">
      <ScheduleContent />
    </Card>
  );
}
