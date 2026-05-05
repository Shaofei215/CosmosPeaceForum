import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { notificationApi } from './api';

export const useNotifications = (params: { skip?: number; limit?: number; type?: string } = {}) => {
  return useQuery({
    queryKey: ['notifications', params],
    queryFn: () => notificationApi.getNotifications(params),
  });
};

export const useNotificationUnreadCount = (enabled = true) => {
  return useQuery({
    queryKey: ['notifications', 'unread-count'],
    queryFn: notificationApi.getUnreadCount,
    enabled,
    refetchInterval: enabled ? 30000 : false,
  });
};

export const useNotificationSummary = (enabled = true) => {
  return useQuery({
    queryKey: ['notifications', 'summary'],
    queryFn: notificationApi.getSummary,
    enabled,
  });
};

export const useMarkNotificationsRead = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: notificationApi.markRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
};
