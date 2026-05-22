import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '@/features/admin/api';
import { themeApi } from './api';

export const themeKeys = {
  public: ['theme', 'public'] as const,
  admin: ['theme', 'admin'] as const,
};

export function usePublicTheme() {
  return useQuery({
    queryKey: themeKeys.public,
    queryFn: themeApi.getPublicTheme,
    staleTime: 5 * 60 * 1000,
  });
}

export function useAdminTheme() {
  return useQuery({
    queryKey: themeKeys.admin,
    queryFn: adminApi.theme,
  });
}

export function useUpdateAdminTheme() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: adminApi.updateTheme,
    onSuccess: (theme, request) => {
      const nextTheme = { ...request, ...theme };
      queryClient.setQueryData(themeKeys.admin, nextTheme);
      queryClient.setQueryData(themeKeys.public, nextTheme);
    },
  });
}
