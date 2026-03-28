/**
 * 帖子模块Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { postApi } from './api';
import type { UpdatePostData } from './types';

/**
 * 获取帖子列表Hook
 */
export const usePosts = (params: { skip?: number; limit?: number } = {}) => {
  return useQuery({
    queryKey: ['posts', params],
    queryFn: () => postApi.getPosts(params),
  });
};

/**
 * 获取帖子详情Hook
 */
export const usePost = (postId: number, currentUserId?: number) => {
  return useQuery({
    queryKey: ['post', postId, currentUserId],
    queryFn: () => postApi.getPost(postId, currentUserId),
    enabled: !!postId,
  });
};

/**
 * 创建帖子Hook
 */
export const useCreatePost = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: postApi.createPost,
    onSuccess: () => {
      // 刷新帖子列表
      queryClient.invalidateQueries({ queryKey: ['posts'] });
      // 刷新信息流
      queryClient.invalidateQueries({ queryKey: ['feed'] });
    },
  });
};

/**
 * 更新帖子Hook
 */
export const useUpdatePost = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ postId, data }: { postId: number; data: UpdatePostData }) =>
      postApi.updatePost(postId, data),
    onSuccess: (_, variables) => {
      // 刷新帖子详情
      queryClient.invalidateQueries({ queryKey: ['post', variables.postId] });
      // 刷新帖子列表
      queryClient.invalidateQueries({ queryKey: ['posts'] });
      // 刷新信息流
      queryClient.invalidateQueries({ queryKey: ['feed'] });
    },
  });
};

/**
 * 删除帖子Hook
 */
export const useDeletePost = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: postApi.deletePost,
    onSuccess: () => {
      // 刷新帖子列表
      queryClient.invalidateQueries({ queryKey: ['posts'] });
      // 刷新信息流
      queryClient.invalidateQueries({ queryKey: ['feed'] });
    },
  });
};

/**
 * 获取用户帖子Hook
 */
export const useUserPosts = (userId: number, params: { skip?: number; limit?: number } = {}) => {
  return useQuery({
    queryKey: ['posts', 'user', userId, params],
    queryFn: () => postApi.getUserPosts(userId, params),
    enabled: !!userId,
  });
};
