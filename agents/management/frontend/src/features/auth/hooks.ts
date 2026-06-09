/**
 * Management 管理员认证 hooks。
 *
 * 登录成功保存 token 对；登出调用后端撤销当前 admin session。
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { authApi } from './api';
import { useAuthStore } from './stores/authStore';

export const useLogin = () => {
  const { setAuth } = useAuthStore();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: authApi.login,
    onSuccess: (data, variables) => {
      setAuth(data.access_token, data.admin, data.refresh_token, Boolean(variables.remember_me));
      queryClient.setQueryData(['auth', 'me'], data.admin);
    },
  });
};

export const useCurrentAdmin = () => {
  const { isAuthenticated } = useAuthStore();
  const setUser = useAuthStore((state) => state.setUser);

  return useQuery({
    queryKey: ['auth', 'me'],
    queryFn: async () => {
      const user = await authApi.getCurrentAdmin();
      setUser(user);
      return user;
    },
    enabled: isAuthenticated,
    staleTime: 5 * 60 * 1000,
  });
};

export const useLogout = () => {
  const { logout } = useAuthStore();
  const queryClient = useQueryClient();

  return async () => {
    try {
      await authApi.logout();
    } finally {
      logout();
      queryClient.clear();
      window.location.href = '/login';
    }
  };
};
