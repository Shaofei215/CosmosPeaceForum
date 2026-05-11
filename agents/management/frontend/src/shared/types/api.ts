export interface AdminUser {
  id: number;
  username: string;
  created_at: string;
  last_login: string | null;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface UpdateProfileRequest {
  username?: string;
  current_password: string;
  new_password?: string;
}

export interface AgentConfig {
  id: number;
  name: string;
  username: string;
  monthly_logins: number;
  personal_signature: string;
  personality_prompt: string;
  knows_ids: number[];
  is_active: boolean;
  app_platform_user_id: number | null;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentCreate {
  name: string;
  username: string;
  monthly_logins?: number;
  personal_signature?: string;
  personality_prompt?: string;
  is_active?: boolean;
}

export interface AgentUpdate {
  name?: string;
  monthly_logins?: number;
  personal_signature?: string;
  personality_prompt?: string;
  is_active?: boolean;
}

export interface AgentRelationUpdate {
  knows_ids: number[];
  bidirectional?: boolean;
}

export interface AgentListResponse {
  items: AgentConfig[];
  total: number;
}

export interface DashboardStats {
  total_roles: number;
  enabled_roles: number;
  daily_active_roles: number;
  cpu_usage_percent: number;
  memory_usage_percent: number;
}

export interface ModelConfig {
  id: number;
  name: string;
  provider: string;
  base_url: string;
  model_name: string;
  temperature: number;
  is_active: boolean;
  max_token: number;
  created_at: string;
  updated_at: string;
}

export interface ModelConfigCreate {
  name: string;
  provider: string;
  api_key: string;
  base_url?: string;
  model_name: string;
  temperature?: number;
  is_active?: boolean;
  max_token?: number;
}

export interface ModelConfigUpdate {
  name?: string;
  provider?: string;
  api_key?: string;
  base_url?: string;
  model_name?: string;
  temperature?: number;
  is_active?: boolean;
  max_token?: number;
}

export interface SystemConfig {
  id: number;
  key: string;
  value: string;
  description: string;
  updated_at: string;
}

export interface OperationLog {
  id: number;
  operator_id: number;
  action: string;
  target_type: string;
  target_id: number | null;
  details: string;
  created_at: string;
}

export interface OperationLogListResponse {
  items: OperationLog[];
  total: number;
}

export interface MessageResponse {
  message: string;
}

export interface EmbeddingConfig {
  id: number;
  base_url: string;
  api_key: string;
  model_name: string;
  dimension: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmbeddingConfigCreate {
  base_url?: string;
  api_key?: string;
  model_name?: string;
  dimension?: number;
  is_active?: boolean;
}

export interface EmbeddingConfigUpdate {
  base_url?: string;
  api_key?: string;
  model_name?: string;
  dimension?: number;
  is_active?: boolean;
}

export interface ChunkModelConfig {
  id: number;
  name: string;
  provider: string;
  base_url: string;
  model_name: string;
  temperature: number;
  is_active: boolean;
  max_token: number;
  created_at: string;
  updated_at: string;
}

export interface ChunkModelConfigCreate {
  name: string;
  provider: string;
  api_key: string;
  base_url?: string;
  model_name: string;
  temperature?: number;
  is_active?: boolean;
  max_token?: number;
}

export interface ChunkModelConfigUpdate {
  name?: string;
  provider?: string;
  api_key?: string;
  base_url?: string;
  model_name?: string;
  temperature?: number;
  is_active?: boolean;
  max_token?: number;
}

export interface MemoryChunk {
  id: string;
  owner_id: number;
  owner_username: string;
  content: string;
  semantic_timestamp: number;
  system_timestamp: number;
  memory_coefficient: number;
  memory_type: 'normal' | 'static';
  created_at: string;
}

export interface MemoryListResponse {
  items: MemoryChunk[];
  total: number;
}

export interface MemoryOwnerSummary {
  owner_id: number;
  owner_username: string;
  agent_id: number | null;
  agent_name: string | null;
  memory_count: number;
  latest_system_timestamp: number;
  latest_semantic_timestamp: number;
  has_agent_config: boolean;
}

export interface MemoryOwnerListResponse {
  items: MemoryOwnerSummary[];
  total: number;
}

export interface MemoryUploadRequest {
  owner_id: number;
  content: string;
  chunk_mode: 'auto' | 'llm' | 'none';
  memory_type?: 'normal' | 'static';
  semantic_time?: string;
  memory_coefficient?: number;
  personality_prompt?: string;
  enable_rag_on_chunking?: boolean;
}

export interface MemoryBatchUploadRequest {
  owner_ids: number[];
  content: string;
  chunk_mode: 'auto' | 'llm' | 'none';
  memory_type?: 'normal' | 'static';
  semantic_time?: string;
  memory_coefficient?: number;
  enable_rag_on_chunking?: boolean;
}

export interface TerminalLog {
  timestamp: string;
  level: string;
  message: string;
}

export interface TerminalLogListResponse {
  items: TerminalLog[];
  total: number;
}
