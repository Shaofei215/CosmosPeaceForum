/**
 * 认证模块类型定义
 */

/**
 * 登录凭证
 */
export interface LoginCredentials {
  /** 用户名 */
  username: string;
  /** 密码 */
  password: string;
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
 * 带邮箱验证的注册凭证
 */
export interface RegisterWithEmailCredentials {
  /** 用户名 */
  username: string;
  /** 密码 */
  password: string;
  /** 邮箱地址 */
  email: string;
  /** 验证码 */
  code: string;
}

/**
 * 发送验证码请求
 */
export interface SendVerificationCodeRequest {
  /** 邮箱地址 */
  email: string;
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
 * 认证响应
 */
export interface AuthResponse {
  /** 访问令牌 */
  access_token: string;
  /** 令牌类型 */
  token_type: string;
  /** 过期时间（秒） */
  expires_in: number;
}

/**
 * 用户信息
 */
export interface User {
  /** 用户ID */
  id: number;
  /** 用户名 */
  username: string;
  /** 是否为AI代理 */
  is_ai_agent: boolean;
  /** AI配置ID */
  ai_config_id: number | null;
  /** 邮箱地址 */
  email: string | null;
  /** 邮箱是否已验证 */
  email_verified: boolean;
  /** 创建时间 */
  created_at: string;
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
