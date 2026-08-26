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
  is_admin: boolean;
  is_super_admin: boolean;
}

export interface AuthStatus {
  logged_in: boolean;
  username: string | null;
  is_admin: boolean;
  is_super_admin: boolean;
}

export interface ToolCallInfo {
  tool: string;
  arguments?: Record<string, unknown>;
  result_type: string;
}

export interface CitationInfo {
  ref: string;
  type: "map_place" | "map_route";
  title: string;
  url: string | null;
  data: Record<string, unknown>;
}

export interface ChatData {
  answer: string;
  intent: string;
  tool_calls: ToolCallInfo[];
  result_type: string;
  data: unknown;
  sources: string[];
  citations: CitationInfo[];
  conversation_id?: string | null;
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationListData {
  items: ConversationSummary[];
  page: number;
  page_size: number;
  total: number;
}

export interface StoredTurn {
  id: string;
  position: number;
  user_message: string;
  response: ChatData;
  created_at: string;
}

export interface ConversationDetailData {
  conversation: ConversationSummary;
  turns: StoredTurn[];
  has_more: boolean;
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
  resource_path?: string | null;
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

// ---- 操作手册管理（自进化审核） ----

export interface AdminPlaybookEntry {
  id: string;
  title: string;
  keywords: string[];
  source: "manual" | "auto" | string;
  instructions: string;
}

export interface AdminPlaybookList {
  entries: AdminPlaybookEntry[];
  hit_stats: Record<string, number>;
}

export interface AdminDraft {
  id: string;
  title: string;
  keywords: string[];
  cluster_count: number;
  warnings: string;
  instructions: string;
}

export interface AdminEvolveDraft {
  id: string | null;
  title: string;
  warnings?: string[];
  error?: string;
}

export interface AdminEvolveResult {
  clusters_found: number;
  drafts: AdminEvolveDraft[];
}

export interface AdminGrantItem {
  student_number: string;
  is_super_admin: boolean;
  granted_by_student_number: string | null;
  created_at: string | null;
}

export interface AdminUserItem {
  id: string;
  student_number: string;
  created_at: string;
  last_login_at: string;
  visit_count: number;
  last_visit_on: string | null;
  last_active_at: string | null;
  has_active_session: boolean;
  conversation_count: number;
}

export interface AdminUserList extends PagedData<AdminUserItem> {
  daily_active_users: number;
}

export interface PagedData<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface AdminConversationList extends PagedData<ConversationSummary> {
  user: { id: string; student_number: string };
}

export interface AdminConversationDetail {
  user: { id: string; student_number: string };
  conversation: ConversationSummary;
  turns: StoredTurn[];
  has_more: boolean;
}

export interface AuditLogItem {
  id: string;
  event_type: string;
  success: boolean;
  actor_student_number: string | null;
  target_student_number: string | null;
  target_type: string | null;
  target_id: string | null;
  error_code: string | null;
  ip_address: string | null;
  user_agent: string | null;
  details: Record<string, unknown>;
  created_at: string;
}
