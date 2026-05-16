import { apiClient } from '@/shared/api/client';
import type { PaginatedResponse } from '@/shared/types/api';
import type { ContentSearchItem, SearchParams, UserSearchItem } from './types';

export const searchApi = {
  searchContent: (params: SearchParams) =>
    apiClient.get<PaginatedResponse<ContentSearchItem>>('/search', {
      params: { ...params, type: 'content' },
    }),

  searchUsers: (params: SearchParams) =>
    apiClient.get<PaginatedResponse<UserSearchItem>>('/search', {
      params: { ...params, type: 'user' },
    }),
};
