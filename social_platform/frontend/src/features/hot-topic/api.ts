import { apiClient } from '@/shared/api/client';
import type { HotTopic } from './types';

export const hotTopicApi = {
  list: (limit = 20) => apiClient.get<HotTopic[]>('/hot-topics', { params: { limit } }),
};
