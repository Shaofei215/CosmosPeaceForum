/**
 * 平台内管理员 API 客户端。
 *
 * 管理员接口使用独立 token key 与 refresh 流程，避免和普通用户登录态互相覆盖。
 */

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { API_CONFIG } from '@/shared/config/api';
import type {
  AdminAnnouncementRequest,
  AdminAnnouncementResponse,
  AdminCreateRequest,
  AdminLoginRequest,
  AdminLoginResponse,
  AdminProfileUpdateRequest,
  AdminUpdateRequest,
  AdminUser,
  ContentDeleteRequest,
  ContentItem,
  ContentModerationLLMPromptConfig,
  ContentModerationLLMSettings,
  ContentModerationLLMSettingsUpdate,
  ReportedContentItem,
  ReportedUserItem,
  ReportReleaseResponse,
  DashboardStats,
  HotTopic,
  HotTopicGeneration,
  HotTopicGenerationRunResponse,
  HotTopicPromptConfig,
  HotTopicRequest,
  HotTopicSettings,
  HotTopicSettingsUpdate,
  InvitationCode,
  InvitationCodeCreateRequest,
  ModerationAppealItem,
  ModerationAppealRejectRequest,
  OperationLog,
  PaginatedResponse,
  TerminalLogList,
  ThemeSettings,
  ThemeSettingsUpdate,
  UserModerationBatchUpdateRequest,
  UserModerationBatchUpdateResponse,
  UserModerationResponse,
  UserModerationUpdateRequest,
  UserWithModeration,
} from './types';
import { useAdminAuthStore } from './store';
import { getAdminAccessToken, getAdminRefreshToken, updateAdminTokens } from './tokenStorage';

interface ApiErrorPayload {
  detail?: unknown;
}

interface RetryRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

interface RefreshResponse {
  access_token: string;
  refresh_token: string;
}

export interface AdminApiError {
  name: 'AdminApiError';
  status: number;
  message: string;
}

const client = axios.create({
  baseURL: `${API_CONFIG.BASE_URL}/admin`,
  timeout: API_CONFIG.TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

/** 从 FastAPI detail 字段中提取适合展示的错误消息。 */
function getApiErrorMessage(detail: unknown) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map(item => {
        if (item && typeof item === 'object' && 'msg' in item) {
          return String((item as { msg?: unknown }).msg);
        }
        return null;
      })
      .filter(Boolean);
    if (messages.length > 0) return messages.join('；');
  }
  return '请求失败，请稍后重试';
}

let refreshPromise: Promise<string | null> | null = null;

/** 合并并发 401，并用平台管理员 refresh token 轮换新的 access token。 */
async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;
  const refreshToken = getAdminRefreshToken();
  if (!refreshToken) return null;

  refreshPromise = axios
    .post<RefreshResponse>(`${API_CONFIG.BASE_URL}/admin/auth/refresh`, {
      refresh_token: refreshToken,
    })
    .then(response => {
      updateAdminTokens(response.data.access_token, response.data.refresh_token);
      useAdminAuthStore.setState({ token: response.data.access_token, isAuthenticated: true });
      return response.data.access_token;
    })
    .catch(() => null)
    .finally(() => {
      refreshPromise = null;
    });
  return refreshPromise;
}

client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAdminAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  response => response.data,
  async (error: AxiosError<ApiErrorPayload>) => {
    const status = error.response?.status ?? 0;
    const originalRequest = error.config as RetryRequestConfig | undefined;
    if (status === 401 && originalRequest && !originalRequest._retry) {
      // 每个请求只自动重试一次，避免 refresh 失败后无限循环。
      originalRequest._retry = true;
      const nextToken = await refreshAccessToken();
      if (nextToken) {
        originalRequest.headers.Authorization = `Bearer ${nextToken}`;
        return client(originalRequest);
      }
      useAdminAuthStore.getState().logout();
    }
    const apiError: AdminApiError = {
      name: 'AdminApiError',
      status,
      message: getApiErrorMessage(error.response?.data?.detail),
    };
    return Promise.reject(apiError);
  }
);

