import { apiClient } from '@/shared/api/client';
import type {
  AdminCreateRequest, AdminUpdateRequest, AdminUser,
  AgentConfig, AgentCreate, AgentUpdate, AgentListResponse, AgentRelationUpdate,
  AgentRuntimeStatusResponse, PromptInjectionRequest, AgentAppLoginResponse,
  DashboardStats,
  ModelConfig, ModelConfigCreate, ModelConfigUpdate,
  SystemConfig, PromptConfig, OperationLogListResponse, MessageResponse,
  EmbeddingConfig, EmbeddingConfigCreate, EmbeddingConfigUpdate,
  ChunkModelConfig, ChunkModelConfigCreate, ChunkModelConfigUpdate,
  MemoryListResponse, MemoryOwnerListResponse, MemoryUploadRequest, MemoryBatchUploadRequest,
  MemoryUpdateRequest, MemoryUpdateResponse,
  TerminalLog, TerminalLogListResponse,
} from '@/shared/types/api';

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export const adminApi = {
  list: (skip = 0, limit = 100) =>
    apiClient.get<PaginatedResponse<AdminUser>>(`/admins/?skip=${skip}&limit=${limit}`),

  create: (data: AdminCreateRequest) =>
    apiClient.post<AdminUser>('/admins/', data),

  update: (id: number, data: AdminUpdateRequest) =>
    apiClient.put<AdminUser>(`/admins/${id}`, data),

  remove: (id: number) =>
    apiClient.delete<MessageResponse>(`/admins/${id}`),
};

export const agentApi = {
  list: (skip = 0, limit = 100) =>
    apiClient.get<AgentListResponse>(`/agents/?skip=${skip}&limit=${limit}`),

  getOne: (id: number) =>
    apiClient.get<AgentConfig>(`/agents/${id}`),

  create: (data: AgentCreate) =>
    apiClient.post<AgentConfig>('/agents/', data),

  update: (id: number, data: AgentUpdate) =>
    apiClient.put<AgentConfig>(`/agents/${id}`, data),

  remove: (id: number) =>
    apiClient.delete<MessageResponse>(`/agents/${id}`),

  restart: (id: number) =>
    apiClient.post<MessageResponse>(`/agents/${id}/restart`),

  start: (id: number) =>
    apiClient.post<MessageResponse>(`/agents/${id}/start`),

  stop: (id: number) =>
    apiClient.post<MessageResponse>(`/agents/${id}/stop`),

  appLogin: (id: number) =>
    apiClient.post<AgentAppLoginResponse>(`/agents/${id}/app-login`),

  batchStart: (ids: number[]) =>
    apiClient.post<MessageResponse>('/agents/batch-start', ids),

  batchStop: (ids: number[]) =>
    apiClient.post<MessageResponse>('/agents/batch-stop', ids),

  batchDelete: (ids: number[]) =>
    apiClient.post<MessageResponse>('/agents/batch-delete', ids),

  injectPrompt: (data: PromptInjectionRequest) =>
    apiClient.post<MessageResponse>('/agents/prompt-injections', data),

  importAgents: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.upload<AgentListResponse>('/agents/import', formData);
  },

  uploadAvatar: (id: number, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.upload<MessageResponse>(`/agents/${id}/avatar`, formData);
  },

  updateRelation: (id: number, data: AgentRelationUpdate) =>
    apiClient.put<AgentConfig>(`/agents/${id}/relation`, data),

  dashboardStats: () =>
    apiClient.get<DashboardStats>('/agents/dashboard-stats'),

  runtimeStatus: () =>
    apiClient.get<AgentRuntimeStatusResponse>('/agents/runtime-status'),
};

export const modelApi = {
  list: () =>
    apiClient.get<ModelConfig[]>('/models/'),

  getOne: (id: number) =>
    apiClient.get<ModelConfig>(`/models/${id}`),

  create: (data: ModelConfigCreate) =>
    apiClient.post<ModelConfig>('/models/', data),

  update: (id: number, data: ModelConfigUpdate) =>
    apiClient.put<ModelConfig>(`/models/${id}`, data),

  remove: (id: number) =>
    apiClient.delete<MessageResponse>(`/models/${id}`),

  toggle: (id: number) =>
    apiClient.put<ModelConfig>(`/models/${id}/toggle`, {}),
};

