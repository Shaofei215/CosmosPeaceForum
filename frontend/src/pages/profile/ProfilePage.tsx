/**
 * 用户资料页面
 */

import { useParams, Link } from 'react-router-dom';
import { useEffect, useRef } from 'react';
import { useUser } from '@/features/user';
import { useInfiniteUserFeed } from '@/features/feed';
import { useAuthStore } from '@/features/auth';
import { PostCard } from '@/widgets/post-card';
import { Avatar, Skeleton } from '@/shared/components/ui';
import { formatDate } from '@/shared/lib/utils';

/**
 * 用户资料页面组件
 */
export default function ProfilePage() {
  const { userId } = useParams<{ userId: string }>();
  const { user: currentUser } = useAuthStore();
  const userIdNum = Number(userId);

  const { data: user, isLoading: isUserLoading } = useUser(userIdNum);
  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading: isFeedLoading,
  } = useInfiniteUserFeed(userIdNum, currentUser?.id);

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

  if (isUserLoading) {
    return <ProfileSkeleton />;
  }

  if (!user) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">用户不存在</p>
        <Link to="/feed" className="text-primary hover:underline mt-2 inline-block">
          返回信息流
        </Link>
      </div>
    );
  }

  const isCurrentUser = currentUser?.id === user.id;

  return (
    <div className="space-y-6">
      {/* 用户资料卡片 */}
      <div className="rounded-xl border bg-card p-6 shadow-sm">
        <div className="flex items-start gap-4">
          <Avatar
            src={user.avatar_url}
            alt={user.username}
            size="xl"
          />
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold">{user.username}</h1>
            <p className="text-sm text-muted-foreground mt-1">
              加入于 {formatDate(user.created_at)}
            </p>
            {user.bio && (
              <p className="mt-3 text-muted-foreground whitespace-pre-wrap">
                {user.bio}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* 用户帖子列表 */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">
          {isCurrentUser ? '我的帖子' : `${user.username} 的帖子`}
        </h2>

        {isFeedLoading ? (
          <>
            <PostCardSkeleton />
            <PostCardSkeleton />
          </>
        ) : posts.length > 0 ? (
          posts.map((post) => <PostCard key={post.id} post={post} />)
        ) : (
          <div className="text-center py-12 text-muted-foreground">
            暂无帖子
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
 * 用户资料骨架屏
 */
function ProfileSkeleton() {
  return (
    <div className="space-y-6">
      <div className="rounded-xl border bg-card p-6 shadow-sm">
        <div className="flex items-start gap-4">
          <Skeleton className="h-16 w-16 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-8 w-32" />
            <Skeleton className="h-4 w-24" />
          </div>
        </div>
      </div>
      <PostCardSkeleton />
      <PostCardSkeleton />
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
    </div>
  );
}
