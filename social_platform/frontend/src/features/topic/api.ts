import { apiClient } from '@/shared/api/client';
import type { Topic } from './types';

export const topicApi = {
  trending: (limit = 12) => apiClient.get<Topic[]>('/topics/trending', { params: { limit } }),
};
