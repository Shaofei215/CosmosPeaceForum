/**
 * 评论模块Hooks
 */

import { useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { commentApi } from './api';
import type {
  CommentSort,
  CreateCommentData,
  Comment,
  CommentLikeResponse,
  CommentListResponse,
} from './types';

/**
 * 获取评论树Hook
 */
export const useComments = (postId: number, userId?: number, sort: CommentSort = 'default') => {
  const seed = useMemo(
    () => `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    [postId, sort],
  );

  return useQuery({
    queryKey: ['comments', postId, userId, sort, seed],
    queryFn: () => commentApi.getComments(postId, { user_id: userId, sort, seed }),
    enabled: !!postId,
  });
};

export const useCommentLikeStatus = (postId: number, commentId: number, enabled = true) => {
  return useQuery({
    queryKey: ['comments', postId, commentId, 'like-status'],
    queryFn: () => commentApi.getCommentLikeStatus(postId, commentId),
    enabled: enabled && !!postId && !!commentId,
  });
};

/**
 * 创建评论Hook
 */
export const useCreateComment = (postId: number) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateCommentData) => commentApi.createComment(postId, data),
    onSuccess: () => {
      // 刷新评论列表
      queryClient.invalidateQueries({ queryKey: ['comments', postId] });
      // 刷新帖子评论数
      queryClient.invalidateQueries({ queryKey: ['post', postId] });
      // 刷新信息流
      queryClient.invalidateQueries({ queryKey: ['feed'] });
    },
  });
};

/**
 * 删除评论Hook
 */
export const useDeleteComment = (postId: number) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (commentId: number) => commentApi.deleteComment(postId, commentId),
    onSuccess: () => {
      // 刷新评论列表
      queryClient.invalidateQueries({ queryKey: ['comments', postId] });
      // 刷新帖子评论数
      queryClient.invalidateQueries({ queryKey: ['post', postId] });
      // 刷新信息流
      queryClient.invalidateQueries({ queryKey: ['feed'] });
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
};

/**
 * 评论点赞Hook（乐观更新）
 */
export const useToggleCommentLike = (
  postId: number,
  userId?: number,
  sort: CommentSort = 'default',
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ commentId }: { commentId: number }) =>
      commentApi.toggleCommentLike(postId, commentId),
    onMutate: async ({ commentId }) => {
      // 取消所有相关的查询
      await queryClient.cancelQueries({ queryKey: ['comments', postId] });

      // 获取之前的缓存数据（包含 userId 的 queryKey）
      const queryKey = ['comments', postId, userId, sort];
      const likeStatusQueryKey = ['comments', postId, commentId, 'like-status'];
      const previousComments = queryClient.getQueriesData<CommentListResponse>({
        queryKey,
      });
      const previousLikeStatus = queryClient.getQueryData<CommentLikeResponse>(likeStatusQueryKey);

      // 递归更新评论点赞状态
      const updateCommentLike = (comments: Comment[]): Comment[] => {
        return comments.map(comment => {
          if (comment.id === commentId) {
            return {
              ...comment,
              is_liked: !comment.is_liked,
              like_count: comment.is_liked ? comment.like_count - 1 : comment.like_count + 1,
            };
          }
          if (comment.children && comment.children.length > 0) {
            return {
              ...comment,
              children: updateCommentLike(comment.children),
            };
          }
          return comment;
        });
      };

      // 乐观更新缓存
      queryClient.setQueriesData<CommentListResponse>({ queryKey }, old => {
        if (!old) return old;
        return {
          ...old,
          items: updateCommentLike(old.items),
        };
      });

      queryClient.setQueryData<CommentLikeResponse>(likeStatusQueryKey, old => {
        if (!old) return old;
        const isLiked = !old.is_liked;
        return {
          is_liked: isLiked,
          like_count: isLiked ? old.like_count + 1 : Math.max(0, old.like_count - 1),
        };
      });

      return { previousComments, previousLikeStatus, queryKey, likeStatusQueryKey };
    },
    onError: (_, __, context) => {
      if (context?.previousComments) {
        context.previousComments.forEach(([queryKey, data]) => {
          queryClient.setQueryData(queryKey, data);
        });
      }
      if (context?.previousLikeStatus && context?.likeStatusQueryKey) {
        queryClient.setQueryData(context.likeStatusQueryKey, context.previousLikeStatus);
      }
    },
    onSuccess: (data, { commentId }) => {
      queryClient.setQueryData(['comments', postId, commentId, 'like-status'], data);
    },
  });
};
