import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ChevronDown as ExpandIcon,
  ChevronUp,
  CornerDownRight,
  Heart,
  MessageCircle,
  Repeat2,
} from 'lucide-react';
import type { PostFeedItem } from '@/features/feed';
import type { PostWithLikeStatus } from '@/features/post';
import { useRepost } from '@/features/post';
import type { Comment } from '@/features/comment';
import { useComments, useCreateComment, useToggleCommentLike } from '@/features/comment';
import { useToggleLike } from '@/features/like';
import { useFollowStatus, useToggleFollow } from '@/features/follow';
import { useAuthStore } from '@/features/auth';
import { Avatar, Button, Skeleton, Textarea } from '@/shared/components/ui';
import { formatDate } from '@/shared/lib/utils';

interface PostCardProps {
  post: PostFeedItem | PostWithLikeStatus;
  expanded?: boolean;
  focusedCommentId?: number;
}

export function PostCard({ post, expanded = false, focusedCommentId }: PostCardProps) {
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuthStore();
  const toggleLike = useToggleLike();
  const toggleFollow = useToggleFollow();
  const createComment = useCreateComment(post.id);
  const repost = useRepost();

  const [isCommentsExpanded, setIsCommentsExpanded] = useState(expanded);
  const [isContentExpanded, setIsContentExpanded] = useState(expanded);
  const [isContentTruncated, setIsContentTruncated] = useState(false);
  const [newCommentContent, setNewCommentContent] = useState('');
  const [commentShouldRepost, setCommentShouldRepost] = useState(false);
  const [replyingTo, setReplyingTo] = useState<{ id: number; username: string } | null>(null);
  const [isRepostOpen, setIsRepostOpen] = useState(false);
  const [repostContent, setRepostContent] = useState('');
  const contentRef = useRef<HTMLParagraphElement>(null);

  const authorName = 'author_name' in post
    ? post.author_name
    : (post.author?.username || `用户${post.author_id}`);
  const authorAvatar = 'author_avatar' in post
    ? post.author_avatar
    : (post.author?.avatar_url || null);
  const authorBio = 'author_bio' in post ? post.author_bio : (post.author?.bio || null);
  const isLiked = 'is_liked' in post ? post.is_liked : post.is_liked_by_current_user;
  const isAuthorAiAgent = 'author_is_ai_agent' in post
    ? post.author_is_ai_agent
    : Boolean(post.author?.is_ai_agent);
  const isCurrentUser = user?.id === post.author_id;
  const { data: followStatus } = useFollowStatus(post.author_id);

  useEffect(() => {
    if (!contentRef.current) return;
    const lineHeight = parseInt(getComputedStyle(contentRef.current).lineHeight) || 24;
    setIsContentTruncated(contentRef.current.scrollHeight > lineHeight * 3 + 1);
  }, [post.content]);

  const { data: commentsData, isLoading: isCommentsLoading } = useComments(post.id, user?.id);
  const previewComments = expanded
    ? (commentsData?.items || [])
    : (commentsData?.items?.slice(0, 5) || []);
  const hasMoreComments = !expanded && (commentsData?.total || 0) > 5;

  const requireLogin = () => {
    if (isAuthenticated) return true;
    navigate('/login');
    return false;
  };

  const handleSubmitNewComment = (event: React.FormEvent) => {
    event.preventDefault();
    event.stopPropagation();
    if (!newCommentContent.trim() || createComment.isPending) return;

    createComment.mutate(
      { content: newCommentContent.trim(), repost: commentShouldRepost },
      {
        onSuccess: () => {
          setNewCommentContent('');
          setCommentShouldRepost(false);
        },
      },
    );
  };

  const handleSubmitRepost = (event: React.FormEvent) => {
    event.preventDefault();
    event.stopPropagation();
    if (repost.isPending) return;

    repost.mutate(
      {
        source_type: 'post',
        source_id: post.id,
        content: repostContent.trim() || undefined,
      },
      {
        onSuccess: () => {
          setRepostContent('');
          setIsRepostOpen(false);
        },
      },
    );
  };

  return (
    <article className="p-4">
      <div className="mb-3 flex items-center gap-3">
        <Link to={`/user/${post.author_id}`}>
          <Avatar src={authorAvatar} alt={authorName} size="md" className="!h-[42px] !w-[42px]" />
        </Link>
        <div className="min-w-0 flex-1">
          <Link
            to={`/user/${post.author_id}`}
            className="font-medium text-foreground transition-colors hover:text-primary"
          >
            {authorName}
          </Link>
          <div className="mt-0.5 flex items-center gap-2">
            {authorBio ? (
              <p className="max-w-[50%] truncate text-xs text-muted-foreground">{authorBio}</p>
            ) : (
              <span />
            )}
            <span className="text-xs text-muted-foreground">·</span>
            <p className="shrink-0 text-xs text-muted-foreground">{formatDate(post.created_at)}</p>
            {isAuthorAiAgent && (
              <>
                <span className="text-xs text-muted-foreground">·</span>
                <p className="shrink-0 text-xs text-muted-foreground">AI生成</p>
              </>
            )}
          </div>
        </div>
        {!isCurrentUser && !followStatus?.is_following && (
          <Button
            variant="outline"
            size="sm"
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              if (!requireLogin()) return;
              toggleFollow.mutate(post.author_id);
            }}
            disabled={toggleFollow.isPending}
            className="h-7 shrink-0 border-black bg-white px-3 text-xs text-black hover:bg-gray-100"
          >
            {toggleFollow.isPending ? (
              <div className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
            ) : (
              '关注'
            )}
          </Button>
        )}
      </div>

      <div className="min-w-0">
        {post.title && (
          <Link to={`/post/${post.id}`}>
            <h3 className="mb-2 line-clamp-2 text-lg font-semibold">{post.title}</h3>
          </Link>
        )}
        <p
          ref={contentRef}
          className={`whitespace-pre-wrap break-words text-foreground/90 ${
            isContentExpanded ? '' : 'line-clamp-3'
          }`}
        >
          <LinkedMentions
            text={post.content}
            authors={post.repost_chain_authors || []}
          />
        </p>
        {post.repost_origin && <RepostOriginBlock origin={post.repost_origin} />}
        {isContentTruncated && (
          <button
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              setIsContentExpanded(!isContentExpanded);
            }}
            className="mt-2 flex items-center gap-1 text-sm text-primary transition-colors hover:text-primary/80"
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

      <div className="mt-4 flex items-center gap-6">
        <button
          className={`flex items-center gap-1.5 text-sm transition-colors ${
            isLiked ? 'text-red-500' : 'text-muted-foreground hover:text-red-500'
          }`}
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            toggleLike.mutate(post.id);
          }}
          disabled={toggleLike.isPending}
        >
          <Heart className={`h-4 w-4 ${isLiked ? 'fill-current' : ''}`} />
          <span>{post.like_count}</span>
        </button>
        <button
          className={`flex items-center gap-1.5 text-sm transition-colors ${
            isCommentsExpanded ? 'text-primary' : 'text-muted-foreground hover:text-primary'
          }`}
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            setIsCommentsExpanded(!isCommentsExpanded);
          }}
        >
          <MessageCircle className="h-4 w-4" />
          <span>{post.comment_count}</span>
        </button>
        <button
          className={`flex items-center gap-1.5 text-sm transition-colors ${
            isRepostOpen ? 'text-primary' : 'text-muted-foreground hover:text-primary'
          }`}
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            if (!requireLogin()) return;
            setIsRepostOpen(!isRepostOpen);
          }}
        >
          <Repeat2 className="h-4 w-4" />
          <span>{post.repost_count || 0}</span>
        </button>
      </div>

      {isRepostOpen && isAuthenticated && (
        <form onSubmit={handleSubmitRepost} className="mt-3">
          <Textarea
            placeholder="写点什么再转发..."
            value={repostContent}
            onChange={(event) => setRepostContent(event.target.value)}
            className="min-h-[60px] resize-none border-0 bg-muted/30 shadow-none focus-visible:ring-0"
            onClick={(event) => event.stopPropagation()}
          />
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={() => setIsRepostOpen(false)}>
              取消
            </Button>
            <Button type="submit" size="sm" disabled={repost.isPending}>
              转发
            </Button>
          </div>
        </form>
      )}

      {isCommentsExpanded && (
        <div className="mt-4">
          {isAuthenticated && !replyingTo && (
            <form onSubmit={handleSubmitNewComment} className="mb-4">
              <div className="flex gap-2">
                <Avatar src={user?.avatar_url || null} alt={user?.username || '用户'} size="sm" />
                <div className="flex-1 space-y-2">
                  <Textarea
                    placeholder="写下你的评论..."
                    value={newCommentContent}
                    onChange={(event) => setNewCommentContent(event.target.value)}
                    className="min-h-[60px] resize-none border-0 bg-muted/30 shadow-none focus-visible:ring-0"
                    onClick={(event) => event.stopPropagation()}
                  />
                  <div className="flex items-center justify-between">
                    <label className="flex items-center gap-2 text-xs text-muted-foreground">
                      <input
                        type="checkbox"
                        checked={commentShouldRepost}
                        onChange={(event) => setCommentShouldRepost(event.target.checked)}
                        className="h-3.5 w-3.5"
                      />
                      同时转发
                    </label>
                    <Button
                      type="submit"
                      size="sm"
                      disabled={!newCommentContent.trim() || createComment.isPending}
                    >
                      评论
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
                  user={user ? { id: user.id, username: user.username } : null}
                  replyingTo={replyingTo}
                  onReply={(commentId, username) => setReplyingTo({ id: commentId, username })}
                  onCancelReply={() => setReplyingTo(null)}
                  onReplySuccess={() => setReplyingTo(null)}
                  depth={0}
                  parentOwner={null}
                  focusedCommentId={focusedCommentId}
                />
              ))}
              {hasMoreComments && (
                <button
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    navigate(`/post/${post.id}`);
                  }}
                  className="w-full py-2 text-center text-sm text-primary transition-colors hover:text-primary/80"
                >
                  查看所有 {commentsData?.total} 条评论
                </button>
              )}
            </div>
          ) : (
            <p className="py-4 text-center text-sm text-muted-foreground">
              {isAuthenticated ? '暂无评论，快来发表第一条评论吧。' : '暂无评论，登录后发表你的看法。'}
            </p>
          )}
        </div>
      )}
    </article>
  );
}

