/**
 * 帖子详情页面
 */

import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Heart, MessageCircle } from 'lucide-react';
import { usePost } from '@/features/post';
import { useComments, useCreateComment } from '@/features/comment';
import { useToggleLike } from '@/features/like';
import { useAuthStore } from '@/features/auth';
import { useUser } from '@/features/user';
import { Avatar, Button, Skeleton, Textarea } from '@/shared/components/ui';
import { formatDate } from '@/shared/lib/utils';
import { CommentList } from '@/widgets/comment-list';
import { useState } from 'react';

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
  const { data: author, isLoading: isAuthorLoading } = useUser(
    post?.author_id ?? 0
  );
  const { data: commentsData, isLoading: isCommentsLoading } = useComments(
    postIdNum,
    user?.id
  );
  const { mutate: toggleLike } = useToggleLike();
  const { mutate: createComment, isPending: isCreatingComment } =
    useCreateComment(postIdNum);

  const [commentContent, setCommentContent] = useState('');

  /**
   * 处理点赞
   */
  const handleLike = () => {
    if (!user) return;
    toggleLike(postIdNum);
  };

  /**
   * 处理评论提交
   */
  const handleCommentSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentContent.trim()) return;

    createComment(
      { content: commentContent.trim() },
      {
        onSuccess: () => {
          setCommentContent('');
        },
      }
    );
  };

  if (isPostLoading || isAuthorLoading) {
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

  return (
    <div className="space-y-6">
      {/* 返回按钮 */}
      <Link
        to="/feed"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        返回
      </Link>

      {/* 帖子内容 */}
      <article className="rounded-xl border bg-card p-6 shadow-sm">
        {/* 作者信息 */}
        <div className="flex items-center gap-3 mb-4">
          <Link to={`/user/${post.author_id}`}>
            <Avatar
              src={author?.avatar_url}
              alt={author?.username || post.author_id.toString()}
              size="lg"
            />
          </Link>
          <div>
            <Link
              to={`/user/${post.author_id}`}
              className="font-medium hover:text-primary transition-colors"
            >
              {author?.username || `用户${post.author_id}`}
            </Link>
            <p className="text-sm text-muted-foreground">
              {formatDate(post.created_at)}
            </p>
          </div>
        </div>

        {/* 内容 */}
        {post.title && <h1 className="text-2xl font-bold mb-4">{post.title}</h1>}
        <div className="prose prose-sm max-w-none whitespace-pre-wrap">
          {post.content}
        </div>

        {/* 互动按钮 */}
        <div className="flex items-center gap-6 mt-6 pt-4 border-t">
          <button
            onClick={handleLike}
            disabled={!user}
            className={`flex items-center gap-2 transition-colors ${
              post.is_liked_by_current_user
                ? 'text-red-500'
                : 'text-muted-foreground hover:text-red-500'
            }`}
          >
            <Heart
              className={`h-5 w-5 ${
                post.is_liked_by_current_user ? 'fill-current' : ''
              }`}
            />
            <span>{post.like_count}</span>
          </button>
          <div className="flex items-center gap-2 text-muted-foreground">
            <MessageCircle className="h-5 w-5" />
            <span>{post.comment_count}</span>
          </div>
        </div>
      </article>

      {/* 评论区域 */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">
          评论 ({commentsData?.total || 0})
        </h2>

        {/* 评论输入框（仅登录用户） */}
        {user && (
          <form onSubmit={handleCommentSubmit} className="space-y-3">
            <Textarea
              placeholder="写下你的评论..."
              value={commentContent}
              onChange={(e) => setCommentContent(e.target.value)}
              rows={3}
              disabled={isCreatingComment}
            />
            <div className="flex justify-end">
              <Button
                type="submit"
                disabled={!commentContent.trim() || isCreatingComment}
                size="sm"
              >
                {isCreatingComment ? '发送中...' : '发送评论'}
              </Button>
            </div>
          </form>
        )}

        {/* 评论列表 */}
        {isCommentsLoading ? (
          <CommentListSkeleton />
        ) : (
          <CommentList
            comments={commentsData?.items || []}
            postId={postIdNum}
          />
        )}
      </div>
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
      <div className="rounded-xl border bg-card p-6 shadow-sm space-y-4">
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

/**
 * 评论列表骨架屏
 */
function CommentListSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((i) => (
        <div key={i} className="flex gap-3">
          <Skeleton className="h-10 w-10 rounded-full shrink-0" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-full" />
          </div>
        </div>
      ))}
    </div>
  );
}
