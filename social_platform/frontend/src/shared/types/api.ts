/**
 * API类型定义
 * 定义通用的API响应类型
 */

/**
 * 标准API响应结构
 */
export interface ApiResponse<T> {
  /** 状态码 */
  code: number;
  /** 消息 */
  message: string;
  /** 数据 */
  data: T;
}

/**
 * 分页元数据
 */
export interface PaginationMeta {
  /** 当前页码 */
  page: number;
  /** 每页记录数 */
  page_size: number;
  /** 总记录数 */
  total: number;
  /** 总页数 */
  total_pages: number;
  /** 是否有下一页 */
  has_next: boolean;
  /** 是否有上一页 */
  has_prev: boolean;
}

/**
 * 分页响应结构
 */
export interface PaginatedResponse<T> {
  /** 状态码 */
  code: number;
  /** 消息 */
  message: string;
  /** 数据列表 */
  data: T[];
  /** 分页信息 */
  pagination: PaginationMeta;
}

/**
 * 错误响应结构
 */
export interface ApiError {
  /** 错误详情 */
  detail: unknown;
}

/**
 * API错误类
 */
export class ApiErrorException extends Error {
  constructor(
    public status: number,
    public message: string,
    public code?: string
  ) {
    super(message);
    this.name = 'ApiErrorException';
  }
}

/**
 * 请求配置选项
 */
export interface RequestConfig {
  /** 是否跳过错误处理 */
  skipErrorHandler?: boolean;
  /** 是否跳过认证 */
  skipAuth?: boolean;
  /** 重试次数 */
  retryCount?: number;
  /** 超时时间 */
  timeout?: number;
}
