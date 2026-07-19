/**
 * 用户模块Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { userApi } from './api';
import type { UpdateUserData, CompleteProfileData, UserProfile } from './types';
import { useAuthStore } from '@/features/auth';
import { getAccessToken } from '@/features/auth/tokenStorage';
import type { QueryClient } from '@tanstack/react-query';

/** 同步当前用户的详情缓存、认证缓存与 Zustand 登录态。 */
function syncCurrentUser(queryClient: QueryClient, updatedUser: UserProfile): void {
  queryClient.setQueryData(['user', updatedUser.id], updatedUser);
  const currentAuthUser = useAuthStore.getState().user;
  const nextAuthUser = currentAuthUser
    ? { ...currentAuthUser, ...updatedUser }
    : toAuthUser(updatedUser);
  queryClient.setQueryData(['auth', 'me'], nextAuthUser);
  const token = getAccessToken();
  if (token) useAuthStore.getState().setAuth(token, nextAuthUser);
  queryClient.invalidateQueries({ queryKey: ['users'] });
}

/**
 * 获取用户列表Hook
 *
 * @param params - 查询参数
 * @example
 * const { data: users, isLoading } = useUsers({ skip: 0, limit: 10 });
 */
export const useUsers = (params: { skip?: number; limit?: number } = {}) => {
  return useQuery({
    queryKey: ['users', params],
    queryFn: () => userApi.getUsers(params),
  });
};

/**
 * 获取用户详情Hook
 *
 * @param userId - 用户ID
 * @example
 * const { data: user, isLoading } = useUser(1);
 */
export const useUser = (userId: number) => {
  return useQuery({
    queryKey: ['user', userId],
    queryFn: () => userApi.getUser(userId),
    enabled: !!userId,
  });
};

/**
 * 通过用户名获取用户Hook
 *
 * @param username - 用户名
 * @example
 * const { data: user, isLoading } = useUserByUsername('john');
 */
export const useUserByUsername = (username: string) => {
  return useQuery({
    queryKey: ['user', 'username', username],
    queryFn: () => userApi.getUserByUsername(username),
    enabled: !!username,
  });
};

/**
 * 更新用户Hook
 *
 * @example
 * const { mutate: updateUser, isPending } = useUpdateUser();
 * updateUser({ userId: 1, data: { bio: 'New bio' } });
 */
export const useUpdateUser = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ userId, data }: { userId: number; data: UpdateUserData }) =>
      userApi.updateUser(userId, data),
    onSuccess: updatedUser => {
      syncCurrentUser(queryClient, updatedUser);
    },
  });
};

/**
 * 将 UserProfile 转换为 User 类型
 */
const toAuthUser = (profile: UserProfile) => ({
  id: profile.id,
  username: profile.username,
  email: null,
  email_verified: false,
  created_at: profile.created_at,
  avatar_url: profile.avatar_url,
  bio: profile.bio,
});

/**
 * 完善用户资料Hook（注册后使用）
 *
 * @example
 * const { mutate: completeProfile, isPending } = useCompleteProfile();
 * completeProfile({ userId: 1, data: { username: 'newname', bio: 'Hello' } });
 */
export const useCompleteProfile = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ userId, data }: { userId: number; data: CompleteProfileData }) =>
      userApi.completeProfile(userId, data),
    onSuccess: updatedUser => {
      syncCurrentUser(queryClient, updatedUser);
    },
  });
};

/**
 * 上传头像Hook
 *
 * @example
 * const { mutate: uploadAvatar, isPending } = useUploadAvatar();
 * uploadAvatar(file);
 */
export const useUploadAvatar = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (file: File) => userApi.uploadAvatar(file),
    onSuccess: updatedUser => {
      syncCurrentUser(queryClient, updatedUser);
    },
  });
};

/**
 * 删除头像Hook
 *
 * @example
 * const { mutate: deleteAvatar, isPending } = useDeleteAvatar();
 * deleteAvatar();
 */
export const useDeleteAvatar = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => userApi.deleteAvatar(),
    onSuccess: updatedUser => {
      syncCurrentUser(queryClient, updatedUser);
    },
  });
};

/**
 * 删除用户Hook
 *
 * @example
 * const { mutate: deleteUser, isPending } = useDeleteUser();
 * deleteUser(1);
 */
export const useDeleteUser = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: userApi.deleteUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
};
