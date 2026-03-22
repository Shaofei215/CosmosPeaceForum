/**
 * API客户端
 * 封装axios，提供统一的请求处理和错误处理
 */

import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { API_CONFIG, HTTP_STATUS } from '@/shared/config/api';
import type { ApiError, ApiErrorException } from '@/shared/types/api';

/**
 * API客户端类
 * 封装axios实例，提供统一的请求拦截和响应处理
 */
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

  /**
   * 设置请求和响应拦截器
   */
  private setupInterceptors(): void {
    // 请求拦截器：添加认证Token
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

    // 响应拦截器：统一错误处理
    this.client.interceptors.response.use(
      (response) => response.data,
      (error: AxiosError<ApiError>) => {
        const status = error.response?.status;
        const message = error.response?.data?.detail || '请求失败，请稍后重试';

        // 处理401未授权：清除token并跳转到登录页
        if (status === HTTP_STATUS.UNAUTHORIZED) {
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          window.location.href = '/login';
        }

        // 构造统一的错误对象
        const apiError: ApiErrorException = {
          name: 'ApiErrorException',
          status: status || 0,
          message,
          code: status?.toString(),
        };

        return Promise.reject(apiError);
      }
    );
  }

  /**
   * GET请求
   *
   * @param url - 请求路径
   * @param config - 请求配置
   * @returns 响应数据
   */
  async get<T>(url: string, config?: Record<string, unknown>): Promise<T> {
    return this.client.get(url, config);
  }

  /**
   * POST请求
   *
   * @param url - 请求路径
   * @param data - 请求体数据
   * @param config - 请求配置
   * @returns 响应数据
   */
  async post<T>(url: string, data?: unknown, config?: Record<string, unknown>): Promise<T> {
    return this.client.post(url, data, config);
  }

  /**
   * PUT请求
   *
   * @param url - 请求路径
   * @param data - 请求体数据
   * @param config - 请求配置
   * @returns 响应数据
   */
  async put<T>(url: string, data?: unknown, config?: Record<string, unknown>): Promise<T> {
    return this.client.put(url, data, config);
  }

  /**
   * DELETE请求
   *
   * @param url - 请求路径
   * @param config - 请求配置
   * @returns 响应数据
   */
  async delete<T>(url: string, config?: Record<string, unknown>): Promise<T> {
    return this.client.delete(url, config);
  }
}

/**
 * API客户端实例
 */
export const apiClient = new ApiClient();
