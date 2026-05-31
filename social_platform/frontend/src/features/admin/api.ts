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
  DashboardStats,
  HotTopic,
  HotTopicGeneration,
  HotTopicGenerationRunResponse,
  HotTopicRequest,
  HotTopicSettings,
  HotTopicSettingsUpdate,
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

interface ApiErrorPayload {
  detail?: unknown;
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

client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('adminToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  response => response.data,
  (error: AxiosError<ApiErrorPayload>) => {
    const status = error.response?.status ?? 0;
    if (status === 401) {
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
  updateProfile: (request: AdminProfileUpdateRequest) =>
    client.put<unknown, AdminUser>('/auth/profile', request),
  dashboardStats: () => client.get<unknown, DashboardStats>('/dashboard/stats'),
  users: (params: { skip?: number; limit?: number; keyword?: string }) =>
    client.get<unknown, PaginatedResponse<UserWithModeration>>('/users/', { params }),
  updateUserModeration: (userId: number, request: UserModerationUpdateRequest) =>
    client.put<unknown, UserModerationResponse>(`/users/${userId}/moderation`, request),
  updateUsersModeration: (request: UserModerationBatchUpdateRequest) =>
    client.put<unknown, UserModerationBatchUpdateResponse>('/users/moderation/batch', request),
  publishAnnouncement: (request: AdminAnnouncementRequest) =>
    client.post<unknown, AdminAnnouncementResponse>('/announcements/', request),
  content: (params: { skip?: number; limit?: number; type?: string; keyword?: string }) =>
    client.get<unknown, PaginatedResponse<ContentItem>>('/content/', { params }),
  deletePost: (postId: number, request: ContentDeleteRequest) =>
    client.delete<unknown, void>(`/content/posts/${postId}`, { data: request }),
  deleteComment: (commentId: number, request: ContentDeleteRequest) =>
    client.delete<unknown, void>(`/content/comments/${commentId}`, { data: request }),
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
