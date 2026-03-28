/**
 * 帖子卡片组件
 * 展示单个帖子的摘要信息
 */

import { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Heart, MessageCircle, ChevronDown, ChevronUp, Send, CornerDownRight, ChevronDown as ExpandIcon } from 'lucide-react';
import type { PostFeedItem } from '@/features/feed';
import type { PostWithLikeStatus } from '@/features/post';
import type { Comment } from '@/features/comment';
import { Avatar, Skeleton, Button, Textarea } from '@/shared/components/ui';
import { formatDate } from '@/shared/lib/utils';
import { useToggleLike } from '@/features/like';
import { useComments, useCreateComment, useToggleCommentLike } from '@/features/comment';
import { useAuthStore } from '@/features/auth';

/**
 * 帖子卡片组件属性
 */
interface PostCardProps {
  post: PostFeedItem | PostWithLikeStatus;
  expanded?: boolean;
}

/**
 * 帖子卡片组件
 */
export function PostCard({ post, expanded = false }: PostCardProps) {
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuthStore();
  const toggleLike = useToggleLike();
  const [isCommentsExpanded, setIsCommentsExpanded] = useState(expanded);
  const [isContentExpanded, setIsContentExpanded] = useState(expanded);
  const [isContentTruncated, setIsContentTruncated] = useState(false);
  const contentRef = useRef<HTMLParagraphElement>(null);
  const [newCommentContent, setNewCommentContent] = useState('');
  const [replyingTo, setReplyingTo] = useState<{ id: number; username: string } | null>(null);

  // 适配两种数据类型的字段
  const authorName = 'author_name' in post ? post.author_name : `用户${post.author_id}`;
  const authorAvatar = 'author_avatar' in post ? post.author_avatar : null;
  const authorBio = 'author_bio' in post ? post.author_bio : null;
  const isLiked = 'is_liked' in post ? post.is_liked : post.is_liked_by_current_user;

  // 检测内容是否被截断
  useEffect(() => {
    if (contentRef.current) {
      const element = contentRef.current;
      // 如果实际高度大于行高*3，说明内容被截断了
      const lineHeight = parseInt(getComputedStyle(element).lineHeight) || 24;
      const maxHeight = lineHeight * 3;
      setIsContentTruncated(element.scrollHeight > maxHeight + 1);
    }
  }, [post.content]);

  // 获取评论列表（仅在展开时请求）
  const { data: commentsData, isLoading: isCommentsLoading } = useComments(
    post.id,
    user?.id,
  );

  // 创建评论（一级评论）
  const createComment = useCreateComment(post.id);

  const handleLike = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    toggleLike.mutate(post.id);
  };

  const handleCommentClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsCommentsExpanded(!isCommentsExpanded);
  };

  const handleViewAllComments = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    navigate(`/post/${post.id}`);
  };

  const handleSubmitNewComment = async (e: React.FormEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (!newCommentContent.trim() || createComment.isPending) return;

    createComment.mutate(
      { content: newCommentContent.trim() },
      {
        onSuccess: () => {
          setNewCommentContent('');
        },
      }
    );
  };

  const handleReply = (commentId: number, username: string) => {
    setReplyingTo({ id: commentId, username });
  };

  const handleCancelReply = () => {
    setReplyingTo(null);
  };

  const handleReplySuccess = () => {
    setReplyingTo(null);
  };

  // 获取评论：展开模式显示所有，非展开模式显示前5条
  const previewComments = expanded
    ? (commentsData?.items || [])
    : (commentsData?.items?.slice(0, 5) || []);
  const hasMoreComments = !expanded && (commentsData?.total || 0) > 5;

  return (
    <article className="rounded-xl bg-card/40 backdrop-blur-md supports-[backdrop-filter]:bg-card/30 p-4 hover:bg-card/50 transition-colors">
      {/* 头部：作者信息 */}
      <div className="flex items-center gap-3 mb-3">
        <Link to={`/user/${post.author_id}`}>
          <Avatar
            src={authorAvatar}
            alt={authorName}
            size="md"
          />
        </Link>
        <div className="flex-1 min-w-0">
          <Link
            to={`/user/${post.author_id}`}
            className="font-medium text-foreground hover:text-primary transition-colors"
          >
            {authorName}
          </Link>
          {authorBio && (
            <p className="text-xs text-muted-foreground truncate max-w-[200px]">
              {authorBio}
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            {formatDate(post.created_at)}
          </p>
        </div>
      </div>

      {/* 内容 */}
      <div className="block">
        {post.title && (
          <Link to={`/post/${post.id}`}>
            <h3 className="font-semibold text-lg mb-2 line-clamp-2">
              {post.title}
            </h3>
          </Link>
        )}
        <p
          ref={contentRef}
          className={`text-foreground/90 whitespace-pre-wrap ${
            isContentExpanded ? '' : 'line-clamp-3'
          }`}
        >
          {post.content}
        </p>
        {/* 展开/收起按钮 - 仅在内容被截断时显示 */}
        {isContentTruncated && (
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setIsContentExpanded(!isContentExpanded);
            }}
            className="mt-2 text-sm text-primary hover:text-primary/80 transition-colors flex items-center gap-1"
          >
            {isContentExpanded ? (
              <>
                <ChevronUp className="h-3 w-3" />
                收起
              </>
            ) : (
              <>
                <ExpandIcon className="h-3 w-3" />
                展开
              </>
            )}
          </button>
        )}
      </div>

      {/* 底部：互动按钮 */}
      <div className="flex items-center gap-6 mt-4 pt-3 border-t">
        <button
          className={`flex items-center gap-1.5 text-sm transition-colors ${
            isLiked
              ? 'text-red-500'
              : 'text-muted-foreground hover:text-red-500'
          }`}
          onClick={handleLike}
          disabled={toggleLike.isPending}
        >
          <Heart
            className={`h-4 w-4 ${isLiked ? 'fill-current' : ''}`}
          />
          <span>{post.like_count}</span>
        </button>
        <button
          className={`flex items-center gap-1.5 text-sm transition-colors ${
            isCommentsExpanded
              ? 'text-primary'
              : 'text-muted-foreground hover:text-primary'
          }`}
          onClick={handleCommentClick}
        >
          <MessageCircle className="h-4 w-4" />
          <span>{post.comment_count}</span>
          {isCommentsExpanded ? (
            <ChevronUp className="h-3 w-3" />
          ) : (
            <ChevronDown className="h-3 w-3" />
          )}
        </button>
      </div>

      {/* 评论预览区域 */}
      {isCommentsExpanded && (
        <div className="mt-4 pt-4 border-t border-dashed">
          {/* 发表评论输入框 - 仅登录用户可见，且不在回复其他评论时显示 */}
          {isAuthenticated && !replyingTo && (
            <form onSubmit={handleSubmitNewComment} className="mb-4">
              <div className="flex gap-2">
                <Avatar
                  src={null}
                  alt={user?.username || '用户'}
                  size="sm"
                />
                <div className="flex-1 space-y-2">
                  <Textarea
                    placeholder="写下你的评论..."
                    value={newCommentContent}
                    onChange={(e) => setNewCommentContent(e.target.value)}
                    className="min-h-[60px] resize-none border-0 shadow-none bg-muted/30 focus-visible:ring-0"
                    onClick={(e) => e.stopPropagation()}
                  />
                  <div className="flex justify-end">
                    <Button
                      type="submit"
                      size="sm"
                      disabled={!newCommentContent.trim() || createComment.isPending}
                      className="gap-1"
                    >
                      {createComment.isPending ? (
                        <div className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
                      ) : (
                        <Send className="h-3 w-3" />
                      )}
                      发表评论
                    </Button>
                  </div>
                </div>
              </div>
            </form>
          )}

          {isCommentsLoading ? (
            <div className="space-y-3">
              <CommentSkeleton />
              <CommentSkeleton />
            </div>
          ) : previewComments.length > 0 ? (
            <div className="space-y-3">
              {previewComments.map((comment) => (
                <CommentItem
                  key={comment.id}
                  comment={comment}
                  postId={post.id}
                  isAuthenticated={isAuthenticated}
                  currentUserId={user?.id}
                  user={user}
                  replyingTo={replyingTo}
                  onReply={handleReply}
                  onCancelReply={handleCancelReply}
                  onReplySuccess={handleReplySuccess}
                  depth={0}
                  parentOwner={null}
                />
              ))}

              {/* 查看更多评论按钮 */}
              {hasMoreComments && (
                <button
                  onClick={handleViewAllComments}
                  className="w-full text-center py-2 text-sm text-primary hover:text-primary/80 transition-colors"
                >
                  查看所有 {commentsData?.total} 条评论
                </button>
              )}
            </div>
          ) : (
            <p className="text-center text-sm text-muted-foreground py-4">
              {isAuthenticated ? '暂无评论，快来发表第一条评论吧！' : '暂无评论，登录后发表你的看法吧！'}
            </p>
          )}
        </div>
      )}
    </article>
  );
}

