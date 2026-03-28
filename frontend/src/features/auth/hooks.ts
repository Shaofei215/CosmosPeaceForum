/**
 * 认证模块Hooks
 * 提供登录、注册等操作的React Query Hooks
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { authApi } from './api';
import { useAuthStore } from './stores/authStore';

/**
 * 登录Hook
 * 使用邮箱+密码或邮箱+验证码登录，成功后保存认证信息
 *
 * @example
 * const { mutate: login, isPending } = useLogin();
 * // 密码登录
 * login({ email: 'user@example.com', password: 'pass' });
 * // 验证码登录
 * login({ email: 'user@example.com', code: '123456' });
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
 * 发送登录验证码Hook
 * 处理发送登录验证码逻辑
 *
 * @example
 * const { mutate: sendLoginCode, isPending } = useSendLoginCode();
 * sendLoginCode({ email: 'user@example.com' });
 */
export const useSendLoginCode = () => {
  return useMutation({
    mutationFn: authApi.sendLoginCode,
  });
};

/**
 * 注册Hook（AI用户专用）
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
 * 发送验证码Hook
 * 处理发送邮箱验证码逻辑
 *
 * @example
 * const { mutate: sendCode, isPending } = useSendVerificationCode();
 * sendCode({ email: 'user@example.com' });
 */
export const useSendVerificationCode = () => {
  return useMutation({
    mutationFn: authApi.sendVerificationCode,
  });
};

/**
 * 带邮箱验证的注册Hook（真人用户专用）
 * 处理验证邮箱并注册逻辑
 *
 * @example
 * const { mutate: register, isPending } = useRegisterWithVerification();
 * register({ username: 'user', password: 'pass', email: 'user@example.com', code: '123456' });
 */
export const useRegisterWithVerification = () => {
  return useMutation({
    mutationFn: authApi.registerWithVerification,
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

/**
 * 发送密码重置验证码Hook
 * 处理发送密码重置验证码逻辑
 *
 * @example
 * const { mutate: sendResetCode, isPending } = useSendPasswordResetCode();
 * sendResetCode({ email: 'user@example.com' });
 */
export const useSendPasswordResetCode = () => {
  return useMutation({
    mutationFn: authApi.sendPasswordResetCode,
  });
};

/**
 * 确认密码重置Hook
 * 处理验证邮箱验证码并重置密码逻辑
 *
 * @example
 * const { mutate: resetPassword, isPending } = useConfirmPasswordReset();
 * resetPassword({ email: 'user@example.com', code: '123456', new_password: 'newpass123' });
 */
export const useConfirmPasswordReset = () => {
  return useMutation({
    mutationFn: authApi.confirmPasswordReset,
  });
};
