/**
 * 信息流模块Hooks
 */

import { useInfiniteQuery } from '@tanstack/react-query';
import { feedApi } from './api';

/** 默认每页数量 */
const DEFAULT_PAGE_SIZE = 20;

/**
 * 全局信息流无限滚动Hook
 */
export const useInfiniteGlobalFeed = (userId?: number) => {
  return useInfiniteQuery({
    queryKey: ['feed', 'global', userId],
    queryFn: ({ pageParam = 1 }) =>
      feedApi.getGlobalFeed({
        page: pageParam,
        page_size: DEFAULT_PAGE_SIZE,
        current_user_id: userId,
      }),
    getNextPageParam: (lastPage) => {
      if (lastPage.pagination.has_next) {
        return lastPage.pagination.page + 1;
      }
      return undefined;
    },
    initialPageParam: 1,
  });
};

/**
 * 用户帖子流无限滚动Hook
 */
export const useInfiniteUserFeed = (targetUserId: number, currentUserId?: number) => {
  return useInfiniteQuery({
    queryKey: ['feed', 'user', targetUserId, currentUserId],
    queryFn: ({ pageParam = 1 }) =>
      feedApi.getUserFeed(targetUserId, {
        page: pageParam,
        page_size: DEFAULT_PAGE_SIZE,
        current_user_id: currentUserId,
      }),
    getNextPageParam: (lastPage) => {
      if (lastPage.pagination.has_next) {
        return lastPage.pagination.page + 1;
      }
      return undefined;
    },
    initialPageParam: 1,
    enabled: !!targetUserId,
  });
};
