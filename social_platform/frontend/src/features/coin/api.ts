import { apiClient } from '@/shared/api/client';
import type { PostCoinResponse, PostCoinStatusResponse } from './types';

export const coinApi = {
  giveCoin: (postId: number) => apiClient.post<PostCoinResponse>(`/posts/${postId}/coin`),
  getStatus: (postId: number) =>
    apiClient.get<PostCoinStatusResponse>(`/posts/${postId}/coin-status`),
};
