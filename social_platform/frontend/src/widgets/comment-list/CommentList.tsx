/**
 * 评论列表组件
 */

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Heart, MessageCircle, CornerDownRight, Repeat2 } from 'lucide-react';
import type { Comment } from '@/features/comment';
import { useToggleCommentLike, useCreateComment } from '@/features/comment';
import {
  getInitialVisibleReplyCount,
  getNextVisibleReplyCount,
  getReplyCount,
} from '@/features/comment/replyVisibility';
import { useRepost } from '@/features/post';
import { useAuthStore } from '@/features/auth';
import { Avatar, Button, Textarea } from '@/shared/components/ui';
import { COMMENT_CONTENT_MAX_LENGTH, POST_CONTENT_MAX_LENGTH } from '@/shared/config/contentLimits';
import { formatDate } from '@/shared/lib/utils';
import { hasVisibleContent } from '@/shared/lib/content';

/**
 * 评论列表组件属性
 */
interface CommentListProps {
  comments: Comment[];
  postId: number;
}

/**
 * 评论列表组件
 */
export function CommentList({ comments, postId }: CommentListProps) {
  if (comments.length === 0) {
    return <div className="text-center py-8 text-muted-foreground">暂无评论，快来抢沙发吧！</div>;
  }

  return (
    <div className="space-y-4">
      {comments.map(comment => (
        <CommentItem
          key={comment.id}
          comment={comment}
          postId={postId}
          depth={0}
          parentOwner={null}
        />
      ))}
    </div>
  );
}

/**
 * 评论项组件属性
 */
interface CommentItemProps {
  comment: Comment;
  postId: number;
  depth: number;
  parentOwner: { id: number; username: string } | null;
  renderReplies?: boolean;
  visibleReplyLimit?: number;
}

/**
 * 评论项组件
 * 展示单条评论及其所有回复（递归平级显示）
 */
