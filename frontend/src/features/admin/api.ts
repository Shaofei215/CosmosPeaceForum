import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { API_CONFIG } from '@/shared/config/api';
import type {
  AdminCreateRequest,
  AdminLoginRequest,
  AdminLoginResponse,
  AdminProfileUpdateRequest,
  AdminUpdateRequest,
  AdminUser,
  ContentDeleteRequest,
  ContentItem,
  DashboardStats,
  OperationLog,
  PaginatedResponse,
  TerminalLogList,
  UserModerationUpdateRequest,
  UserWithModeration,
} from './types';
import { useAdminAuthStore } from './store';

interface ApiErrorPayload {
  detail?: string;
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

client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('adminToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response.data,
  (error: AxiosError<ApiErrorPayload>) => {
    const status = error.response?.status ?? 0;
    if (status === 401) {
      useAdminAuthStore.getState().logout();
    }
    const apiError: AdminApiError = {
      name: 'AdminApiError',
      status,
      message: error.response?.data?.detail || '请求失败，请稍后重试',
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
    client.put<unknown, UserWithModeration>(`/users/${userId}/moderation`, request),
  content: (params: { skip?: number; limit?: number; type?: string; keyword?: string }) =>
    client.get<unknown, PaginatedResponse<ContentItem>>('/content/', { params }),
  deletePost: (postId: number, request: ContentDeleteRequest) =>
    client.delete<unknown, void>(`/content/posts/${postId}`, { data: request }),
  deleteComment: (commentId: number, request: ContentDeleteRequest) =>
    client.delete<unknown, void>(`/content/comments/${commentId}`, { data: request }),
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
};
