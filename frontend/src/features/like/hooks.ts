/**
 * 点赞模块Hooks
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { likeApi } from './api';
import type { LikeStatusResponse } from './types';

export const useLikeStatus = (postId: number, enabled = true) => {
  return useQuery({
    queryKey: ['posts', postId, 'like-status'],
    queryFn: () => likeApi.getLikeStatus(postId),
    enabled: enabled && postId > 0,
  });
};

/**
 * 切换点赞Hook（乐观更新）
 */
export const useToggleLike = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: likeApi.toggleLike,
    onMutate: async (postId: number) => {
      // 取消正在进行的重新获取
      // 注意：帖子详情的queryKey可能包含userId，需要匹配所有可能的key
      await queryClient.cancelQueries({ queryKey: ['post', postId] });
      await queryClient.cancelQueries({ queryKey: ['feed'] });

      // 保存之前的状态（尝试获取带userId和不带userId的缓存）
      const queryCache = queryClient.getQueryCache();
      const postQueries = queryCache.findAll({ queryKey: ['post', postId] });
      const previousPosts = postQueries.map(query => ({
        queryKey: query.queryKey,
        data: query.state.data,
      }));

      // 乐观更新帖子详情（匹配所有可能的queryKey变体）
      queryClient.setQueriesData({ queryKey: ['post', postId] }, (old: Record<string, unknown> | undefined) => {
        if (!old) return old;
        const newIsLiked = !old.is_liked_by_current_user;
        return {
          ...old,
          is_liked_by_current_user: newIsLiked,
          like_count: newIsLiked
            ? (old.like_count as number) + 1
            : (old.like_count as number) - 1,
        };
      });

      // 乐观更新信息流（处理无限查询的分页数据结构）
      queryClient.setQueriesData({ queryKey: ['feed'] }, (old: Record<string, unknown> | undefined) => {
        if (!old) return old;

        // 处理无限查询结构 { pages: [{ data: [...] }, ...] }
        if (old.pages && Array.isArray(old.pages)) {
          return {
            ...old,
            pages: (old.pages as Array<Record<string, unknown>>).map((page) => {
              if (!page.data || !Array.isArray(page.data)) return page;
              return {
                ...page,
                data: page.data.map((post: Record<string, unknown>) => {
                  if (post.id === postId) {
                    const newIsLiked = !post.is_liked;
                    return {
                      ...post,
                      is_liked: newIsLiked,
                      like_count: newIsLiked
                        ? (post.like_count as number) + 1
                        : (post.like_count as number) - 1,
                    };
                  }
                  return post;
                }),
              };
            }),
          };
        }

        // 处理普通查询结构 { data: [...] }
        if (old.data && Array.isArray(old.data)) {
          return {
            ...old,
            data: (old.data as Array<Record<string, unknown>>).map((post) => {
              if (post.id === postId) {
                const newIsLiked = !post.is_liked;
                return {
                  ...post,
                  is_liked: newIsLiked,
                  like_count: newIsLiked
                    ? (post.like_count as number) + 1
                    : (post.like_count as number) - 1,
                };
              }
              return post;
            }),
          };
        }

        return old;
      });

      return { previousPosts };
    },
    onSuccess: (data, postId) => {
      queryClient.setQueryData<LikeStatusResponse>(['posts', postId, 'like-status'], data);
    },
    onError: (_error, _postId, context) => {
      // 回滚所有之前保存的状态
      if (context?.previousPosts) {
        context.previousPosts.forEach(({ queryKey, data }) => {
          if (data) {
            queryClient.setQueryData(queryKey, data);
          }
        });
      }
    },
  });
};