export const embeddingApi = {
  get: () =>
    apiClient.get<EmbeddingConfig>('/embeddings/'),

  create: (data: EmbeddingConfigCreate) =>
    apiClient.post<EmbeddingConfig>('/embeddings/', data),

  update: (data: EmbeddingConfigUpdate) =>
    apiClient.put<EmbeddingConfig>('/embeddings/', data),
};

export const systemApi = {
  list: () =>
    apiClient.get<SystemConfig[]>('/system/'),

  update: (key: string, value: string) =>
    apiClient.put<SystemConfig>(`/system/${key}`, { value }),

  restart: () =>
    apiClient.post<MessageResponse>('/system/restart'),
};

export const promptApi = {
  list: () =>
    apiClient.get<PromptConfig[]>('/prompts/'),

  update: (key: string, value: string) =>
    apiClient.put<PromptConfig>(`/prompts/${key}`, { value }),

  reset: (key: string) =>
    apiClient.post<PromptConfig>(`/prompts/${key}/reset`),
};

export const logApi = {
  list: (skip = 0, limit = 100, agentId?: number) => {
    const params = new URLSearchParams({
      skip: String(skip),
      limit: String(limit),
    });
    if (agentId !== undefined) params.set('agent_id', String(agentId));
    return apiClient.get<OperationLogListResponse>(`/logs/?${params.toString()}`);
  },
};

export const chunkModelApi = {
  list: () =>
    apiClient.get<ChunkModelConfig[]>('/chunk-models/'),

  getOne: (id: number) =>
    apiClient.get<ChunkModelConfig>(`/chunk-models/${id}`),

  create: (data: ChunkModelConfigCreate) =>
    apiClient.post<ChunkModelConfig>('/chunk-models/', data),

  update: (id: number, data: ChunkModelConfigUpdate) =>
    apiClient.put<ChunkModelConfig>(`/chunk-models/${id}`, data),

  remove: (id: number) =>
    apiClient.delete<MessageResponse>(`/chunk-models/${id}`),

  toggle: (id: number) =>
    apiClient.put<ChunkModelConfig>(`/chunk-models/${id}/toggle`, {}),
};

export const memoryApi = {
  list: (skip = 0, limit = 100, owner_id?: number) => {
    let url = `/memories/?skip=${skip}&limit=${limit}`;
    if (owner_id !== undefined) url += `&owner_id=${owner_id}`;
    return apiClient.get<MemoryListResponse>(url);
  },

  listOwners: () =>
    apiClient.get<MemoryOwnerListResponse>('/memories/owners'),

  search: (query: string, skip = 0, limit = 50, ownerId?: number) => {
    const params = new URLSearchParams({ query, skip: String(skip), limit: String(limit) });
    if (ownerId !== undefined) params.set('owner_id', String(ownerId));
    return apiClient.get<MemoryListResponse>(`/memories/search?${params.toString()}`);
  },

  uploadSingle: (data: MemoryUploadRequest) =>
    apiClient.post<MessageResponse>('/memories/upload', data, { timeout: 300000 }),

  uploadBatch: (data: MemoryBatchUploadRequest) =>
    apiClient.post<MessageResponse>('/memories/upload-batch', data),

  deleteMemory: (memoryId: string) =>
    apiClient.delete<MessageResponse>(`/memories/${memoryId}`),

  updateMemory: (memoryId: string, data: MemoryUpdateRequest) =>
    apiClient.put<MemoryUpdateResponse>(`/memories/${memoryId}`, data),

  clearUserMemories: (ownerId: number) =>
    apiClient.delete<MessageResponse>(`/memories/user/${ownerId}`),
};

interface TerminalLogParams {
  count?: number;
  level?: string;
  keyword?: string;
  role?: string;
}

export const terminalLogApi = {
  list: (params: TerminalLogParams = {}) =>
    apiClient.get<TerminalLogListResponse>('/logs/terminal', { params }),

  recent: (count = 50, role?: string, keyword?: string, level?: string) => {
    const params = new URLSearchParams({ count: String(count) });
    if (role) params.set('role', role);
    if (keyword) params.set('keyword', keyword);
    if (level) params.set('level', level);
    return apiClient.get<{ items: TerminalLog[]; total: number }>(
      `/terminal-logs/recent?${params.toString()}`,
    );
  },

  clear: () =>
    apiClient.delete<MessageResponse>('/logs/terminal'),
};
