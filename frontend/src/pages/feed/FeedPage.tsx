/**
 * 信息流页面
 * 展示全局帖子流
 */

import { useEffect, useRef } from 'react';
import { useInfiniteGlobalFeed } from '@/features/feed';
import { useAuthStore } from '@/features/auth';
import { PostCard } from '@/widgets/post-card';
import { CreatePostForm } from '@/widgets/create-post-form';
import { Skeleton } from '@/shared/components/ui';

/**
 * 信息流页面组件
 */
export default function FeedPage() {
  const { user } = useAuthStore();
  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
  } = useInfiniteGlobalFeed(user?.id);

  // 无限滚动监听
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

  // 合并所有页面的帖子
  const posts = data?.pages.flatMap((page) => page.data) || [];

  return (
    <div className="space-y-6">
      {/* 创建帖子表单（仅登录用户可见） */}
      {user && <CreatePostForm />}

      {/* 帖子列表 */}
      <div className="space-y-4">
        {isLoading ? (
          // 加载骨架屏
          <>
            <PostCardSkeleton />
            <PostCardSkeleton />
            <PostCardSkeleton />
          </>
        ) : posts.length > 0 ? (
          posts.map((post) => (
            <PostCard key={post.id} post={post} />
          ))
        ) : (
          <div className="text-center py-12 text-muted-foreground">
            暂无帖子，快来发布第一条吧！
          </div>
        )}
      </div>

      {/* 加载更多 */}
      <div ref={loadMoreRef} className="py-4 text-center">
        {isFetchingNextPage && (
          <div className="flex items-center justify-center gap-2 text-muted-foreground">
            <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
            加载中...
          </div>
        )}
        {!hasNextPage && posts.length > 0 && (
          <span className="text-muted-foreground text-sm">没有更多内容了</span>
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
    <div className="rounded-xl border bg-card p-4 shadow space-y-4">
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
