/**
 * 平台管理员类型定义。
 *
 * 登录响应携带 access/refresh token 和 session_id，供管理员短会话与记住我模式使用。
 */

export const ADMIN_PERMISSIONS = [
  'view_dashboard',
  'manage_users',
  'manage_content',
  'manage_hot_topics',
  'manage_admins',
  'view_logs',
] as const;

export type AdminPermission = (typeof ADMIN_PERMISSIONS)[number];

export interface AdminUser {
  id: number;
  username: string;
  email: string | null;
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
  remember_me?: boolean;
}

export interface AdminLoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  refresh_expires_in: number;
  session_id: string;
  admin: AdminUser;
}

export interface AdminProfileUpdateRequest {
  current_password: string;
  username?: string;
  new_password?: string;
}

export interface AdminCreateRequest {
  username: string;
  email?: string;
  password: string;
  permissions: AdminPermission[];
  is_active: boolean;
  is_super_admin: boolean;
}

export interface AdminUpdateRequest {
  email?: string | null;
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
  cpu_usage_percent: number;
  memory_usage_percent: number;
}

export interface UserModerationStatus {
  account_banned: boolean;
  account_banned_at: string | null;
  account_ban_reason: string | null;
  publish_banned_until: string | null;
  publish_violation_count: number;
  publish_permanently_banned: boolean;
  publish_ban_reason: string | null;
  comment_banned_until: string | null;
  comment_violation_count: number;
  comment_permanently_banned: boolean;
  comment_ban_reason: string | null;
  interaction_banned_until: string | null;
  interaction_violation_count: number;
  interaction_permanently_banned: boolean;
  interaction_ban_reason: string | null;
  avatar_banned_until: string | null;
  avatar_violation_count: number;
  avatar_permanently_banned: boolean;
  avatar_ban_reason: string | null;
  username_banned_until: string | null;
  username_violation_count: number;
  username_permanently_banned: boolean;
  username_ban_reason: string | null;
  bio_banned_until: string | null;
  bio_violation_count: number;
  bio_permanently_banned: boolean;
  bio_ban_reason: string | null;
  updated_at: string | null;
}

export interface UserWithModeration {
  id: number;
  username: string | null;
  email: string | null;
  bio: string | null;
  avatar_url: string | null;
  created_at: string;
  following_count: number;
  followers_count: number;
  post_count: number;
  comment_count: number;
  moderation: UserModerationStatus;
}

export type ViolationCategory =
  | 'publish'
  | 'comment'
  | 'interaction'
  | 'avatar'
  | 'username'
  | 'bio'
  | 'account';

export interface UserViolationRequest {
  category: ViolationCategory;
  reason?: string;
}

export interface UserModerationResponse extends UserModerationStatus {
  user_id: number;
}

export interface UserViolationBatchRequest extends UserViolationRequest {
  user_ids: number[];
}

export interface UserModerationBatchUpdateResponse {
  updated_count: number;
  items: UserModerationResponse[];
}

export interface InvitationCode {
  id: number;
  email: string;
  code: string;
  prefix: string;
  status: 'unused' | 'used';
  created_at: string;
  updated_at: string;
  created_by_admin_id: number | null;
  created_by_admin_username: string | null;
  used_by_user_id: number | null;
  used_by_username: string | null;
  used_at: string | null;
}

export interface InvitationCodeCreateRequest {
  email: string;
  prefix: string;
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
  post_id: number | null;
  author_id: number;
  author_username: string | null;
  title: string | null;
  content: string;
  created_at: string;
  created_by_agent: boolean;
  like_count: number;
  comment_count: number | null;
  reply_count: number | null;
  moderation_status: string;
  archived_at: string | null;
  archive_reason: string | null;
}

export interface ContentDeleteRequest {
  reason?: string;
  notify_author: boolean;
}

export interface ContentReportReason {
  reason: string;
  count: number;
}

export interface ReportedContentItem extends ContentItem {
  report_count: number;
  report_reasons: ContentReportReason[];
  last_reported_at: string;
  source: string;
}

export interface ReportedUserItem {
  id: number;
  username: string | null;
  bio: string | null;
  avatar_url: string | null;
  created_at: string;
  report_count: number;
  report_reasons: ContentReportReason[];
  last_reported_at: string;
}

export interface ModerationAppealItem {
  id: number;
  notification_id: number;
  appellant_id: number;
  appellant_username: string | null;
  target_type: string;
  target_id: number;
  target_label: string;
  target_content: string | null;
  action_label: string;
  moderation_reason: string | null;
  appeal_reason: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ModerationAppealRejectRequest {
  reason: string;
}

export interface ReportReleaseResponse {
  released_count: number;
}

export interface ContentModerationLLMSettings {
  id: number;
  enabled: boolean;
  llm_base_url: string | null;
  llm_model_name: string | null;
  llm_api_key: string | null;
  updated_at: string;
}

export type ContentModerationLLMSettingsUpdate = Partial<
  Omit<ContentModerationLLMSettings, 'id' | 'updated_at'>
>;

export interface ContentModerationLLMPromptConfig {
  key: string;
  name: string;
  description: string;
  value: string;
  default_value: string;
  updated_at: string;
}

export type HotTopicSource = 'manual' | 'agent';
export type HotTopicStatus = 'active' | 'draft' | 'archived';
export type HotTopicPublishPolicy = 'auto' | 'draft';

export interface HotTopic {
  id: number;
  title: string;
  search_query: string;
  summary: string | null;
  source: HotTopicSource;
  status: HotTopicStatus;
  rank: number;
  generation_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface HotTopicRequest {
  title: string;
  search_query: string;
  summary?: string | null;
  source?: HotTopicSource;
  status?: HotTopicStatus;
  rank?: number;
}

export interface HotTopicSettings {
  id: number;
  agent_enabled: boolean;
  agent_interval_minutes: number;
  publish_policy: HotTopicPublishPolicy;
  llm_base_url: string | null;
  llm_model_name: string | null;
  llm_api_key: string | null;
  web_search_enabled: boolean;
  tavily_api_key: string | null;
  history_limit: number;
  max_llm_rounds: number;
  updated_at: string;
}

export type HotTopicSettingsUpdate = Partial<Omit<HotTopicSettings, 'id' | 'updated_at'>>;

export interface HotTopicPromptConfig {
  key: string;
  name: string;
  description: string;
  value: string;
  default_value: string;
  updated_at: string;
}

export interface HotTopicGeneration {
  id: number;
  status: 'pending' | 'success' | 'failed';
  publish_policy: HotTopicPublishPolicy;
  input_snapshot: string | null;
  output_json: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface HotTopicGenerationRunResponse {
  generation: HotTopicGeneration;
  topics: HotTopic[];
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
