import { useQuery } from '@tanstack/react-query';
import { hotTopicApi } from './api';

export const hotTopicKeys = {
  publicList: (limit: number) => ['hot-topics', 'public', limit] as const,
};

export function useHotTopics(limit = 20) {
  return useQuery({
    queryKey: hotTopicKeys.publicList(limit),
    queryFn: () => hotTopicApi.list(limit),
    staleTime: 2 * 60 * 1000,
  });
}
