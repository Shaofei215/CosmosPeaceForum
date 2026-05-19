/**
 * 信息流模块Hooks
 */

import { useMemo } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { feedApi } from './api';
import type { FeedType } from './types';

/** 默认每页数量 */
const DEFAULT_PAGE_SIZE = 20;

const FEED_CACHE_TIME = 1000 * 60 * 30;
const stableFeedSeeds = new Map<string, string>();

function getStableFeedSeed(userId: number | undefined, feedType: FeedType) {
  const seedKey = `${userId ?? 'anonymous'}:${feedType}`;
  const existingSeed = stableFeedSeeds.get(seedKey);

  if (existingSeed) {
    return existingSeed;
  }

  const seed = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  stableFeedSeeds.set(seedKey, seed);
  return seed;
}

/**
 * 全局信息流无限滚动Hook
 */
export const useInfiniteGlobalFeed = (userId?: number, feedType: FeedType = 'recommended') => {
  const seed = useMemo(() => getStableFeedSeed(userId, feedType), [feedType, userId]);

  return useInfiniteQuery({
    queryKey: ['feed', 'global', userId, feedType],
    queryFn: ({ pageParam = 1 }) =>
      feedApi.getGlobalFeed({
        page: pageParam,
        page_size: DEFAULT_PAGE_SIZE,
        current_user_id: userId,
        feed_type: feedType,
        seed,
      }),
    getNextPageParam: lastPage => {
      if (lastPage.pagination.has_next) {
        return lastPage.pagination.page + 1;
      }
      return undefined;
    },
    initialPageParam: 1,
    staleTime: FEED_CACHE_TIME,
    gcTime: FEED_CACHE_TIME,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
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
    getNextPageParam: lastPage => {
      if (lastPage.pagination.has_next) {
        return lastPage.pagination.page + 1;
      }
      return undefined;
    },
    initialPageParam: 1,
    enabled: !!targetUserId,
  });
};
