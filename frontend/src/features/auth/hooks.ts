/**
 * 认证模块Hooks
 * 提供登录、注册等操作的React Query Hooks
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { authApi } from './api';
import { useAuthStore } from './stores/authStore';
import type { LoginCredentials, RegisterCredentials } from './types';

/**
 * 登录Hook
 * 处理用户登录逻辑，成功后保存认证信息
 *
 * @example
 * const { mutate: login, isPending } = useLogin();
 * login({ username: 'user', password: 'pass' });
 */
export const useLogin = () => {
  const { setAuth } = useAuthStore();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: authApi.login,
    onSuccess: async (data) => {
      try {
        // 先保存token到localStorage，以便后续请求使用
        localStorage.setItem('token', data.access_token);
        // 获取用户信息
        const user = await authApi.getCurrentUser();
        // 保存认证信息到store
        setAuth(data.access_token, user);
        // 预缓存用户信息
        queryClient.setQueryData(['auth', 'me'], user);
      } catch (error) {
        // 获取用户信息失败，清理token并抛出错误
        localStorage.removeItem('token');
        throw error;
      }
    },
  });
};

/**
 * 注册Hook
 * 处理用户注册逻辑
 *
 * @example
 * const { mutate: register, isPending } = useRegister();
 * register({ username: 'user', password: 'pass' });
 */
export const useRegister = () => {
  return useMutation({
    mutationFn: authApi.register,
  });
};

/**
 * 获取当前用户Hook
 * 获取当前登录用户信息
 *
 * @example
 * const { data: user, isLoading } = useCurrentUser();
 */
export const useCurrentUser = () => {
  const { isAuthenticated } = useAuthStore();

  return useQuery({
    queryKey: ['auth', 'me'],
    queryFn: authApi.getCurrentUser,
    enabled: isAuthenticated,
    staleTime: 5 * 60 * 1000, // 5分钟
  });
};

/**
 * 登出Hook
 * 处理用户登出逻辑
 *
 * @example
 * const logout = useLogout();
 * logout();
 */
export const useLogout = () => {
  const { logout } = useAuthStore();
  const queryClient = useQueryClient();

  return () => {
    logout();
    // 清除所有查询缓存
    queryClient.clear();
  };
};
