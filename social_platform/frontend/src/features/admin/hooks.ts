/**
 * 平台管理员认证 hooks。
 *
 * 登录成功保存管理员 token 对；登出先调用后端撤销当前 session，再清本地状态。
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from './api';
import { useAdminAuthStore } from './store';

export const adminKeys = {
  me: ['admin', 'me'] as const,
  stats: ['admin', 'stats'] as const,
  users: (keyword: string) => ['admin', 'users', keyword] as const,
  reportedUsers: (keyword: string) => ['admin', 'users', 'reports', keyword] as const,
  moderatedUsers: (keyword: string) => ['admin', 'users', 'moderated', keyword] as const,
  invitations: (keyword: string) => ['admin', 'users', 'invitations', keyword] as const,
  userReportModerationSettings: ['admin', 'users', 'report-moderation-settings'] as const,
  userReportModerationPrompt: ['admin', 'users', 'report-moderation-prompt'] as const,
  content: (type: string, keyword: string) => ['admin', 'content', type, keyword] as const,
  reportedContent: (type: string, keyword: string) =>
    ['admin', 'content', 'reports', type, keyword] as const,
  archivedContent: (type: string, keyword: string) =>
    ['admin', 'content', 'archived', type, keyword] as const,
  reportModerationSettings: ['admin', 'content', 'report-moderation-settings'] as const,
  reportModerationPrompt: ['admin', 'content', 'report-moderation-prompt'] as const,
  hotTopics: (status: string, source: string) => ['admin', 'hot-topics', status, source] as const,
  hotTopicSettings: ['admin', 'hot-topic-settings'] as const,
  hotTopicPrompt: ['admin', 'hot-topic-prompt'] as const,
  hotTopicGenerations: ['admin', 'hot-topic-generations'] as const,
  admins: ['admin', 'admins'] as const,
  operations: ['admin', 'operations'] as const,
  terminal: (keyword: string) => ['admin', 'terminal', keyword] as const,
};

export function useAdminLogin() {
  const setAuth = useAdminAuthStore(state => state.setAuth);

  return useMutation({
    mutationFn: adminApi.login,
    onSuccess: (data, variables) => {
      setAuth(data.access_token, data.admin, data.refresh_token, Boolean(variables.remember_me));
    },
  });
}

export function useCurrentAdmin() {
  const isAuthenticated = useAdminAuthStore(state => state.isAuthenticated);
  const setAdmin = useAdminAuthStore(state => state.setAdmin);

  return useQuery({
    queryKey: adminKeys.me,
    queryFn: async () => {
      const admin = await adminApi.me();
      setAdmin(admin);
      return admin;
    },
    enabled: isAuthenticated,
    staleTime: 2 * 60 * 1000,
  });
}

export function useAdminLogout() {
  const logout = useAdminAuthStore(state => state.logout);
  const queryClient = useQueryClient();

  return async () => {
    try {
      await adminApi.logout();
    } finally {
      logout();
      queryClient.removeQueries({ queryKey: ['admin'] });
    }
  };
}

export function useAdminProfileUpdate() {
  const setAdmin = useAdminAuthStore(state => state.setAdmin);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: adminApi.updateProfile,
    onSuccess: admin => {
      setAdmin(admin);
      queryClient.setQueryData(adminKeys.me, admin);
    },
  });
}
