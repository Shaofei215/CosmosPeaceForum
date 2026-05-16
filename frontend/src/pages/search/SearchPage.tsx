import { useEffect, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Bot, User as UserIcon } from 'lucide-react';
import { useInfiniteSearch, type ContentSearchItem, type SearchType } from '@/features/search';
import type { UserSearchItem } from '@/features/search';
import { PostCard } from '@/widgets/post-card';
import { Avatar, Skeleton } from '@/shared/components/ui';

export default function SearchPage() {
  const [searchParams] = useSearchParams();
  const query = searchParams.get('q') || '';
  const requestedType = searchParams.get('type');
  const type: SearchType = requestedType === 'user' ? 'user' : 'content';

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
  } = useInfiniteSearch(type, query);

  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (observerRef.current) {
      observerRef.current.disconnect();
    }

    observerRef.current = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
        fetchNextPage();
      }
    });

    if (loadMoreRef.current) {
      observerRef.current.observe(loadMoreRef.current);
    }

    return () => observerRef.current?.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  const items = data?.pages.flatMap((page) => page.data) || [];
  const contentItems = items as ContentSearchItem[];
  const userItems = items as UserSearchItem[];

  return (
    <div className="overflow-hidden rounded-lg bg-white shadow-sm">
      {isLoading ? (
        <div className="divide-y divide-border/50">
          <SearchSkeleton type={type} />
          <SearchSkeleton type={type} />
          <SearchSkeleton type={type} />
        </div>
      ) : items.length > 0 ? (
        <div className="divide-y divide-border/50">
          {type === 'content'
            ? contentItems.map((post) => <PostCard key={post.id} post={post} />)
            : userItems.map((user) => <UserResult key={user.id} user={user} />)}
        </div>
      ) : (
        <div className="py-10 text-center text-muted-foreground">
          {query.trim() ? '没有找到匹配结果。' : '输入关键词开始搜索。'}
        </div>
      )}

      <div ref={loadMoreRef} className="border-t border-border/50 py-3 text-center">
        {isFetchingNextPage && (
          <div className="flex items-center justify-center gap-2 text-muted-foreground">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            加载中...
          </div>
        )}
        {!hasNextPage && items.length > 0 && (
          <span className="text-sm text-muted-foreground">没有更多结果了</span>
        )}
      </div>
    </div>
  );
}

function UserResult({ user }: { user: UserSearchItem }) {
  return (
    <Link
      to={`/user/${user.id}`}
      className="flex items-center gap-3 p-3 transition-colors hover:bg-muted/40 sm:p-4"
    >
      <Avatar src={user.avatar_url} alt={user.username} size="md" />
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate font-medium text-foreground">{user.username}</span>
          {user.is_ai_agent && (
            <span className="inline-flex h-5 shrink-0 items-center gap-1 rounded-full bg-primary/10 px-2 text-xs text-primary">
              <Bot className="h-3 w-3" />
              AI
            </span>
          )}
        </div>
        <p className="mt-0.5 truncate text-sm text-muted-foreground">
          {user.bio || '还没有签名'}
        </p>
        <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
          <span>{user.followers_count || 0} 粉丝</span>
          <span>{user.following_count || 0} 关注</span>
        </div>
      </div>
    </Link>
  );
}

function SearchSkeleton({ type }: { type: SearchType }) {
  if (type === 'user') {
    return (
      <div className="flex items-center gap-3 p-3 sm:p-4">
        <Skeleton className="h-10 w-10 rounded-full" />
        <div className="min-w-0 flex-1 space-y-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-48" />
        </div>
        <UserIcon className="h-4 w-4 text-muted-foreground" />
      </div>
    );
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
