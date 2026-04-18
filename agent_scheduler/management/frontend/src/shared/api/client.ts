import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { API_CONFIG, HTTP_STATUS } from '@/shared/config/api';

class ApiClient {
  private client: AxiosInstance;

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

  private setupInterceptors(): void {
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        const token = localStorage.getItem('token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    this.client.interceptors.response.use(
      (response) => response.data,
      (error: AxiosError<{ detail?: string }>) => {
        const status = error.response?.status;
        const message = error.response?.data?.detail || '请求失败，请稍后重试';

        if (status === HTTP_STATUS.UNAUTHORIZED && !window.location.pathname.includes('/login')) {
          localStorage.removeItem('token');
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
