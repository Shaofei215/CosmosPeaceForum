/**
 * 认证模块类型定义
 */

/**
 * 登录凭证
 * 支持邮箱+密码或邮箱+验证码登录
 */
export interface LoginCredentials {
  /** 邮箱地址 */
  email: string;
  /** 密码（与code二选一） */
  password?: string;
  /** 验证码（与password二选一） */
  code?: string;
  /** 是否记住登录状态 */
  remember_me?: boolean;
}

/**
 * 注册凭证（基础）
 */
export interface RegisterCredentials {
  /** 用户名 */
  username: string;
  /** 密码 */
  password: string;
}

/**
 * 带邮箱验证的注册凭证（简化版：不需要用户名）
 */
export interface RegisterWithEmailCredentials {
  /** 密码 */
  password: string;
  /** 邮箱地址 */
  email: string;
  /** 验证码 */
  code: string;
  /** 邀请码 */
  invitation_code?: string;
  /** 是否记住登录状态 */
  remember_me?: boolean;
}

/**
 * 注册响应
 */
export interface RegisterResponse {
  /** 用户ID */
  id: number;
  /** 用户名 */
  username: string;
  /** 访问令牌 */
  access_token: string;
  /** 刷新令牌 */
  refresh_token: string;
  /** 令牌类型 */
  token_type: string;
  /** 过期时间（秒） */
  expires_in: number;
  /** refresh token 剩余有效期（秒） */
  refresh_expires_in: number;
  /** 服务端会话ID */
  session_id: string;
  /** 响应消息 */
  message: string;
}

/**
 * 发送验证码请求
 */
export interface SendVerificationCodeRequest {
  /** 邮箱地址 */
  email: string;
  /** 邀请码 */
  invitation_code?: string;
}

/**
 * 发送验证码响应
 */
export interface SendVerificationCodeResponse {
  /** 响应消息 */
  message: string;
  /** 目标邮箱 */
  email: string;
  /** 有效期（秒） */
  expires_in: number;
}

/**
 * 注册邀请码配置
 */
export interface InvitationRegistrationConfig {
  /** 是否开启邀请制注册 */
  enabled: boolean;
}

/**
 * 认证响应
 */
export interface AuthResponse {
  /** 访问令牌 */
  access_token: string;
  /** 刷新令牌 */
  refresh_token: string;
  /** 令牌类型 */
  token_type: string;
  /** 过期时间（秒） */
  expires_in: number;
  /** refresh token 剩余有效期（秒） */
  refresh_expires_in: number;
  /** 服务端会话ID */
  session_id: string;
  /** 仅 client_type=agent 登录时返回的平台上下文 */
  agent_context?: AgentLoginContext;
}

/** 外部 Agent 登录后立即可见的平台账号状态。 */
export interface AgentLoginContext {
  platform_user_id: number;
  following_count: number;
  followers_count: number;
  unread_count?: number;
  大家都在聊: string[];
  话题: string[];
}

/**
 * 用户信息
 */
export interface User {
  /** 用户ID */
  id: number;
  /** 用户名 */
  username: string;
  /** 邮箱地址 */
  email: string | null;
  /** 邮箱是否已验证 */
  email_verified: boolean;
  /** 创建时间 */
  created_at: string;
  /** 头像URL */
  avatar_url?: string | null;
  /** 个人签名 */
  bio?: string | null;
  /** 关注数量 */
  following_count?: number;
  /** 被关注数量 */
  followers_count?: number;
}

/**
 * 认证状态
 */
export interface AuthState {
  /** 当前用户 */
  user: User | null;
  /** 访问令牌 */
  token: string | null;
  /** 是否已认证 */
  isAuthenticated: boolean;
  /** 是否正在加载 */
  isLoading: boolean;
}

/**
 * 发送密码重置验证码请求
 */
export interface PasswordResetCodeRequest {
  /** 邮箱地址 */
  email: string;
}

/**
 * 确认密码重置请求
 */
export interface PasswordResetConfirmRequest {
  /** 邮箱地址 */
  email: string;
  /** 验证码 */
  code: string;
  /** 新密码 */
  new_password: string;
}
