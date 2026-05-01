import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { authApi } from './api';
import { useAuthStore } from './stores/authStore';

export const useLogin = () => {
  const { setAuth } = useAuthStore();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: authApi.login,
    onSuccess: async (data) => {
      try {
        localStorage.setItem('token', data.access_token);
        const user = await authApi.getCurrentAdmin();
        setAuth(data.access_token, user);
        queryClient.setQueryData(['auth', 'me'], user);
      } catch {
        localStorage.removeItem('token');
        throw new Error('获取管理员信息失败');
      }
    },
  });
};

export const useCurrentAdmin = () => {
  const { isAuthenticated } = useAuthStore();

  return useQuery({
    queryKey: ['auth', 'me'],
    queryFn: authApi.getCurrentAdmin,
    enabled: isAuthenticated,
    staleTime: 5 * 60 * 1000,
  });
};

export const useLogout = () => {
  const { logout } = useAuthStore();
  const queryClient = useQueryClient();

  return () => {
    logout();
    queryClient.clear();
    window.location.href = '/login';
  };
};
