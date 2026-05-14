/**
 * 关注列表页面
 * 展示用户的关注列表
 */

import { useEffect, useRef } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useInfiniteFollowingList } from '@/features/follow';
import { Avatar, Skeleton } from '@/shared/components/ui';
import type { FollowUserItem } from '@/features/follow';

export default function FollowingListPage() {
  const { userId } = useParams<{ userId: string }>();
  const userIdNum = Number(userId);

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    isError,
  } = useInfiniteFollowingList(userIdNum);

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

  const followingList = data?.pages.flatMap((page) => page.data) || [];

  if (isError) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">加载失败，请稍后重试</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg bg-white p-0 shadow-sm">
      <h2 className="text-lg font-semibold px-3 pt-3">关注</h2>

      {isLoading ? (
        <div className="divide-y divide-border/50">
          <UserItemSkeleton />
          <UserItemSkeleton />
          <UserItemSkeleton />
        </div>
      ) : followingList.length > 0 ? (
        <div className="divide-y divide-border/50">
          {followingList.map((item) => (
            <UserItem key={item.id} user={item} />
          ))}
        </div>
      ) : (
        <div className="text-center py-10 text-muted-foreground">
          暂无关注
        </div>
      )}

      <div ref={loadMoreRef} className="py-3 text-center border-t border-border/50">
        {isFetchingNextPage && (
          <div className="flex items-center justify-center gap-2 text-muted-foreground">
            <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
            加载中...
          </div>
        )}
        {!hasNextPage && followingList.length > 0 && (
          <span className="text-muted-foreground text-sm">没有更多了</span>
        )}
      </div>
    </div>
  );
}

interface UserItemProps {
  user: FollowUserItem;
}

function UserItem({ user }: UserItemProps) {
  return (
    <Link
      to={`/user/${user.id}`}
      className="flex items-center gap-3 px-3 py-2"
    >
      <Avatar src={user.avatar_url} alt={user.username} size="md" />
      <div className="flex-1 min-w-0">
        <div className="font-medium text-foreground truncate">
          {user.username}
        </div>
        {user.bio && (
          <p className="text-sm text-muted-foreground truncate mt-0.5">
            {user.bio}
          </p>
        )}
      </div>
    </Link>
  );
}

function UserItemSkeleton() {
  return (
    <div className="flex items-center gap-3 px-3 py-2">
      <Skeleton className="h-10 w-10 rounded-full" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-3 w-32" />
      </div>
    </div>
  );
}