export const adminApi = {
  login: (request: AdminLoginRequest) =>
    client.post<unknown, AdminLoginResponse>('/auth/login', request),
  me: () => client.get<unknown, AdminUser>('/auth/me'),
  logout: () => client.post<unknown, { message: string }>('/auth/logout'),
  updateProfile: (request: AdminProfileUpdateRequest) =>
    client.put<unknown, AdminUser>('/auth/profile', request),
  dashboardStats: () => client.get<unknown, DashboardStats>('/dashboard/stats'),
  users: (params: { skip?: number; limit?: number; keyword?: string }) =>
    client.get<unknown, PaginatedResponse<UserWithModeration>>('/users/', { params }),
  reportedUsers: (params: { skip?: number; limit?: number; keyword?: string }) =>
    client.get<unknown, PaginatedResponse<ReportedUserItem>>('/users/reports', { params }),
  moderatedUsers: (params: { skip?: number; limit?: number; keyword?: string }) =>
    client.get<unknown, PaginatedResponse<UserWithModeration>>('/users/moderated', { params }),
  userAppeals: (params: { skip?: number; limit?: number; keyword?: string }) =>
    client.get<unknown, PaginatedResponse<ModerationAppealItem>>('/users/appeals', { params }),
  approveUserAppeal: (appealId: number) =>
    client.post<unknown, void>('/users/appeals/' + appealId + '/approve'),
  rejectUserAppeal: (appealId: number, request: ModerationAppealRejectRequest) =>
    client.post<unknown, void>('/users/appeals/' + appealId + '/reject', request),
  invitations: (params: { skip?: number; limit?: number; keyword?: string }) =>
    client.get<unknown, PaginatedResponse<InvitationCode>>('/users/invitations', { params }),
  createInvitation: (request: InvitationCodeCreateRequest) =>
    client.post<unknown, InvitationCode>('/users/invitations', request),
  releaseReportedUser: (userId: number) =>
    client.post<unknown, ReportReleaseResponse>('/users/reports/' + userId + '/release'),
  banReportedUser: (userId: number, request: ContentDeleteRequest) =>
    client.delete<unknown, void>('/users/reports/' + userId, { data: request }),
  moderateReportedUser: (userId: number, request: UserModerationUpdateRequest) =>
    client.put<unknown, UserModerationResponse>(
      '/users/reports/' + userId + '/moderation',
      request
    ),
  userReportModerationSettings: () =>
    client.get<unknown, ContentModerationLLMSettings>('/users/report-moderation/settings'),
  updateUserReportModerationSettings: (request: ContentModerationLLMSettingsUpdate) =>
    client.put<unknown, ContentModerationLLMSettings>('/users/report-moderation/settings', request),
  userReportModerationPrompt: () =>
    client.get<unknown, ContentModerationLLMPromptConfig>('/users/report-moderation/prompt'),
  updateUserReportModerationPrompt: (value: string) =>
    client.put<unknown, ContentModerationLLMPromptConfig>('/users/report-moderation/prompt', {
      value,
    }),
  resetUserReportModerationPrompt: () =>
    client.post<unknown, ContentModerationLLMPromptConfig>('/users/report-moderation/prompt/reset'),
  updateUserModeration: (userId: number, request: UserModerationUpdateRequest) =>
    client.put<unknown, UserModerationResponse>(`/users/${userId}/moderation`, request),
  updateUsersModeration: (request: UserModerationBatchUpdateRequest) =>
    client.put<unknown, UserModerationBatchUpdateResponse>('/users/moderation/batch', request),
  publishAnnouncement: (request: AdminAnnouncementRequest) =>
    client.post<unknown, AdminAnnouncementResponse>('/announcements/', request),
  content: (params: { skip?: number; limit?: number; type?: string; keyword?: string }) =>
    client.get<unknown, PaginatedResponse<ContentItem>>('/content/', { params }),
  reportedContent: (params: { skip?: number; limit?: number; type?: string; keyword?: string }) =>
    client.get<unknown, PaginatedResponse<ReportedContentItem>>('/content/reports', { params }),
  archivedContent: (params: { skip?: number; limit?: number; type?: string; keyword?: string }) =>
    client.get<unknown, PaginatedResponse<ContentItem>>('/content/archived', { params }),
  contentAppeals: (params: { skip?: number; limit?: number; keyword?: string }) =>
    client.get<unknown, PaginatedResponse<ModerationAppealItem>>('/content/appeals', { params }),
  approveContentAppeal: (appealId: number) =>
    client.post<unknown, void>('/content/appeals/' + appealId + '/approve'),
  rejectContentAppeal: (appealId: number, request: ModerationAppealRejectRequest) =>
    client.post<unknown, void>('/content/appeals/' + appealId + '/reject', request),
  releaseReportedContent: (type: string, id: number) =>
    client.post<unknown, ReportReleaseResponse>('/content/reports/' + type + '/' + id + '/release'),
  deleteReportedContent: (type: string, id: number, request: ContentDeleteRequest) =>
    client.delete<unknown, void>('/content/reports/' + type + '/' + id, { data: request }),
  reportModerationSettings: () =>
    client.get<unknown, ContentModerationLLMSettings>('/content/report-moderation/settings'),
  updateReportModerationSettings: (request: ContentModerationLLMSettingsUpdate) =>
    client.put<unknown, ContentModerationLLMSettings>(
      '/content/report-moderation/settings',
      request
    ),
  reportModerationPrompt: () =>
    client.get<unknown, ContentModerationLLMPromptConfig>('/content/report-moderation/prompt'),
  updateReportModerationPrompt: (value: string) =>
    client.put<unknown, ContentModerationLLMPromptConfig>('/content/report-moderation/prompt', {
      value,
    }),
  resetReportModerationPrompt: () =>
    client.post<unknown, ContentModerationLLMPromptConfig>(
      '/content/report-moderation/prompt/reset'
    ),
  deletePost: (postId: number, request: ContentDeleteRequest) =>
    client.delete<unknown, void>(`/content/posts/${postId}`, { data: request }),
  deleteComment: (commentId: number, request: ContentDeleteRequest) =>
    client.delete<unknown, void>(`/content/comments/${commentId}`, { data: request }),
  restorePost: (postId: number) => client.post<unknown, void>(`/content/posts/${postId}/restore`),
  restoreComment: (commentId: number) =>
    client.post<unknown, void>(`/content/comments/${commentId}/restore`),
  hotTopics: (params: { skip?: number; limit?: number; status?: string; source?: string }) =>
    client.get<unknown, PaginatedResponse<HotTopic>>('/hot-topics/', { params }),
  createHotTopic: (request: HotTopicRequest) =>
    client.post<unknown, HotTopic>('/hot-topics/', request),
  updateHotTopic: (topicId: number, request: Partial<HotTopicRequest>) =>
    client.put<unknown, HotTopic>(`/hot-topics/items/${topicId}`, request),
  deleteHotTopic: (topicId: number) => client.delete<unknown, void>(`/hot-topics/items/${topicId}`),
  publishHotTopic: (topicId: number) =>
    client.post<unknown, HotTopic>(`/hot-topics/items/${topicId}/publish`),
  archiveHotTopic: (topicId: number) =>
    client.post<unknown, HotTopic>(`/hot-topics/items/${topicId}/archive`),
  hotTopicSettings: () => client.get<unknown, HotTopicSettings>('/hot-topics/settings'),
  updateHotTopicSettings: (request: HotTopicSettingsUpdate) =>
    client.put<unknown, HotTopicSettings>('/hot-topics/settings', request),
  hotTopicPrompt: () => client.get<unknown, HotTopicPromptConfig>('/hot-topics/prompt'),
  updateHotTopicPrompt: (value: string) =>
    client.put<unknown, HotTopicPromptConfig>('/hot-topics/prompt', { value }),
  resetHotTopicPrompt: () => client.post<unknown, HotTopicPromptConfig>('/hot-topics/prompt/reset'),
  getHotTopicGenerateEventsUrl: (token: string) =>
    `${API_CONFIG.BASE_URL}/admin/hot-topics/generate/events?token=${encodeURIComponent(token)}`,
  hotTopicGenerations: (params: { skip?: number; limit?: number }) =>
    client.get<unknown, PaginatedResponse<HotTopicGeneration>>('/hot-topics/generations', {
      params,
    }),
  generateHotTopics: () =>
    client.post<unknown, HotTopicGenerationRunResponse>('/hot-topics/generate'),
  publishHotTopicGeneration: (generationId: number) =>
    client.post<unknown, HotTopic[]>(`/hot-topics/generations/${generationId}/publish`),
  admins: (params: { skip?: number; limit?: number }) =>
    client.get<unknown, PaginatedResponse<AdminUser>>('/admins/', { params }),
  createAdmin: (request: AdminCreateRequest) =>
    client.post<unknown, AdminUser>('/admins/', request),
  updateAdmin: (adminId: number, request: AdminUpdateRequest) =>
    client.put<unknown, AdminUser>(`/admins/${adminId}`, request),
  operationLogs: (params: { skip?: number; limit?: number }) =>
    client.get<unknown, PaginatedResponse<OperationLog>>('/logs/operations', { params }),
  terminalLogs: (params: { count?: number; level?: string; keyword?: string }) =>
    client.get<unknown, TerminalLogList>('/logs/terminal', { params }),
  clearTerminalLogs: () => client.delete<unknown, { message: string }>('/logs/terminal'),
  theme: () => client.get<unknown, ThemeSettings>('/theme'),
  updateTheme: (request: ThemeSettingsUpdate) =>
    client.put<unknown, ThemeSettings>('/theme', request),
};
