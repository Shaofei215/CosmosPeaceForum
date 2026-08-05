import { apiClient } from '@/shared/api/client';
import type { DislikeResponse, DislikeStatusResponse } from './types';

export const dislikeApi = {
  toggleDislike: (postId: number) => apiClient.post<DislikeResponse>(`/posts/${postId}/dislike`),
  getStatus: (postId: number) =>
    apiClient.get<DislikeStatusResponse>(`/posts/${postId}/dislike-status`),
};
