import axios from "axios";
import type {
  ApiEnvelope,
  AuthStatus,
  CaptchaData,
  ChatData,
  ConversationDetailData,
  ConversationListData,
  ClassroomSchedule,
  GradeReport,
  LoginData,
  Schedule,
  ResourceTree,
  SearchData,
  TrainingPlan,
} from "./types";

const TOKEN_KEY = "session_token";
const AUTH_EXPIRED_CODES = new Set(["AUTH_REQUIRED", "SESSION_EXPIRED"]);
const authExpiredListeners = new Set<() => void>();

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

/** 订阅登录会话失效；用于让路由立即刷新认证状态。 */
export function onAuthExpired(listener: () => void) {
  authExpiredListeners.add(listener);
  return () => {
    authExpiredListeners.delete(listener);
  };
}

/** 统一处理普通请求与流式请求返回的会话失效错误。 */
export function handleAuthExpired(code: string | undefined): boolean {
  if (!code || !AUTH_EXPIRED_CODES.has(code) || !getToken()) {
    return false;
  }
  setToken(null);
  authExpiredListeners.forEach((listener) => listener());
  return true;
}

/** 业务错误：后端返回 success=false 或 HTTP 错误时抛出 */
export class ApiBizError extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

const client = axios.create({ baseURL: "/", timeout: 90000 });

// 请求拦截：自动附带会话 token
client.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.set("X-Session-Token", token);
  }
  return config;
});

// 响应拦截：统一拆包 {success, data, message, code}
client.interceptors.response.use(
  (response) => {
    const body = response.data as ApiEnvelope<unknown>;
    if (body && body.success === false) {
      handleAuthExpired(body.code);
      throw new ApiBizError(body.code ?? "UNKNOWN", body.message ?? "请求失败");
    }
    return response;
  },
  (error) => {
    const body = error.response?.data as ApiEnvelope<unknown> | undefined;
    if (body?.code) {
      handleAuthExpired(body.code);
      throw new ApiBizError(body.code, body.message ?? "请求失败");
    }
    if (error.code === "ECONNABORTED") {
      throw new ApiBizError("TIMEOUT", "请求超时，请稍后重试");
    }
    throw new ApiBizError("NETWORK_ERROR", "无法连接后端服务，请确认后端已启动");
  },
);

function unwrap<T>(response: { data: ApiEnvelope<T> }): T {
  return response.data.data as T;
}

export const api = {
  // ---- 认证 ----
  getCaptcha: () =>
    client.post<ApiEnvelope<CaptchaData>>("/api/auth/captcha").then(unwrap),
  login: (payload: {
    session_token: string;
    username: string;
    password: string;
    captcha: string;
  }) => client.post<ApiEnvelope<LoginData>>("/api/auth/login", payload).then(unwrap),
  logout: () => client.post<ApiEnvelope<unknown>>("/api/auth/logout").then(unwrap),
  authStatus: () =>
    client.get<ApiEnvelope<AuthStatus>>("/api/auth/status").then(unwrap),

  // ---- 对话 ----
  chat: (message: string, conversationId?: string | null) =>
    client
      .post<ApiEnvelope<ChatData>>("/api/chat", {
        message,
        conversation_id: conversationId || null,
      })
      .then(unwrap),
  conversations: (page = 1, pageSize = 20) =>
    client
      .get<ApiEnvelope<ConversationListData>>("/api/conversations", {
        params: { page, page_size: pageSize },
      })
      .then(unwrap),
  conversation: (id: string, beforePosition?: number, limit = 50) =>
    client
      .get<ApiEnvelope<ConversationDetailData>>(`/api/conversations/${id}`, {
        params: {
          limit,
          ...(beforePosition ? { before_position: beforePosition } : {}),
        },
      })
      .then(unwrap),
  deleteConversation: (id: string) =>
    client.delete<ApiEnvelope<{ deleted: boolean }>>(`/api/conversations/${id}`).then(unwrap),

  // ---- 教务查询 ----
  schedule: (term: string, week?: number) =>
    client
      .get<ApiEnvelope<Schedule>>("/api/schedule", { params: { term, week } })
      .then(unwrap),
  grades: (term?: string) =>
    client
      .get<ApiEnvelope<GradeReport>>("/api/grades", { params: term ? { term } : {} })
      .then(unwrap),
  trainingPlan: () =>
    client.get<ApiEnvelope<TrainingPlan>>("/api/training-plan").then(unwrap),
  classroomBuildings: (campus: string) =>
    client
      .get<ApiEnvelope<{ label: string; value: string }[]>>("/api/classroom-buildings", {
        params: { campus },
      })
      .then(unwrap),
  classroomSchedule: (params: {
    term: string;
    campus?: string;
    building?: string;
  }) =>
    client
      .get<ApiEnvelope<ClassroomSchedule>>("/api/classroom-schedule", { params })
      .then(unwrap),

  // ---- 知识库/资讯 ----
  knowledgeSearch: (q: string) =>
    client
      .get<ApiEnvelope<SearchData>>("/api/knowledge/search", { params: { q } })
      .then(unwrap),
  informationSearch: (q: string) =>
    client
      .get<ApiEnvelope<SearchData>>("/api/information/search", { params: { q } })
      .then(unwrap),

  // ---- 资料文件 ----

  /** 资料文件树（按目录分组） */
  resourceFiles: () =>
    client.get<ApiEnvelope<ResourceTree>>("/api/knowledge/files").then(unwrap),

  /** 资料文件下载/预览 URL */
  resourceFileUrl: (path: string) =>
    `/api/knowledge/files/download?path=${encodeURIComponent(path)}`,

  /** 通用 GET 请求（用于后端代理转发外部 API） */
  getExternal: async <T = unknown>(url: string) => {
    const res = await client.get<ApiEnvelope<T>>(url);
    return res.data.data as T;
  },
};
