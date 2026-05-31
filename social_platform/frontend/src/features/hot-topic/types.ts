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

export interface HotTopicFormData {
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
  updated_at: string;
}

export type HotTopicSettingsUpdate = Partial<Omit<HotTopicSettings, 'id' | 'updated_at'>>;

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
