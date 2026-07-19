/**
 * 通知相关 hooks。
 *
 * SSE 连接从 tokenStorage 读取最新 access token，避免 refresh 后继续使用旧 token。
 */

import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { notificationApi } from './api';
import type { NotificationSummaryResponse, NotificationUnreadCountResponse } from './types';
import { getAccessToken } from '@/features/auth/tokenStorage';
import { apiClient } from '@/shared/api/client';
import { openAuthenticatedSse } from '@/shared/api/authenticatedSse';

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

export const useSubmitModerationAppeal = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ notificationId, reason }: { notificationId: number; reason: string }) =>
      notificationApi.submitAppeal(notificationId, { reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
};

export const useNotificationEvents = (enabled = true) => {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!enabled || !getAccessToken()) {
      return;
    }
    const controller = new AbortController();

    const handleNotificationChange = (eventData: string) => {
      try {
        const data = JSON.parse(eventData) as NotificationUnreadCountResponse &
          NotificationSummaryResponse;
        queryClient.setQueryData<NotificationUnreadCountResponse>(
          ['notifications', 'unread-count'],
          { unread_count: data.unread_count }
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

    const connect = async () => {
      let retryDelay = 1000;
      while (!controller.signal.aborted) {
        try {
          await openAuthenticatedSse({
            url: notificationApi.getEventsUrl(),
            signal: controller.signal,
            getAccessToken,
            refreshAccessToken: () => apiClient.refreshAccessToken(),
            onMessage: message => {
              if (message.event === 'notifications.changed') {
                handleNotificationChange(message.data);
              }
            },
          });
          retryDelay = 1000;
        } catch {
          if (controller.signal.aborted) return;
        }
        await new Promise(resolve => window.setTimeout(resolve, retryDelay));
        retryDelay = Math.min(retryDelay * 2, 15000);
      }
    };
    void connect();

    return () => {
      controller.abort();
    };
  }, [enabled, queryClient]);
};