/**
 * 评论骨架屏
 */
function CommentSkeleton() {
  return (
    <div className="flex gap-2">
      <Skeleton className="h-8 w-8 rounded-full flex-shrink-0" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-16 w-full rounded-lg" />
      </div>
    </div>
  );
}

/**
 * 评论项组件属性
 */
interface CommentItemProps {
  comment: Comment;
  postId: number;
  isAuthenticated: boolean;
  currentUserId?: number;
  user: { id: number; username: string } | null;
  replyingTo: { id: number; username: string } | null;
  onReply: (commentId: number, username: string) => void;
  onCancelReply: () => void;
  onReplySuccess: () => void;
  depth: number;
  parentOwner: { id: number; username: string } | null;
}

/**
 * 评论项组件
 * 展示单条评论及其所有回复（递归平级显示）
 */
function CommentItem({
  comment,
  postId,
  isAuthenticated,
  currentUserId,
  user,
  replyingTo,
  onReply,
  onCancelReply,
  onReplySuccess,
  depth,
  parentOwner,
}: CommentItemProps) {
  const [showReplies, setShowReplies] = useState(depth === 0 ? false : true);
  const toggleCommentLike = useToggleCommentLike(postId, currentUserId);
  const isReplying = replyingTo?.id === comment.id;

  const handleLike = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    toggleCommentLike.mutate({ commentId: comment.id });
  };

  const handleReplyClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (isReplying) {
      onCancelReply();
    } else {
      onReply(comment.id, comment.owner.username);
    }
  };

  const hasReplies = comment.children && comment.children.length > 0;
  const isTopLevel = depth === 0;
  const isSecondLevel = depth === 1;

  return (
    <div className={`${isTopLevel ? 'space-y-3' : ''}`}>
      {/* 评论内容 */}
      <div className={`flex gap-2 ${!isTopLevel ? 'mt-3' : ''}`}>
        <Avatar
          src={comment.owner.avatar_url}
          alt={comment.owner.username}
          size="sm"
        />
        <div className="flex-1 min-w-0">
          <div className="px-0 py-0">
            {/* 用户名显示 */}
            {isTopLevel || isSecondLevel ? (
              // 一级评论和一级回复：只显示用户名
              <Link
                to={`/user/${comment.owner_id}`}
                className="text-sm font-medium text-foreground/70 hover:text-primary"
              >
                {comment.owner.username}
              </Link>
            ) : (
              // 三级及以上（回复的回复）：显示 xxx 回复 xxx
              <div className="flex items-center gap-1 text-sm">
                <Link
                  to={`/user/${comment.owner_id}`}
                  className="font-medium text-foreground/70 hover:text-primary"
                >
                  {comment.owner.username}
                </Link>
                <span className="text-muted-foreground">回复</span>
                <Link
                  to={`/user/${parentOwner?.id || comment.owner_id}`}
                  className="text-muted-foreground hover:text-primary"
                >
                  @{parentOwner?.username || comment.owner.username}
                </Link>
              </div>
            )}
            <p className="text-sm text-foreground/85 mt-0.5 whitespace-pre-wrap break-words">
              {comment.content}
            </p>
          </div>
          <div className="flex items-center gap-4 mt-1 ml-1">
            <span className="text-xs text-muted-foreground">
              {formatDate(comment.created_at)}
            </span>
            <button
              onClick={handleLike}
              disabled={toggleCommentLike.isPending}
              className={`flex items-center gap-1 text-xs transition-colors ${
                comment.is_liked
                  ? 'text-red-500'
                  : 'text-muted-foreground hover:text-red-500'
              }`}
            >
              <Heart
                className={`h-3 w-3 ${comment.is_liked ? 'fill-current' : ''}`}
              />
              {comment.like_count > 0 && <span>{comment.like_count}</span>}
            </button>
            {isAuthenticated && (
              <button
                onClick={handleReplyClick}
                className={`text-xs transition-colors ${
                  isReplying
                    ? 'text-primary'
                    : 'text-muted-foreground hover:text-primary'
                }`}
              >
                {isReplying ? '取消回复' : '回复'}
              </button>
            )}
            {isTopLevel && hasReplies && (
              <button
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setShowReplies(!showReplies);
                }}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors"
              >
                <CornerDownRight className="h-3 w-3" />
                {showReplies ? '收起回复' : `查看 ${comment.reply_count} 条回复`}
              </button>
            )}
          </div>

          {/* 回复输入框 */}
          {isReplying && user && replyingTo && (
            <ReplyInput
              postId={postId}
              parentId={replyingTo.id}
              replyToUsername={replyingTo.username}
              onCancel={onCancelReply}
              onSuccess={onReplySuccess}
            />
          )}
        </div>
      </div>

      {/* 回复列表 - 递归平级显示 */}
      {showReplies && hasReplies && (
        <div className={`${isTopLevel ? 'pl-8' : 'pl-0'}`}>
          {comment.children.map((child) => (
            <CommentItem
              key={child.id}
              comment={child}
              postId={postId}
              isAuthenticated={isAuthenticated}
              currentUserId={currentUserId}
              user={user}
              replyingTo={replyingTo}
              onReply={onReply}
              onCancelReply={onCancelReply}
              onReplySuccess={onReplySuccess}
              depth={depth + 1}
              parentOwner={{ id: comment.owner_id, username: comment.owner.username }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * 回复输入框组件
 */
function ReplyInput({
  postId,
  parentId,
  replyToUsername,
  onCancel,
  onSuccess,
}: {
  postId: number;
  parentId: number;
  replyToUsername: string;
  onCancel: () => void;
  onSuccess: () => void;
}) {
  const [content, setContent] = useState('');
  const createComment = useCreateComment(postId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (!content.trim() || createComment.isPending) return;

    createComment.mutate(
      {
        content: content.trim(),
        parent_id: parentId,
      },
      {
        onSuccess: () => {
          onSuccess();
        },
      }
    );
  };

  return (
    <form onSubmit={handleSubmit} className="mt-3">
      <div className="flex gap-2">
        <div className="flex-1 space-y-2">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>回复 @{replyToUsername}</span>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onCancel();
              }}
              className="text-primary hover:text-primary/80"
            >
              取消
            </button>
          </div>
          <Textarea
            placeholder="写下你的回复..."
            value={content}
            onChange={(e) => setContent(e.target.value)}
            className="min-h-[60px] resize-none border-0 shadow-none bg-muted/30 focus-visible:ring-0"
            onClick={(e) => e.stopPropagation()}
            autoFocus
          />
          <div className="flex justify-end">
            <Button
              type="submit"
              size="sm"
              disabled={!content.trim() || createComment.isPending}
              className="gap-1"
            >
              {createComment.isPending ? (
                <div className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
              ) : (
                <Send className="h-3 w-3" />
              )}
              发送
            </Button>
          </div>
        </div>
      </div>
    </form>
  );
}
