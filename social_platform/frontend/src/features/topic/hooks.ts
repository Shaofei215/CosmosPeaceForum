import { useQuery } from '@tanstack/react-query';
import { topicApi } from './api';

export const topicKeys = {
  trending: (limit: number) => ['topics', 'trending', limit] as const,
};

export function useTrendingTopics(limit = 12) {
  return useQuery({
    queryKey: topicKeys.trending(limit),
    queryFn: () => topicApi.trending(limit),
    staleTime: 2 * 60 * 1000,
  });
}
