import { httpClient, unwrap } from "./client";
import type {
  AdminConversationDetail,
  AdminConversationList,
  AdminDraft,
  AdminEvolveResult,
  AdminGrantItem,
  AdminPlaybookList,
  AdminUserList,
  ApiEnvelope,
  AuditLogItem,
  PagedData,
} from "./types";

export const adminApi = {
  playbooks: () =>
    httpClient.get<ApiEnvelope<AdminPlaybookList>>("/api/admin/playbooks").then(unwrap),
  drafts: () =>
    httpClient.get<ApiEnvelope<{ drafts: AdminDraft[] }>>("/api/admin/playbooks/drafts").then(unwrap),
  evolve: () =>
    httpClient.post<ApiEnvelope<AdminEvolveResult>>("/api/admin/playbooks/evolve", null, {
      timeout: 600000,
    }).then(unwrap),
  approve: (draftId: string) =>
    httpClient.post<ApiEnvelope<{ id: string; title: string; keywords: string[] }>>(
      `/api/admin/playbooks/drafts/${draftId}/approve`,
    ).then(unwrap),
  reject: (draftId: string) =>
    httpClient.post<ApiEnvelope<{ id: string; rejected: boolean }>>(
      `/api/admin/playbooks/drafts/${draftId}/reject`,
    ).then(unwrap),
  admins: () =>
    httpClient.get<ApiEnvelope<{ items: AdminGrantItem[]; can_manage: boolean }>>(
      "/api/admin/admins",
    ).then(unwrap),
  grantAdmin: (studentNumber: string) =>
    httpClient.post<ApiEnvelope<AdminGrantItem>>("/api/admin/admins", {
      student_number: studentNumber,
    }).then(unwrap),
  revokeAdmin: (studentNumber: string) =>
    httpClient.delete<ApiEnvelope<{ student_number: string; revoked: boolean }>>(
      `/api/admin/admins/${encodeURIComponent(studentNumber)}`,
    ).then(unwrap),
  users: (page = 1, pageSize = 20, q = "") =>
    httpClient.get<ApiEnvelope<AdminUserList>>("/api/admin/users", {
      params: { page, page_size: pageSize, q },
    }).then(unwrap),
  exportUsers: (q = "") =>
    httpClient.get<Blob>("/api/admin/users/export", {
      params: { q },
      responseType: "blob",
    }),
  userConversations: (userId: string, page = 1, pageSize = 20) =>
    httpClient.get<ApiEnvelope<AdminConversationList>>(
      `/api/admin/users/${userId}/conversations`,
      { params: { page, page_size: pageSize } },
    ).then(unwrap),
  conversation: (conversationId: string, beforePosition?: number, limit = 50) =>
    httpClient.get<ApiEnvelope<AdminConversationDetail>>(
      `/api/admin/conversations/${conversationId}`,
      { params: { limit, ...(beforePosition ? { before_position: beforePosition } : {}) } },
    ).then(unwrap),
  auditLogs: (params: Record<string, unknown>) =>
    httpClient.get<ApiEnvelope<PagedData<AuditLogItem>>>("/api/admin/audit-logs", { params }).then(unwrap),
};
