import { useInfiniteQuery } from '@tanstack/react-query';
import { searchApi } from './api';
import type { SearchType } from './types';

const DEFAULT_PAGE_SIZE = 20;

export const useInfiniteSearch = (type: SearchType, query: string) => {
  const normalizedQuery = query.trim();

  return useInfiniteQuery({
    queryKey: ['search', type, normalizedQuery],
    queryFn: ({ pageParam = 1 }) => {
      const params = {
        type,
        q: normalizedQuery,
        page: pageParam,
        page_size: DEFAULT_PAGE_SIZE,
      };

      return type === 'content'
        ? searchApi.searchContent(params)
        : searchApi.searchUsers(params);
    },
    getNextPageParam: (lastPage) => {
      if (lastPage.pagination.has_next) {
        return lastPage.pagination.page + 1;
      }
      return undefined;
    },
    initialPageParam: 1,
    enabled: normalizedQuery.length > 0,
  });
};
