import { useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useInfiniteSearch, type ContentSearchItem, type SearchType } from '@/features/search';
import type { UserSearchItem } from '@/features/search';
import { PostCard } from '@/widgets/post-card';
import { UserListItem, UserListItemSkeleton } from '@/widgets/user-list-item';
import { Skeleton } from '@/shared/components/ui';
import { copywriting } from '@/shared/config/copywriting';

export default function SearchPage() {
  const [searchParams] = useSearchParams();
  const query = searchParams.get('q') || '';
  const requestedType = searchParams.get('type');
  const type: SearchType =
    requestedType === 'user' ? 'user' : requestedType === 'topic' ? 'topic' : 'content';

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } = useInfiniteSearch(
    type,
    query
  );

  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (observerRef.current) {
      observerRef.current.disconnect();
    }

    observerRef.current = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
        fetchNextPage();
      }
    });

    if (loadMoreRef.current) {
      observerRef.current.observe(loadMoreRef.current);
    }

    return () => observerRef.current?.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  const items = data?.pages.flatMap(page => page.data) || [];
  const contentItems = items as ContentSearchItem[];
  const userItems = items as UserSearchItem[];

  return (
    <div className="overflow-hidden rounded-lg bg-card text-card-foreground shadow-sm">
      {isLoading ? (
        <div className="divide-y divide-border/50">
          <SearchSkeleton type={type} />
          <SearchSkeleton type={type} />
          <SearchSkeleton type={type} />
        </div>
      ) : items.length > 0 ? (
        <div className="divide-y divide-border/50">
          {type === 'content' || type === 'topic'
            ? contentItems.map(post => <PostCard key={post.id} post={post} />)
            : userItems.map(user => <UserListItem key={user.id} user={user} />)}
        </div>
      ) : (
        <div className="py-10 text-center text-muted-foreground">
          {query.trim()
            ? copywriting('search.empty_results', '没有找到匹配结果。')
            : copywriting('search.empty_query', '输入关键词开始搜索。')}
        </div>
      )}

      <div ref={loadMoreRef} className="border-t border-border/50 py-3 text-center">
        {isFetchingNextPage && (
          <div className="flex items-center justify-center gap-2 text-muted-foreground">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            {copywriting('common.loading', '加载中...')}
          </div>
        )}
        {!hasNextPage && items.length > 0 && (
          <span className="text-sm text-muted-foreground">
            {copywriting('search.end_results', '没有更多结果了')}
          </span>
        )}
      </div>
    </div>
  );
}

function SearchSkeleton({ type }: { type: SearchType }) {
  if (type === 'user') {
    return <UserListItemSkeleton />;
  }

  return (
    <div className="space-y-4 p-3 sm:p-4">
      <div className="flex items-center gap-3">
        <Skeleton className="h-10 w-10 rounded-full" />
        <div className="space-y-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-3 w-16" />
        </div>
      </div>
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-3/4" />
    </div>
  );
}
