import { apiClient } from '@/shared/api/client';
import type {
  NotificationListResponse,
  NotificationSummaryResponse,
  NotificationUnreadCountResponse,
} from './types';

export const notificationApi = {
  getNotifications: (params: { skip?: number; limit?: number; type?: string } = {}) =>
    apiClient.get<NotificationListResponse>('/notifications', { params }),

  getUnreadCount: () =>
    apiClient.get<NotificationUnreadCountResponse>('/notifications/unread-count'),

  getSummary: () =>
    apiClient.get<NotificationSummaryResponse>('/notifications/summary'),

  markRead: () =>
    apiClient.post<{ updated_count: number }>('/notifications/mark-read'),
};
