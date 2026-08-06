// 与后端 app/schemas 保持一致的接口类型定义

export interface ApiEnvelope<T> {
  success: boolean;
  data: T | null;
  message: string | null;
  code?: string;
}

export interface CaptchaData {
  session_token: string;
  image_base64: string;
  content_type: string;
}

export interface LoginData {
  session_token: string;
  username: string;
  success: boolean;
}

export interface AuthStatus {
  logged_in: boolean;
  username: string | null;
}

export interface ToolCallInfo {
  tool: string;
  arguments?: Record<string, unknown>;
  result_type: string;
}

export interface ChatData {
  answer: string;
  intent: string;
  tool_calls: ToolCallInfo[];
  result_type: string;
  data: unknown;
  sources: string[];
}

export interface ScheduleEntry {
  course_name: string;
  teacher: string | null;
  classroom: string | null;
  weeks_text: string;
  weeks: number[];
  weekday: number;
  period: number;
  period_name: string;
}

export interface Schedule {
  term: string;
  week: number | null;
  items: ScheduleEntry[];
  remarks: string | null;
}

export interface GradeItem {
  index: number;
  term: string;
  course_code: string;
  course_name: string;
  score: string;
  credit: string;
  total_hours: string;
  grade_point: string;
  assessment_method: string;
  course_attribute: string;
  course_nature: string;
}

export interface GradeReport {
  required_credits: string | null;
  earned_credits: string | null;
  remaining_credits: string | null;
  major_gpa: string | null;
  minor_gpa: string | null;
  items: GradeItem[];
}

export interface TrainingPlanCourse {
  index: number;
  term: string;
  course_code: string;
  course_name: string;
  department: string;
  credit: string;
  total_hours: string;
  assessment_method: string;
  course_attribute: string;
  is_exam: string;
}

export interface TrainingPlan {
  items: TrainingPlanCourse[];
}

export interface ClassroomEntry {
  classroom: string;
  weekday: number;
  period: string;
  course_name: string;
  teacher: string | null;
  weeks_text: string | null;
  weeks: number[];
  class_name: string | null;
}

export interface ClassroomSchedule {
  term: string;
  items: ClassroomEntry[];
}

export interface SearchChunk {
  text: string;
  source: string;
  title: string;
  score?: number;
}

export interface SearchData {
  query: string;
  results: SearchChunk[];
  sources: string[];
}

export interface ResourceFile {
  name: string;
  path: string;
  ext: string;
  size: number;
}

export interface ResourceDirectory {
  name: string;
  path: string;
  files: ResourceFile[];
}

export interface ResourceTree {
  directories: ResourceDirectory[];
  files: ResourceFile[];
}
