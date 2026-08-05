/**
 * 信息流页面
 * 展示全局帖子流
 */

import { useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useInfiniteGlobalFeed } from '@/features/feed';
import type { FeedType } from '@/features/feed';
import { useAuthStore } from '@/features/auth';
import { PostCard } from '@/widgets/post-card';
import { Skeleton } from '@/shared/components/ui';
import { copywriting } from '@/shared/config/copywriting';

/**
 * 信息流页面组件
 */
export default function FeedPage() {
  const { user } = useAuthStore();
  const [searchParams] = useSearchParams();
  const requestedFeedType = searchParams.get('feed_type');
  // URL 只接受后端支持的三种流；缺省时显示推荐流。
  const feedType: FeedType =
    requestedFeedType === 'latest' || requestedFeedType === 'following'
      ? requestedFeedType
      : 'recommended';
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } = useInfiniteGlobalFeed(
    user?.id,
    feedType
  );

  // 无限滚动监听
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

  // 合并所有页面的帖子
  const posts = data?.pages.flatMap(page => page.data) || [];

  return (
    <div className="overflow-hidden rounded-lg bg-card p-0 text-card-foreground shadow-sm">
      {/* 帖子列表 */}
      {isLoading ? (
        // 加载骨架屏
        <div className="divide-y divide-border/50">
          <PostCardSkeleton />
          <PostCardSkeleton />
          <PostCardSkeleton />
        </div>
      ) : posts.length > 0 ? (
        <div className="divide-y divide-border/50">
          {posts.map(post => (
            <PostCard key={post.id} post={post} />
          ))}
        </div>
      ) : (
        <div className="text-center py-10 text-muted-foreground">
          {feedType === 'following'
            ? copywriting('feed.empty_following', '关注的人还没有新内容。')
            : copywriting('feed.empty_global', '暂无帖子，快来发布第一条吧！')}
        </div>
      )}

      {/* 加载更多 */}
      <div ref={loadMoreRef} className="py-3 text-center border-t border-border/50">
        {isFetchingNextPage && (
          <div className="flex items-center justify-center gap-2 text-muted-foreground">
            <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
            {copywriting('common.loading', '加载中...')}
          </div>
        )}
        {!hasNextPage && posts.length > 0 && (
          <span className="text-muted-foreground text-sm">
            {copywriting('common.no_more_content', '没有更多内容了')}
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * 帖子卡片骨架屏
 */
function PostCardSkeleton() {
  return (
    <div className="space-y-4 rounded-lg bg-card p-3 sm:p-4">
      <div className="flex items-center gap-3">
        <Skeleton className="h-10 w-10 rounded-full" />
        <div className="space-y-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-3 w-16" />
        </div>
      </div>
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-3/4" />
      <div className="flex gap-4 pt-2">
        <Skeleton className="h-8 w-16" />
        <Skeleton className="h-8 w-16" />
      </div>
    </div>
  );
}