function CommentItem({
  comment,
  postId,
  depth,
  parentOwner,
  renderReplies = true,
  visibleReplyLimit,
}: CommentItemProps) {
  const { user } = useAuthStore();
  const toggleCommentLike = useToggleCommentLike(postId, user?.id);
  const { mutate: createComment, isPending } = useCreateComment(postId);
  const repost = useRepost();
  const totalReplies = renderReplies ? getReplyCount(comment) : 0;
  const initialVisibleReplyCount = renderReplies ? getInitialVisibleReplyCount(comment) : 0;

  const [showReplies, setShowReplies] = useState(depth === 0 ? false : true);
  const [visibleReplyCount, setVisibleReplyCount] = useState(initialVisibleReplyCount);
  const [isReplying, setIsReplying] = useState(false);
  const [replyContent, setReplyContent] = useState('');
  const [isReposting, setIsReposting] = useState(false);
  const [repostContent, setRepostContent] = useState('');

  const isTopLevel = depth === 0;
  const isSecondLevel = depth === 1;
  const hasReplies = totalReplies > 0;
  const displayedReplyCount = visibleReplyLimit ?? visibleReplyCount;
  const hasMoreRepliesToShow = visibleReplyLimit === undefined && visibleReplyCount < totalReplies;

  useEffect(() => {
    if (visibleReplyLimit !== undefined) return;

    if (visibleReplyCount > totalReplies) {
      setVisibleReplyCount(totalReplies);
    } else if (visibleReplyCount === 0 && totalReplies > 0) {
      setVisibleReplyCount(getNextVisibleReplyCount(0, totalReplies));
    }
  }, [totalReplies, visibleReplyCount, visibleReplyLimit]);

  /**
   * 处理点赞
   */
  const handleLike = () => {
    if (!user) return;
    toggleCommentLike.mutate({ commentId: comment.id });
  };

  /**
   * 处理回复提交
   */
  const handleReplySubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!hasVisibleContent(replyContent)) return;

    createComment(
      {
        content: replyContent,
        parent_id: comment.id,
      },
      {
        onSuccess: () => {
          setReplyContent('');
          setIsReplying(false);
        },
      }
    );
  };

  return (
    <div className={`${isTopLevel ? 'space-y-3' : ''}`}>
      {/* 评论内容 */}
      <div className={`flex gap-3 ${!isTopLevel ? 'mt-3' : ''}`}>
        <Link to={`/user/${comment.owner_id}`}>
          <Avatar
            src={comment.owner?.avatar_url}
            alt={comment.owner?.username || `用户${comment.owner_id}`}
            size={isTopLevel ? 'md' : 'sm'}
          />
        </Link>
        <div className="flex-1 min-w-0">
          <div className="p-0">
            {/* 用户名显示 */}
            {isTopLevel || isSecondLevel ? (
              // 一级评论和一级回复：只显示用户名
              <Link
                to={`/user/${comment.owner_id}`}
                className="font-medium text-sm hover:text-primary transition-colors"
              >
                {comment.owner?.username || `用户${comment.owner_id}`}
              </Link>
            ) : (
              // 三级及以上（回复的回复）：显示 xxx 回复 xxx
              <div className="flex items-center gap-1 text-sm">
                <Link
                  to={`/user/${comment.owner_id}`}
                  className="font-medium hover:text-primary transition-colors"
                >
                  {comment.owner?.username || `用户${comment.owner_id}`}
                </Link>
                <span className="text-muted-foreground">回复</span>
                <Link
                  to={`/user/${parentOwner?.id || comment.owner_id}`}
                  className="text-muted-foreground hover:text-primary"
                >
                  @{parentOwner?.username || comment.owner?.username}
                </Link>
              </div>
            )}
            <p className="text-sm mt-1 whitespace-pre-wrap break-words">{comment.content}</p>
          </div>

          {/* 操作按钮 */}
          <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
            <span>{formatDate(comment.created_at)}</span>
            <button
              onClick={handleLike}
              disabled={!user}
              className={`flex items-center gap-1 transition-colors ${
                comment.is_liked ? 'text-red-500' : 'hover:text-red-500'
              }`}
            >
              <Heart className={`h-3.5 w-3.5 ${comment.is_liked ? 'fill-current' : ''}`} />
              <span>{comment.like_count}</span>
            </button>
            {user && (
              <button
                onClick={() => setIsReplying(!isReplying)}
                className={`flex items-center gap-1 transition-colors ${
                  isReplying ? 'text-primary' : 'hover:text-primary'
                }`}
              >
                <MessageCircle className="h-3.5 w-3.5" />
                <span>{isReplying ? '取消回复' : '回复'}</span>
              </button>
            )}
            {user && (
              <button
                onClick={() => setIsReposting(value => !value)}
                className={`flex items-center gap-1 transition-colors ${
                  isReposting ? 'text-primary' : 'hover:text-primary'
                }`}
              >
                <Repeat2 className="h-3.5 w-3.5" />
                <span>转发</span>
              </button>
            )}
            {comment.created_by_agent && <span>AI生成</span>}
            {isTopLevel && hasReplies && (
              <button
                onClick={() => setShowReplies(!showReplies)}
                className="flex items-center gap-1 hover:text-primary transition-colors"
              >
                <CornerDownRight className="h-3.5 w-3.5" />
                {showReplies ? '收起回复' : `查看 ${totalReplies} 条回复`}
              </button>
            )}
          </div>

          {/* 回复输入框 */}
          {isReplying && (
            <form onSubmit={handleReplySubmit} className="mt-3 space-y-2">
              <div className="text-xs text-muted-foreground">
                回复 @{comment.owner?.username || '用户'}
              </div>
              <Textarea
                placeholder="写下你的回复..."
                value={replyContent}
                onChange={e => setReplyContent(e.target.value)}
                maxLength={COMMENT_CONTENT_MAX_LENGTH}
                rows={2}
                disabled={isPending}
                className="border-0 shadow-none bg-muted/30 focus-visible:ring-0"
              />
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsReplying(false)}
                >
                  取消
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={!hasVisibleContent(replyContent) || isPending}
                >
                  评论
                </Button>
              </div>
            </form>
          )}

          {isReposting && (
            <form
              onSubmit={e => {
                e.preventDefault();
                if (repost.isPending) return;

                repost.mutate(
                  {
                    source_type: 'comment',
                    source_id: comment.id,
                    content: hasVisibleContent(repostContent) ? repostContent : undefined,
                  },
                  {
                    onSuccess: () => {
                      setRepostContent('');
                      setIsReposting(false);
                    },
                  }
                );
              }}
              className="mt-3 space-y-2"
            >
              <Textarea
                placeholder="写点什么再转发..."
                value={repostContent}
                onChange={e => setRepostContent(e.target.value)}
                maxLength={POST_CONTENT_MAX_LENGTH}
                rows={2}
                disabled={repost.isPending}
                className="border-0 shadow-none bg-muted/30 focus-visible:ring-0"
              />
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsReposting(false)}
                >
                  取消
                </Button>
                <Button type="submit" size="sm" disabled={repost.isPending}>
                  转发
                </Button>
              </div>
            </form>
          )}
        </div>
      </div>

      {/* 回复列表 - 递归平级显示 */}
      {showReplies && hasReplies && (
        <div className={`${isTopLevel ? 'ml-12' : 'ml-0'}`}>
          {(() => {
            let remainingReplyCount = displayedReplyCount;

            return comment.children.map(child => {
              if (remainingReplyCount <= 0) return null;

              const childReplyCount = getReplyCount(child);
              const childVisibleReplyLimit = Math.min(childReplyCount, remainingReplyCount - 1);
              remainingReplyCount -= 1 + childVisibleReplyLimit;

              return (
                <CommentItem
                  key={child.id}
                  comment={child}
                  postId={postId}
                  depth={depth + 1}
                  parentOwner={{
                    id: comment.owner_id,
                    username: comment.owner?.username || `用户${comment.owner_id}`,
                  }}
                  visibleReplyLimit={childVisibleReplyLimit}
                />
              );
            });
          })()}
          {hasMoreRepliesToShow && (
            <button
              type="button"
              onClick={() =>
                setVisibleReplyCount(count => getNextVisibleReplyCount(count, totalReplies))
              }
              className="mt-3 text-sm text-primary transition-colors hover:text-primary/80"
            >
              展开更多回复 ({visibleReplyCount}/{totalReplies})
            </button>
          )}
        </div>
      )}
    </div>
  );
}
