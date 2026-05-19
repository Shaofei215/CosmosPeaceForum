/**
 * 关注模块Hooks
 */

import { useMutation, useQuery, useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { followApi } from './api';
import type { FollowStatusResponse } from './types';
import { useAuthStore } from '@/features/auth/stores/authStore';

interface UseFollowStatusOptions {
  enabled?: boolean;
  initialData?: FollowStatusResponse;
}

export const useToggleFollow = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: followApi.toggleFollow,
    onMutate: async (userId: number) => {
      await queryClient.cancelQueries({ queryKey: ['followStatus', userId] });

      const previousStatus = queryClient.getQueryData<FollowStatusResponse>([
        'followStatus',
        userId,
      ]);

      queryClient.setQueryData<FollowStatusResponse>(['followStatus', userId], old => {
        if (!old) {
          return {
            user_id: userId,
            is_following: true,
            is_followed_by: false,
            is_mutual: false,
          };
        }
        const newIsFollowing = !old.is_following;
        return {
          ...old,
          is_following: newIsFollowing,
          is_mutual: newIsFollowing && old.is_followed_by,
        };
      });

      return { previousStatus };
    },
    onError: (_error, _userId, context) => {
      if (context?.previousStatus) {
        queryClient.setQueryData(['followStatus', _userId], context.previousStatus);
      }
    },
    onSuccess: data => {
      queryClient.invalidateQueries({ queryKey: ['followStatus', data.user_id] });
      queryClient.invalidateQueries({ queryKey: ['feed'] });
      queryClient.invalidateQueries({ queryKey: ['user'] });
      queryClient.invalidateQueries({ queryKey: ['search'] });
      queryClient.invalidateQueries({ queryKey: ['infiniteFollowingList'] });
      queryClient.invalidateQueries({ queryKey: ['infiniteFollowersList'] });
    },
  });
};

export const useFollowStatus = (userId: number, options: UseFollowStatusOptions = {}) => {
  const { isAuthenticated } = useAuthStore();

  return useQuery({
    queryKey: ['followStatus', userId],
    queryFn: () => followApi.getFollowStatus(userId),
    enabled: isAuthenticated && !!userId && (options.enabled ?? true),
    initialData: options.initialData,
  });
};

export const useInfiniteFollowingList = (userId: number) => {
  return useInfiniteQuery({
    queryKey: ['infiniteFollowingList', userId],
    queryFn: ({ pageParam = 1 }) =>
      followApi.getFollowing(userId, { page: pageParam, page_size: 20 }),
    enabled: !!userId,
    initialPageParam: 1,
    getNextPageParam: lastPage => {
      if (lastPage.pagination.has_next) {
        return lastPage.pagination.page + 1;
      }
      return undefined;
    },
  });
};

export const useInfiniteFollowersList = (userId: number) => {
  return useInfiniteQuery({
    queryKey: ['infiniteFollowersList', userId],
    queryFn: ({ pageParam = 1 }) =>
      followApi.getFollowers(userId, { page: pageParam, page_size: 20 }),
    enabled: !!userId,
    initialPageParam: 1,
    getNextPageParam: lastPage => {
      if (lastPage.pagination.has_next) {
        return lastPage.pagination.page + 1;
      }
      return undefined;
    },
  });
};
