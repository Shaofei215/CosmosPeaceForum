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
  created_at: string;
  updated_at: string;
}

export interface AgentCreate {
  name: string;
  username: string;
  monthly_logins?: number;
  personal_signature?: string;
  personality_prompt?: string;
  knows_ids?: number[];
  is_active?: boolean;
}

export interface AgentUpdate {
  name?: string;
  monthly_logins?: number;
  personal_signature?: string;
  personality_prompt?: string;
  knows_ids?: number[];
  is_active?: boolean;
}

export interface AgentListResponse {
  items: AgentConfig[];
  total: number;
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