function RepostOriginBlock({
  origin,
}: {
  origin: NonNullable<(PostFeedItem | PostWithLikeStatus)['repost_origin']>;
}) {
  const authorName = origin.author?.username || `用户${origin.author_id}`;

  return (
    <div className="mt-3 rounded-md border border-border/70 bg-muted/30 p-3 transition-colors hover:bg-muted/50">
      <Link
        to={`/user/${origin.author_id}`}
        className="text-xs font-medium text-foreground/70 hover:text-primary"
        onClick={(event) => event.stopPropagation()}
      >
        @{authorName}
      </Link>
      <Link
        to={`/post/${origin.id}`}
        className="mt-1 block line-clamp-3 whitespace-pre-wrap break-words text-sm text-foreground/75 hover:text-foreground"
        onClick={(event) => event.stopPropagation()}
      >
        {origin.content}
      </Link>
    </div>
  );
}

function LinkedMentions({
  text,
  authors,
}: {
  text: string;
  authors: { user_id: number; username: string }[];
}) {
  if (!authors.length) {
    return <>{text}</>;
  }

  const authorByName = new Map(authors.map((author) => [author.username, author]));
  const parts = text.split(/(@[^:\s/]+)/g);

  return (
    <>
      {parts.map((part, index) => {
        if (!part.startsWith('@')) {
          return <span key={`${part}-${index}`}>{part}</span>;
        }

        const username = part.slice(1);
        const author = authorByName.get(username);
        if (!author) {
          return <span key={`${part}-${index}`}>{part}</span>;
        }

        return (
          <Link
            key={`${part}-${index}`}
            to={`/user/${author.user_id}`}
            className="font-medium text-primary hover:text-primary/80"
            onClick={(event) => event.stopPropagation()}
          >
            {part}
          </Link>
        );
      })}
    </>
  );
}

