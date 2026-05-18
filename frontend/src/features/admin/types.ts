export const ADMIN_PERMISSIONS = [
  'view_dashboard',
  'manage_users',
  'manage_content',
  'manage_admins',
  'view_logs',
] as const;

export type AdminPermission = (typeof ADMIN_PERMISSIONS)[number];

export interface AdminUser {
  id: number;
  username: string;
  permissions: AdminPermission[];
  is_active: boolean;
  is_super_admin: boolean;
  must_change_credentials: boolean;
  created_at: string;
  updated_at: string;
  last_login: string | null;
}

export interface AdminLoginRequest {
  username: string;
  password: string;
}

export interface AdminLoginResponse {
  access_token: string;
  token_type: string;
  admin: AdminUser;
}

export interface AdminProfileUpdateRequest {
  current_password: string;
  username?: string;
  new_password?: string;
}

export interface AdminCreateRequest {
  username: string;
  password: string;
  permissions: AdminPermission[];
  is_active: boolean;
  is_super_admin: boolean;
}

export interface AdminUpdateRequest {
  permissions?: AdminPermission[];
  is_active?: boolean;
  is_super_admin?: boolean;
  new_password?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export interface DashboardStats {
  total_users: number;
  daily_active_users: number;
  total_posts: number;
  total_comments: number;
  banned_users: number;
  active_restrictions: number;
  active_threads: number;
  process_memory_mb: number;
  load_average_1m: number;
}

export interface UserModerationStatus {
  account_banned: boolean;
  account_banned_at: string | null;
  account_ban_reason: string | null;
  publish_banned_until: string | null;
  publish_ban_reason: string | null;
  comment_banned_until: string | null;
  comment_ban_reason: string | null;
  interaction_banned_until: string | null;
  interaction_ban_reason: string | null;
  updated_at: string | null;
}

export interface UserWithModeration {
  id: number;
  username: string | null;
  email: string | null;
  bio: string | null;
  avatar_url: string | null;
  is_ai_agent: boolean;
  ai_config_id: number | null;
  created_at: string;
  following_count: number;
  followers_count: number;
  post_count: number;
  comment_count: number;
  moderation: UserModerationStatus;
}

export interface UserModerationUpdateRequest {
  account_banned?: boolean;
  account_ban_reason?: string;
  publish_banned_until?: string | null;
  publish_ban_reason?: string;
  comment_banned_until?: string | null;
  comment_ban_reason?: string;
  interaction_banned_until?: string | null;
  interaction_ban_reason?: string;
}

export interface UserModerationResponse extends UserModerationStatus {
  user_id: number;
}

export interface UserModerationBatchUpdateRequest {
  user_ids: number[];
  moderation: UserModerationUpdateRequest;
}

export interface UserModerationBatchUpdateResponse {
  updated_count: number;
  items: UserModerationResponse[];
}

export interface AdminAnnouncementRequest {
  content: string;
}

export interface AdminAnnouncementResponse {
  recipient_count: number;
}

export interface ContentItem {
  id: number;
  type: string;
  author_id: number;
  author_username: string | null;
  title: string | null;
  content: string;
  created_at: string;
  like_count: number;
  comment_count: number | null;
  reply_count: number | null;
}

export interface ContentDeleteRequest {
  reason?: string;
  notify_author: boolean;
}

export interface OperationLog {
  id: number;
  operator_id: number | null;
  operator_username: string | null;
  action: string;
  target_type: string;
  target_id: number | null;
  details: string;
  created_at: string;
}

export interface TerminalLog {
  timestamp: string;
  level: string;
  message: string;
}

export interface TerminalLogList {
  items: TerminalLog[];
  total: number;
}
