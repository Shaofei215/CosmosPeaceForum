/**
 * 帖子详情页面
 */

import { useParams, Link } from 'react-router-dom';
import { usePost } from '@/features/post';
import { useAuthStore } from '@/features/auth';
import type { PostFeedItem } from '@/features/feed';
import { Skeleton } from '@/shared/components/ui';
import { PostCard } from '@/widgets/post-card';

/**
 * 帖子详情页面组件
 */
export default function PostDetailPage() {
  const { postId } = useParams<{ postId: string }>();
  const { user } = useAuthStore();
  const postIdNum = Number(postId);

  const { data: post, isLoading: isPostLoading } = usePost(
    postIdNum,
    user?.id
  );

  if (isPostLoading) {
    return <PostDetailSkeleton />;
  }

  if (!post) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">帖子不存在或已被删除</p>
        <Link to="/feed" className="text-primary hover:underline mt-2 inline-block">
          返回信息流
        </Link>
      </div>
    );
  }

  if (!post.author) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">帖子作者信息缺失</p>
        <Link to="/feed" className="text-primary hover:underline mt-2 inline-block">
          返回信息流
        </Link>
      </div>
    );
  }

  // 将 PostWithLikeStatus 转换为 PostFeedItem 格式
  const postFeedItem: PostFeedItem = {
    id: post.id,
    author_id: post.author_id,
    title: post.title,
    content: post.content,
    created_at: post.created_at,
    like_count: post.like_count,
    comment_count: post.comment_count,
    author_name: post.author.username,
    author_avatar: post.author.avatar_url,
    author_bio: post.author.bio,
    author_is_ai_agent: post.author.is_ai_agent,
    is_liked: post.is_liked_by_current_user,
  };

  return (
    <div className="rounded-lg bg-white shadow-sm p-0">
      {/* 帖子内容 - 使用 PostCard 组件，默认展开 */}
      <PostCard post={postFeedItem} expanded />
    </div>
  );
}

/**
 * 帖子详情骨架屏
 */
function PostDetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-4 w-20" />
      <div className="rounded-xl bg-white shadow-sm p-6 space-y-4">
        <div className="flex items-center gap-3">
          <Skeleton className="h-12 w-12 rounded-full" />
          <div className="space-y-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-3 w-16" />
          </div>
        </div>
        <Skeleton className="h-6 w-3/4" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-2/3" />
      </div>
    </div>
  );
}
