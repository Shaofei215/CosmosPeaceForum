import { apiClient } from '@/shared/api/client';
import type {
  AgentConfig, AgentCreate, AgentUpdate, AgentListResponse, AgentRelationUpdate,
  ModelConfig, ModelConfigCreate, ModelConfigUpdate,
  SystemConfig, OperationLogListResponse, MessageResponse,
  EmbeddingConfig, EmbeddingConfigCreate, EmbeddingConfigUpdate,
  ChunkModelConfig, ChunkModelConfigCreate, ChunkModelConfigUpdate,
  MemoryChunk, MemoryListResponse, MemoryUploadRequest, MemoryBatchUploadRequest,
  TerminalLogListResponse,
} from '@/shared/types/api';

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

export const logApi = {
  list: (skip = 0, limit = 100) =>
    apiClient.get<OperationLogListResponse>(`/logs/?skip=${skip}&limit=${limit}`),
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

  uploadSingle: (data: MemoryUploadRequest) =>
    apiClient.post<MessageResponse>('/memories/upload', data),

  uploadBatch: (data: MemoryBatchUploadRequest) =>
    apiClient.post<MessageResponse>('/memories/upload-batch', data),

  deleteMemory: (memoryId: string) =>
    apiClient.delete<MessageResponse>(`/memories/${memoryId}`),

  clearUserMemories: (ownerId: number) =>
    apiClient.delete<MessageResponse>(`/memories/user/${ownerId}`),
};

export const terminalLogApi = {
  list: (skip = 0, limit = 200, level?: string, keyword?: string) => {
    let url = `/terminal-logs/?skip=${skip}&limit=${limit}`;
    if (level) url += `&level=${level}`;
    if (keyword) url += `&keyword=${keyword}`;
    return apiClient.get<TerminalLogListResponse>(url);
  },

  recent: (count = 50) =>
    apiClient.get<{ items: TerminalLog[]; total: number }>(`/terminal-logs/recent?count=${count}`),

  clear: () =>
    apiClient.post<MessageResponse>('/terminal-logs/clear'),
};
