/**
 * 评论模块Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { commentApi } from './api';
import type { CreateCommentData, Comment, CommentListResponse } from './types';

/**
 * 获取评论树Hook
 */
export const useComments = (postId: number, userId?: number) => {
  return useQuery({
    queryKey: ['comments', postId, userId],
    queryFn: () => commentApi.getComments(postId, { user_id: userId }),
    enabled: !!postId,
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
    },
  });
};

/**
 * 评论点赞Hook（乐观更新）
 */
export const useToggleCommentLike = (postId: number, userId?: number) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ commentId }: { commentId: number }) =>
      commentApi.toggleCommentLike(postId, commentId),
    onMutate: async ({ commentId }) => {
      // 取消所有相关的查询
      await queryClient.cancelQueries({ queryKey: ['comments', postId] });

      // 获取之前的缓存数据（包含 userId 的 queryKey）
      const queryKey = ['comments', postId, userId];
      const previousComments = queryClient.getQueryData<CommentListResponse>(queryKey);

      // 递归更新评论点赞状态
      const updateCommentLike = (comments: Comment[]): Comment[] => {
        return comments.map((comment) => {
          if (comment.id === commentId) {
            return {
              ...comment,
              is_liked: !comment.is_liked,
              like_count: comment.is_liked
                ? comment.like_count - 1
                : comment.like_count + 1,
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
      queryClient.setQueryData<CommentListResponse>(queryKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          items: updateCommentLike(old.items),
        };
      });

      return { previousComments, queryKey };
    },
    onError: (_, __, context) => {
      if (context?.previousComments && context?.queryKey) {
        queryClient.setQueryData(context.queryKey, context.previousComments);
      }
    },
  });
};
