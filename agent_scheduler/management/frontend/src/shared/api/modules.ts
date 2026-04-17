import { apiClient } from '@/shared/api/client';
import type {
  AgentConfig, AgentCreate, AgentUpdate, AgentListResponse,
  ModelConfig, ModelConfigCreate, ModelConfigUpdate,
  SystemConfig, OperationLogListResponse, MessageResponse,
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
