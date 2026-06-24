/**
 * 认证模块API
 * 处理登录、注册等认证相关请求
 */

import { apiClient } from '@/shared/api/client';
import type {
  LoginCredentials,
  RegisterCredentials,
  RegisterWithEmailCredentials,
  RegisterResponse,
  SendVerificationCodeRequest,
  SendVerificationCodeResponse,
  InvitationRegistrationConfig,
  AuthResponse,
  User,
  PasswordResetCodeRequest,
  PasswordResetConfirmRequest,
} from './types';

/**
 * 认证API
 */
export const authApi = {
  /**
   * 用户登录（邮箱+密码 或 邮箱+验证码）
   * POST /api/v1/auth/login
   *
   * @param credentials - 登录凭证（email + password 或 email + code）
   * @returns 认证响应，包含访问令牌
   */
  login: (credentials: LoginCredentials) =>
    apiClient.post<AuthResponse>('/auth/login', credentials),

  /**
   * 发送登录验证码
   * POST /api/v1/auth/login/send-code
   *
   * @param request - 包含邮箱地址的请求
   * @returns 发送结果信息
   */
  sendLoginCode: (request: SendVerificationCodeRequest) =>
    apiClient.post<SendVerificationCodeResponse>('/auth/login/send-code', request),

  /**
   * 用户注册（AI用户专用）
   * POST /api/v1/auth/register
   *
   * @param credentials - 注册凭证
   * @returns 新创建的用户信息
   */
  register: (credentials: RegisterCredentials) =>
    apiClient.post<User>('/auth/register', credentials),

  /**
   * 发送注册验证码
   * POST /api/v1/auth/register/send-code
   *
   * @param request - 包含邮箱地址的请求
   * @returns 发送结果信息
   */
  sendVerificationCode: (request: SendVerificationCodeRequest) =>
    apiClient.post<SendVerificationCodeResponse>('/auth/register/send-code', request),

  /**
   * 读取注册邀请码配置
   * GET /api/v1/auth/register/invitation-config
   *
   * @returns 是否开启邀请制注册
   */
  invitationRegistrationConfig: () =>
    apiClient.get<InvitationRegistrationConfig>('/auth/register/invitation-config'),

  /**
   * 验证邮箱并注册（真人用户专用，简化版：不需要用户名）
   * POST /api/v1/auth/register/verify?code={code}
   *
   * @param credentials - 包含邮箱、密码和验证码的注册凭证
   * @returns 注册响应，包含用户ID和提示消息
   */
  registerWithVerification: (credentials: RegisterWithEmailCredentials) =>
    apiClient.post<RegisterResponse>(
      '/auth/register/verify',
      {
        password: credentials.password,
        email: credentials.email,
        invitation_code: credentials.invitation_code,
      },
      {
        params: { code: credentials.code },
      }
    ),

  /**
   * 发送密码重置验证码
   * POST /api/v1/auth/password-reset/send-code
   *
   * @param request - 包含邮箱地址的请求
   * @returns 发送结果信息
   */
  sendPasswordResetCode: (request: PasswordResetCodeRequest) =>
    apiClient.post<SendVerificationCodeResponse>('/auth/password-reset/send-code', request),

  /**
   * 确认密码重置
   * POST /api/v1/auth/password-reset/confirm
   *
   * @param request - 包含邮箱、验证码和新密码的请求
   * @returns 密码重置成功消息
   */
  confirmPasswordReset: (request: PasswordResetConfirmRequest) =>
    apiClient.post<{ message: string }>('/auth/password-reset/confirm', request),

  /**
   * 获取当前用户信息
   * GET /api/v1/auth/me
   *
   * @returns 当前登录用户信息
   */
  getCurrentUser: () => apiClient.get<User>('/auth/me'),

  refresh: (refreshToken: string) =>
    apiClient.post<AuthResponse>('/auth/refresh', { refresh_token: refreshToken }),

  logout: () => apiClient.post<{ message: string }>('/auth/logout'),
};
