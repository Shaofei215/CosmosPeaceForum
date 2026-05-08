import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { notificationApi } from './api';
import type { NotificationSummaryResponse, NotificationUnreadCountResponse } from './types';

export const useNotifications = (params: { skip?: number; limit?: number; type?: string } = {}) => {
  return useQuery({
    queryKey: ['notifications', params],
    queryFn: () => notificationApi.getNotifications(params),
  });
};

export const useNotificationUnreadCount = (enabled = true) => {
  useNotificationEvents(enabled);

  return useQuery({
    queryKey: ['notifications', 'unread-count'],
    queryFn: notificationApi.getUnreadCount,
    enabled,
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

export const useNotificationEvents = (enabled = true) => {
  const queryClient = useQueryClient();

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!enabled || !token) {
      return;
    }

    const eventSource = new EventSource(notificationApi.getEventsUrl(token));

    const handleNotificationChange = (event: MessageEvent<string>) => {
      try {
        const data = JSON.parse(event.data) as NotificationUnreadCountResponse &
          NotificationSummaryResponse;
        queryClient.setQueryData<NotificationUnreadCountResponse>(
          ['notifications', 'unread-count'],
          { unread_count: data.unread_count },
        );
        queryClient.setQueryData<NotificationSummaryResponse>(['notifications', 'summary'], {
          following_count: data.following_count,
          followers_count: data.followers_count,
          unread_count: data.unread_count,
        });
      } catch {
        queryClient.invalidateQueries({ queryKey: ['notifications', 'unread-count'] });
        queryClient.invalidateQueries({ queryKey: ['notifications', 'summary'] });
      }

      queryClient.invalidateQueries({ queryKey: ['notifications'], exact: false });
    };

    eventSource.addEventListener('notifications.changed', handleNotificationChange);

    return () => {
      eventSource.removeEventListener('notifications.changed', handleNotificationChange);
      eventSource.close();
    };
  }, [enabled, queryClient]);
};
