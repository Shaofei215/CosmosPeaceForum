import { apiClient } from '@/shared/api/client';
import { API_CONFIG } from '@/shared/config/api';
import type {
  NotificationListResponse,
  ModerationAppealRequest,
  ModerationAppealResponse,
  NotificationSummaryResponse,
  NotificationUnreadCountResponse,
} from './types';

export const notificationApi = {
  getNotifications: (params: { skip?: number; limit?: number; type?: string } = {}) =>
    apiClient.get<NotificationListResponse>('/notifications', { params }),

  getUnreadCount: () =>
    apiClient.get<NotificationUnreadCountResponse>('/notifications/unread-count'),

  getSummary: () => apiClient.get<NotificationSummaryResponse>('/notifications/summary'),

  markRead: () => apiClient.post<{ updated_count: number }>('/notifications/mark-read'),

  submitAppeal: (notificationId: number, request: ModerationAppealRequest) =>
    apiClient.post<ModerationAppealResponse>(`/notifications/${notificationId}/appeal`, request),

  getEventsUrl: () => `${API_CONFIG.BASE_URL}/notifications/events`,
};
