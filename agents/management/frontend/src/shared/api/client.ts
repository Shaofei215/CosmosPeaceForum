/**
 * Management API 客户端。
 *
 * 统一注入短期 access token，并在 401 时使用 refresh token 静默轮换。
 * refresh 失败时清理本地认证状态，让用户回到登录页重新建立服务端 session。
 */

import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { API_CONFIG, HTTP_STATUS } from '@/shared/config/api';
import { getAccessToken, getRefreshToken, updateTokens } from '@/features/auth/tokenStorage';
import { useAuthStore } from '@/features/auth/stores/authStore';

interface RetryRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

interface RefreshResponse {
  access_token: string;
  refresh_token: string;
}

interface ValidationErrorDetail {
  msg?: string;
}

interface ApiErrorResponse {
  detail?: string | ValidationErrorDetail[];
}

/** 把 FastAPI 的字符串或结构化校验错误统一转换成可安全渲染的文本。 */
function normalizeErrorMessage(detail: ApiErrorResponse['detail']): string {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => item.msg)
      .filter((message): message is string => Boolean(message));
    if (messages.length > 0) return messages.join('；');
  }
  return '请求失败，请稍后重试';
}

/** 封装 axios 实例，集中处理认证头、refresh 轮换和错误格式化。 */
class ApiClient {
  private client: AxiosInstance;
  private refreshPromise: Promise<string | null> | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_CONFIG.BASE_URL,
      timeout: API_CONFIG.TIMEOUT,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  /**
   * 使用当前 refresh token 换取新的 token 对。
   *
   * refreshPromise 用于合并同一时间爆发的多个 401，避免并发请求重复消费同一个
   * 一次性 refresh token。
   */
  private async refreshAccessToken(): Promise<string | null> {
    if (this.refreshPromise) return this.refreshPromise;
    const refreshToken = getRefreshToken();
    if (!refreshToken) return null;

    this.refreshPromise = axios
      .post<RefreshResponse>(`${API_CONFIG.BASE_URL}/auth/refresh`, { refresh_token: refreshToken })
      .then((response) => {
        updateTokens(response.data.access_token, response.data.refresh_token);
        useAuthStore.setState({ isAuthenticated: true });
        return response.data.access_token;
      })
      .catch(() => null)
      .finally(() => {
        this.refreshPromise = null;
      });
    return this.refreshPromise;
  }

  /** 注册请求/响应拦截器，保证所有业务请求自动参与 session 刷新流程。 */
  private setupInterceptors(): void {
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        const token = getAccessToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    this.client.interceptors.response.use(
      (response) => response.data,
      async (error: AxiosError<ApiErrorResponse>) => {
        const status = error.response?.status;
        const originalRequest = error.config as RetryRequestConfig | undefined;

        if (status === HTTP_STATUS.UNAUTHORIZED && originalRequest && !originalRequest._retry) {
          // 每个请求只重试一次，避免 refresh 失败时形成 401 循环。
          originalRequest._retry = true;
          const nextToken = await this.refreshAccessToken();
          if (nextToken) {
            originalRequest.headers.Authorization = `Bearer ${nextToken}`;
            return this.client(originalRequest);
          }
        }

        const message = normalizeErrorMessage(error.response?.data?.detail);

        if (status === HTTP_STATUS.UNAUTHORIZED && !window.location.pathname.includes('/login')) {
          useAuthStore.getState().logout();
          window.location.href = '/login';
        }

        return Promise.reject({
          name: 'ApiError',
          status: status || 0,
          message,
          code: status?.toString(),
        });
      }
    );
  }

  async get<T>(url: string, config?: Record<string, unknown>): Promise<T> {
    return this.client.get(url, config);
  }

  async post<T>(url: string, data?: unknown, config?: Record<string, unknown>): Promise<T> {
    return this.client.post(url, data, config);
  }

  async put<T>(url: string, data?: unknown, config?: Record<string, unknown>): Promise<T> {
    return this.client.put(url, data, config);
  }

  async delete<T>(url: string, config?: Record<string, unknown>): Promise<T> {
    return this.client.delete(url, config);
  }

  async upload<T>(url: string, formData: FormData): Promise<T> {
    return this.client.post(url, formData, {
      headers: { 'Content-Type': undefined },
    });
  }
}

export const apiClient = new ApiClient();
