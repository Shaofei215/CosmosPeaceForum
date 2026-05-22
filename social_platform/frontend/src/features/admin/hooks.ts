import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from './api';
import { useAdminAuthStore } from './store';

export const adminKeys = {
  me: ['admin', 'me'] as const,
  stats: ['admin', 'stats'] as const,
  users: (keyword: string) => ['admin', 'users', keyword] as const,
  content: (type: string, keyword: string) => ['admin', 'content', type, keyword] as const,
  admins: ['admin', 'admins'] as const,
  operations: ['admin', 'operations'] as const,
  terminal: (keyword: string) => ['admin', 'terminal', keyword] as const,
};

export function useAdminLogin() {
  const setAuth = useAdminAuthStore(state => state.setAuth);

  return useMutation({
    mutationFn: adminApi.login,
    onSuccess: data => {
      setAuth(data.access_token, data.admin);
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

  return () => {
    logout();
    queryClient.removeQueries({ queryKey: ['admin'] });
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
