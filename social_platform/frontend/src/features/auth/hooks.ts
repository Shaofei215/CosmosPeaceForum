/**
 * 认证模块Hooks
 * 提供登录、注册等操作的React Query Hooks
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { authApi } from './api';
import { useAuthStore } from './stores/authStore';
import { getRefreshToken } from './tokenStorage';

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
  const { setAuth, logout } = useAuthStore();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: authApi.login,
    onSuccess: async (data, variables) => {
      try {
        setAuth(
          data.access_token,
          {
            id: 0,
            username: '',
            email: null,
            email_verified: false,
            created_at: new Date().toISOString(),
          },
          data.refresh_token,
          Boolean(variables.remember_me)
        );
        // 获取用户信息
        const user = await authApi.getCurrentUser();
        // 保存认证信息到store
        setAuth(data.access_token, user);
        // 预缓存用户信息
        queryClient.setQueryData(['auth', 'me'], user);
      } catch (error) {
        // 获取用户信息失败，清理 token 并抛出错误
        logout();
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
 * 注册邀请码配置Hook
 * 控制注册页是否展示邀请码输入，实际校验仍由后端注册接口负责
 */
export const useInvitationRegistrationConfig = () => {
  return useQuery({
    queryKey: ['auth', 'invitation-registration-config'],
    queryFn: authApi.invitationRegistrationConfig,
    staleTime: 5 * 60 * 1000,
  });
};

/**
 * 带邮箱验证的注册Hook（真人用户专用）
 * 处理验证邮箱并注册逻辑，注册成功后自动保存认证信息
 *
 * @example
 * const { mutate: register, isPending } = useRegisterWithVerification();
 * register({ password: 'pass', email: 'user@example.com', code: '123456' });
 */
export const useRegisterWithVerification = () => {
  const { setAuth } = useAuthStore();

  return useMutation({
    mutationFn: authApi.registerWithVerification,
    onSuccess: (data, variables) => {
      // 注册成功后保存token和临时用户信息
      // 用户详细信息（如下用户名）将在资料完善页面更新
      const tempUser = {
        id: data.id,
        username: data.username,
        email: null,
        email_verified: false,
        created_at: new Date().toISOString(),
        avatar_url: null,
        bio: null,
        coin_balance: data.coin_balance,
        login_streak: data.login_streak,
      };
      setAuth(data.access_token, tempUser, data.refresh_token, Boolean(variables.remember_me));
    },
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

  return async () => {
    const refreshToken = getRefreshToken();
    try {
      if (refreshToken) {
        await authApi.logout();
      }
    } finally {
      logout();
      // 清除所有查询缓存
      queryClient.clear();
    }
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
