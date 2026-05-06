import { Link, useParams, useSearchParams } from 'react-router-dom';
import { usePost } from '@/features/post';
import { useAuthStore } from '@/features/auth';
import { Skeleton } from '@/shared/components/ui';
import { PostCard } from '@/widgets/post-card';

export default function PostDetailPage() {
  const { postId } = useParams<{ postId: string }>();
  const [searchParams] = useSearchParams();
  const { user } = useAuthStore();
  const postIdNum = Number(postId);
  const focusedCommentId = Number(searchParams.get('commentId') || 0) || undefined;

  const { data: post, isLoading: isPostLoading } = usePost(postIdNum, user?.id);

  if (isPostLoading) {
    return <PostDetailSkeleton />;
  }

  if (!post) {
    return (
      <div className="py-12 text-center">
        <p className="text-muted-foreground">帖子不存在或已被删除</p>
        <Link to="/feed" className="mt-2 inline-block text-primary hover:underline">
          返回信息流
        </Link>
      </div>
    );
  }

  return (
    <div className="rounded-lg bg-white p-0 shadow-sm">
      <PostCard post={post} expanded focusedCommentId={focusedCommentId} />
    </div>
  );
}

function PostDetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-4 w-20" />
      <div className="space-y-4 rounded-xl bg-white p-6 shadow-sm">
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