function CommentSkeleton() {
  return (
    <div className="flex gap-2">
      <Skeleton className="h-8 w-8 flex-shrink-0 rounded-full" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-16 w-full rounded-lg" />
      </div>
    </div>
  );
}

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
  focusedCommentId?: number;
}

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
  focusedCommentId,
}: CommentItemProps) {
  const shouldShowFocusedReply = focusedCommentId ? containsComment(comment, focusedCommentId) : false;
  const [showReplies, setShowReplies] = useState(depth === 0 ? shouldShowFocusedReply : true);
  const toggleCommentLike = useToggleCommentLike(postId, currentUserId);
  const repost = useRepost();
  const itemRef = useRef<HTMLDivElement>(null);
  const isReplying = replyingTo?.id === comment.id;
  const [isRepostOpen, setIsRepostOpen] = useState(false);
  const [repostContent, setRepostContent] = useState('');
  const isTopLevel = depth === 0;
  const isSecondLevel = depth === 1;
  const hasReplies = comment.children && comment.children.length > 0;

  useEffect(() => {
    if (focusedCommentId && shouldShowFocusedReply) {
      setShowReplies(true);
    }
  }, [focusedCommentId, shouldShowFocusedReply]);

  useEffect(() => {
    if (focusedCommentId === comment.id && itemRef.current) {
      itemRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
      itemRef.current.classList.add('ring-1', 'ring-primary/40', 'bg-primary/5');
      window.setTimeout(() => {
        itemRef.current?.classList.remove('ring-1', 'ring-primary/40', 'bg-primary/5');
      }, 2400);
    }
  }, [focusedCommentId, comment.id]);

  return (
    <div className={isTopLevel ? 'space-y-3' : ''}>
      <div
        id={`comment-${comment.id}`}
        ref={itemRef}
        className={`flex gap-2 rounded-md transition-colors ${!isTopLevel ? 'mt-3' : ''}`}
      >
        <Avatar src={comment.owner?.avatar_url} alt={comment.owner?.username || `用户${comment.owner_id}`} size="sm" />
        <div className="min-w-0 flex-1">
          {isTopLevel || isSecondLevel ? (
            <Link
              to={`/user/${comment.owner_id}`}
              className="text-sm font-medium text-foreground/70 hover:text-primary"
            >
              {comment.owner?.username || `用户${comment.owner_id}`}
            </Link>
          ) : (
            <div className="flex items-center gap-1 text-sm">
              <Link to={`/user/${comment.owner_id}`} className="font-medium text-foreground/70 hover:text-primary">
                {comment.owner?.username || `用户${comment.owner_id}`}
              </Link>
              <span className="text-muted-foreground">回复</span>
              <Link to={`/user/${parentOwner?.id || comment.owner_id}`} className="text-muted-foreground hover:text-primary">
                @{parentOwner?.username || comment.owner?.username}
              </Link>
            </div>
          )}
          <p className="mt-0.5 whitespace-pre-wrap break-words text-sm text-foreground/85">{comment.content}</p>

          <div className="ml-1 mt-1 flex items-center gap-4">
            <span className="text-xs text-muted-foreground">{formatDate(comment.created_at)}</span>
            <button
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                toggleCommentLike.mutate({ commentId: comment.id });
              }}
              disabled={toggleCommentLike.isPending}
              className={`flex items-center gap-1 text-xs transition-colors ${
                comment.is_liked ? 'text-red-500' : 'text-muted-foreground hover:text-red-500'
              }`}
            >
              <Heart className={`h-3 w-3 ${comment.is_liked ? 'fill-current' : ''}`} />
              {comment.like_count > 0 && <span>{comment.like_count}</span>}
            </button>
            {isAuthenticated && !isReplying && (
              <button
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  onReply(comment.id, comment.owner?.username || `用户${comment.owner_id}`);
                }}
                className="flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-primary"
              >
                <MessageCircle className="h-3 w-3" />
              </button>
            )}
            {isAuthenticated && (
              <button
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  setIsRepostOpen((value) => !value);
                }}
                className={`flex items-center gap-1 text-xs transition-colors ${
                  isRepostOpen ? 'text-primary' : 'text-muted-foreground hover:text-primary'
                }`}
              >
                <Repeat2 className="h-3 w-3" />
              </button>
            )}
            {comment.owner?.is_ai_agent && <span className="text-xs text-muted-foreground">AI生成</span>}
            {isTopLevel && hasReplies && (
              <button
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  setShowReplies(!showReplies);
                }}
                className="flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-primary"
              >
                <CornerDownRight className="h-3 w-3" />
                {showReplies ? '收起回复' : `查看 ${comment.reply_count} 条回复`}
              </button>
            )}
          </div>

          {isReplying && user && replyingTo && (
            <ReplyInput
              postId={postId}
              parentId={replyingTo.id}
              replyToUsername={replyingTo.username}
              onCancel={onCancelReply}
              onSuccess={onReplySuccess}
            />
          )}

          {isRepostOpen && (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                event.stopPropagation();
                if (repost.isPending) return;

                repost.mutate(
                  {
                    source_type: 'comment',
                    source_id: comment.id,
                    content: repostContent.trim() || undefined,
                  },
                  {
                    onSuccess: () => {
                      setRepostContent('');
                      setIsRepostOpen(false);
                    },
                  },
                );
              }}
              className="mt-3 space-y-2"
            >
              <Textarea
                placeholder="写点什么再转发..."
                value={repostContent}
                onChange={(event) => setRepostContent(event.target.value)}
                className="min-h-[56px] resize-none border-0 bg-muted/30 shadow-none focus-visible:ring-0"
                onClick={(event) => event.stopPropagation()}
              />
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={(event) => {
                    event.stopPropagation();
                    setIsRepostOpen(false);
                  }}
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

      {showReplies && hasReplies && (
        <div className={isTopLevel ? 'pl-8' : 'pl-0'}>
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
              parentOwner={{ id: comment.owner_id, username: comment.owner?.username || `用户${comment.owner_id}` }}
              focusedCommentId={focusedCommentId}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function containsComment(comment: Comment, commentId: number): boolean {
  if (comment.id === commentId) return true;
  return Boolean(comment.children?.some((child) => containsComment(child, commentId)));
}

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
  const [shouldRepost, setShouldRepost] = useState(false);
  const createComment = useCreateComment(postId);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    event.stopPropagation();
    if (!content.trim() || createComment.isPending) return;

    createComment.mutate(
      {
        content: content.trim(),
        parent_id: parentId,
        repost: shouldRepost,
      },
      {
        onSuccess: () => {
          setContent('');
          setShouldRepost(false);
          onSuccess();
        },
      },
    );
  };

  return (
    <form onSubmit={handleSubmit} className="mt-3">
      <div className="flex-1 space-y-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>回复 @{replyToUsername}</span>
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
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
          onChange={(event) => setContent(event.target.value)}
          className="min-h-[60px] resize-none border-0 bg-muted/30 shadow-none focus-visible:ring-0"
          onClick={(event) => event.stopPropagation()}
          autoFocus
        />
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={shouldRepost}
              onChange={(event) => setShouldRepost(event.target.checked)}
              className="h-3.5 w-3.5"
            />
            同时转发
          </label>
          <Button type="submit" size="sm" disabled={!content.trim() || createComment.isPending}>
            评论
          </Button>
        </div>
      </div>
    </form>
  );
}
