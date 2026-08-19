import axios from "axios";
import type {
  AdminDraft,
  AdminEvolveResult,
  AdminPlaybookList,
  ApiEnvelope,
} from "./types";

/**
 * 操作手册管理（自进化审核）API。
 *
 * 使用独立 axios 实例：管理接口的 401（AUTH_REQUIRED）表示管理员令牌无效，
 * 不能像共享实例那样误清学生登录会话。令牌仅存 sessionStorage，关闭标签页即失效。
 */

export class AdminApiError extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

const ADMIN_TOKEN_KEY = "admin_token";

export function getAdminToken(): string {
  return sessionStorage.getItem(ADMIN_TOKEN_KEY) ?? "";
}

export function setAdminToken(token: string) {
  if (token) {
    sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
  } else {
    sessionStorage.removeItem(ADMIN_TOKEN_KEY);
  }
}

const client = axios.create({ baseURL: "/", timeout: 90000 });

client.interceptors.request.use((config) => {
  const token = getAdminToken();
  if (token) {
    config.headers.set("X-Admin-Token", token);
  }
  return config;
});

client.interceptors.response.use(
  (response) => {
    const body = response.data as ApiEnvelope<unknown>;
    if (body && body.success === false) {
      throw new AdminApiError(body.code ?? "UNKNOWN", body.message ?? "请求失败");
    }
    return response;
  },
  (error) => {
    const body = error.response?.data as ApiEnvelope<unknown> | undefined;
    if (body?.code) {
      throw new AdminApiError(body.code, body.message ?? "请求失败");
    }
    if (error.code === "ECONNABORTED") {
      throw new AdminApiError("TIMEOUT", "请求超时，进化耗时较长，请稍后刷新草稿列表");
    }
    throw new AdminApiError("NETWORK_ERROR", "无法连接后端服务，请确认后端已启动");
  },
);

function unwrap<T>(response: { data: ApiEnvelope<T> }): T {
  return response.data.data as T;
}

export const adminApi = {
  /** 正式手册列表与命中统计 */
  playbooks: () =>
    client.get<ApiEnvelope<AdminPlaybookList>>("/api/admin/playbooks").then(unwrap),

  /** 待审草稿列表 */
  drafts: () =>
    client
      .get<ApiEnvelope<{ drafts: AdminDraft[] }>>("/api/admin/playbooks/drafts")
      .then(unwrap),

  /** 触发一次进化流水线（耗时较长） */
  evolve: () =>
    client
      .post<ApiEnvelope<AdminEvolveResult>>("/api/admin/playbooks/evolve", null, {
        timeout: 600000,
      })
      .then(unwrap),

  /** 审核通过：草稿转正式手册并立即生效 */
  approve: (draftId: string) =>
    client
      .post<ApiEnvelope<{ id: string; title: string; keywords: string[] }>>(
        `/api/admin/playbooks/drafts/${draftId}/approve`,
      )
      .then(unwrap),

  /** 审核拒绝：删除草稿 */
  reject: (draftId: string) =>
    client
      .post<ApiEnvelope<{ id: string; rejected: boolean }>>(
        `/api/admin/playbooks/drafts/${draftId}/reject`,
      )
      .then(unwrap),
};
