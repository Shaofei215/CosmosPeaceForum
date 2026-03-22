/**
 * 用户模块Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { userApi } from './api';
import type { UpdateUserData } from './types';

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
    onSuccess: (_, variables) => {
      // 刷新用户详情缓存
      queryClient.invalidateQueries({ queryKey: ['user', variables.userId] });
      // 刷新用户列表缓存
      queryClient.invalidateQueries({ queryKey: ['users'] });
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
      // 刷新用户列表缓存
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
};
