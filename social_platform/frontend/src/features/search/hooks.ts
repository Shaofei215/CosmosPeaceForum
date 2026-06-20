import { useInfiniteQuery } from '@tanstack/react-query';
import type { PaginatedResponse } from '@/shared/types/api';
import { searchApi } from './api';
import type { ContentSearchItem, SearchType, UserSearchItem } from './types';

const DEFAULT_PAGE_SIZE = 20;
type SearchItem = ContentSearchItem | UserSearchItem;
type SearchResult = PaginatedResponse<SearchItem>;

export const useInfiniteSearch = (type: SearchType, query: string) => {
  const normalizedQuery = query.trim();

  return useInfiniteQuery({
    queryKey: ['search', type, normalizedQuery],
    queryFn: async ({ pageParam = 1 }): Promise<SearchResult> => {
      const params = {
        type,
        q: normalizedQuery,
        page: pageParam,
        page_size: DEFAULT_PAGE_SIZE,
      };

      if (type === 'user') {
        return searchApi.searchUsers(params);
      }
      if (type === 'topic') {
        return searchApi.searchTopics(params);
      }
      return searchApi.searchContent(params);
    },
    getNextPageParam: lastPage => {
      if (lastPage.pagination.has_next) {
        return lastPage.pagination.page + 1;
      }
      return undefined;
    },
    initialPageParam: 1,
    enabled: normalizedQuery.length > 0,
  });
};
