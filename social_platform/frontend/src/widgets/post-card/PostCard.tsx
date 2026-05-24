import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ChevronDown as ExpandIcon,
  ChevronUp,
  Clock,
  CornerDownRight,
  Flame,
  Heart,
  MessageCircle,
  MoreHorizontal,
  Repeat2,
  Trash2,
} from 'lucide-react';
import type { PostFeedItem } from '@/features/feed';
import type { PostWithLikeStatus } from '@/features/post';
import { useDeletePost, useRepost } from '@/features/post';
import type { Comment, CommentSort } from '@/features/comment';
import {
  useComments,
  useCreateComment,
  useDeleteComment,
  useToggleCommentLike,
} from '@/features/comment';
import {
  containsComment,
  getInitialVisibleReplyCount,
  getNextVisibleReplyCount,
  getReplyCount,
} from '@/features/comment/replyVisibility';
import { useToggleLike } from '@/features/like';
import { useFollowStatus, useToggleFollow, type FollowStatusResponse } from '@/features/follow';
import { useAuthStore } from '@/features/auth';
import { Avatar, Button, Skeleton, Textarea } from '@/shared/components/ui';
import { formatDate } from '@/shared/lib/utils';
import { MarkdownRenderer } from '@/shared/components/markdown/MarkdownRenderer';
import { stripMarkdown } from '@/shared/components/markdown/markdownUtils';

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
  const deletePost = useDeletePost();

  const [isCommentsExpanded, setIsCommentsExpanded] = useState(expanded);
  const [isContentExpanded, setIsContentExpanded] = useState(expanded);
  const [isContentTruncated, setIsContentTruncated] = useState(false);
  const [newCommentContent, setNewCommentContent] = useState('');
  // 评论排序是每张帖子卡片自己的状态，避免展开多个帖子时互相影响。
  const [commentSort, setCommentSort] = useState<CommentSort>('default');
  const [commentShouldRepost, setCommentShouldRepost] = useState(false);
  const [replyingTo, setReplyingTo] = useState<{ id: number; username: string } | null>(null);
  const [isRepostOpen, setIsRepostOpen] = useState(false);
  const [isMoreOpen, setIsMoreOpen] = useState(false);
  const [repostContent, setRepostContent] = useState('');
  const contentRef = useRef<HTMLParagraphElement>(null);

  const authorName =
    'author_name' in post ? post.author_name : post.author?.username || `用户${post.author_id}`;
  const authorAvatar =
    'author_avatar' in post ? post.author_avatar : post.author?.avatar_url || null;
  const authorBio = 'author_bio' in post ? post.author_bio : post.author?.bio || null;
  const isLiked = 'is_liked' in post ? post.is_liked : post.is_liked_by_current_user;
  const isAuthorAiAgent =
    'author_is_ai_agent' in post ? post.author_is_ai_agent : Boolean(post.author?.is_ai_agent);
  const isCurrentUser = user?.id === post.author_id;
  const isArticle = post.type === 'article';
  const hasAuthorFollowStatus =
    'author_is_following' in post || 'author_is_followed_by' in post || 'author_is_mutual' in post;
  const initialFollowStatus: FollowStatusResponse | undefined = hasAuthorFollowStatus
    ? {
        user_id: post.author_id,
        is_following: Boolean('author_is_following' in post && post.author_is_following),
        is_followed_by: Boolean('author_is_followed_by' in post && post.author_is_followed_by),
        is_mutual: Boolean('author_is_mutual' in post && post.author_is_mutual),
      }
    : undefined;
  const { data: followStatus } = useFollowStatus(post.author_id, {
    enabled: !hasAuthorFollowStatus && !isCurrentUser,
    initialData: initialFollowStatus,
  });

  useEffect(() => {
    if (isArticle) return;
    if (!contentRef.current) return;
    const lineHeight = parseInt(getComputedStyle(contentRef.current).lineHeight) || 24;
    setIsContentTruncated(contentRef.current.scrollHeight > lineHeight * 3 + 1);
  }, [isArticle, post.content]);

  const { data: commentsData, isLoading: isCommentsLoading } = useComments(
    post.id,
    user?.id,
    commentSort,
    { enabled: isCommentsExpanded }
  );
  const topLevelComments = commentsData?.items || [];
  const previewComments = expanded ? topLevelComments : topLevelComments.slice(0, 5);
  const hasMoreComments = !expanded && topLevelComments.length > 5;

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
      }
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
      }
    );
  };

  const handleDeletePost = (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    if (!isCurrentUser || deletePost.isPending) return;

    deletePost.mutate(post.id, {
      onSuccess: () => {
        setIsMoreOpen(false);
        if (expanded) {
          navigate('/');
        }
      },
    });
  };

  return (
    <article className="p-3 sm:p-4">
      <div className="mb-3 flex items-center gap-2 sm:gap-3">
        <Link to={`/user/${post.author_id}`}>
          <Avatar
            src={authorAvatar}
            alt={authorName}
            size="md"
            className="post-card-avatar !h-[42px] !w-[42px]"
          />
        </Link>
        <div className="min-w-0 flex-1">
          <Link
            to={`/user/${post.author_id}`}
            className="font-medium text-foreground transition-colors hover:text-primary"
          >
            {authorName}
          </Link>
          <div className="post-meta-row mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5">
            {authorBio ? (
              <p className="max-w-[9rem] truncate text-xs text-muted-foreground sm:max-w-[50%]">
                {authorBio}
              </p>
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
            onClick={event => {
              event.preventDefault();
              event.stopPropagation();
              if (!requireLogin()) return;
              toggleFollow.mutate(post.author_id);
            }}
            disabled={toggleFollow.isPending}
            className="h-7 shrink-0 border-[var(--theme-accent-bg)] bg-white px-3 text-xs text-[var(--theme-accent-bg)] hover:bg-[var(--theme-subtle-bg)]"
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
        {isArticle ? (
          expanded ? (
            <div className="space-y-4">
              <h1 className="text-xl font-semibold leading-8 text-foreground sm:text-2xl sm:leading-9">
                {post.title}
              </h1>
              <MarkdownRenderer content={post.content} />
            </div>
          ) : (
            <Link
              to={`/post/${post.id}`}
              className="block rounded-md transition-colors hover:bg-muted/20"
            >
              <h3 className="mb-2 line-clamp-2 text-xl font-semibold leading-7 text-foreground sm:text-2xl sm:leading-8">
                {post.title || 'Untitled'}
              </h3>
              <p className="line-clamp-3 text-sm leading-6 text-muted-foreground">
                {stripMarkdown(post.content)}
              </p>
            </Link>
          )
        ) : (
          <>
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
              <LinkedMentions text={post.content} authors={post.repost_chain_authors || []} />
            </p>
          </>
        )}
        {post.repost_origin && <RepostOriginBlock origin={post.repost_origin} />}
        {!post.repost_origin && post.repost_origin_missing && <MissingRepostOriginBlock />}
        {!isArticle && isContentTruncated && (
          <button
            onClick={event => {
              event.preventDefault();
              event.stopPropagation();
              setIsContentExpanded(!isContentExpanded);
            }}
            className="mt-2 flex items-center gap-1 text-sm text-[var(--theme-accent-bg)] transition-colors hover:opacity-80"
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

      <div className="post-action-row mt-4 flex items-center gap-4 sm:gap-6">
        <button
          className={`flex items-center gap-1.5 text-sm transition-colors ${
            isLiked ? 'text-red-500' : 'text-muted-foreground hover:text-red-500'
          }`}
          onClick={event => {
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
          onClick={event => {
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
          onClick={event => {
            event.preventDefault();
            event.stopPropagation();
            if (!requireLogin()) return;
            setIsRepostOpen(!isRepostOpen);
          }}
        >
          <Repeat2 className="h-4 w-4" />
          <span>{post.repost_count || 0}</span>
        </button>
        <div className="relative ml-auto">
          <button
            className={`flex h-7 w-7 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground ${
              isMoreOpen ? 'bg-muted text-foreground' : ''
            }`}
            onClick={event => {
              event.preventDefault();
              event.stopPropagation();
              setIsMoreOpen(value => !value);
            }}
            aria-label="更多操作"
          >
            <MoreHorizontal className="h-4 w-4" />
          </button>
          {isMoreOpen && (
            <div
              className="absolute bottom-8 right-0 z-20 min-w-28 rounded-md border border-border bg-background p-1 shadow-md"
              onClick={event => event.stopPropagation()}
            >
              {isCurrentUser && (
                <button
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-destructive hover:bg-destructive/10"
                  onClick={handleDeletePost}
                  disabled={deletePost.isPending}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  删除
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {isRepostOpen && isAuthenticated && (
        <form onSubmit={handleSubmitRepost} className="mt-3">
          <Textarea
            placeholder="写点什么再转发..."
            value={repostContent}
            onChange={event => setRepostContent(event.target.value)}
            className="min-h-[60px] resize-none border-0 bg-muted/30 shadow-none focus-visible:ring-0"
            onClick={event => event.stopPropagation()}
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
          <div className="mb-3 flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-foreground/80">评论</span>
            <div className="flex items-center gap-1 rounded-md bg-muted/50 p-1">
              <button
                type="button"
                onClick={event => {
                  event.preventDefault();
                  event.stopPropagation();
                  setCommentSort('default');
                }}
                className={`flex items-center gap-1 rounded px-1.5 py-1 text-xs transition-colors sm:px-2 ${
                  commentSort === 'default'
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Flame className="h-3 w-3" />
                默认
              </button>
              <button
                type="button"
                onClick={event => {
                  event.preventDefault();
                  event.stopPropagation();
                  setCommentSort('latest');
                }}
                className={`flex items-center gap-1 rounded px-1.5 py-1 text-xs transition-colors sm:px-2 ${
                  commentSort === 'latest'
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Clock className="h-3 w-3" />
                最新
              </button>
            </div>
          </div>

          {isAuthenticated && !replyingTo && (
            <form onSubmit={handleSubmitNewComment} className="mb-4">
              <div className="flex gap-2">
                <Avatar src={user?.avatar_url || null} alt={user?.username || '用户'} size="sm" />
                <div className="flex-1 space-y-2">
                  <Textarea
                    placeholder="写下你的评论..."
                    value={newCommentContent}
                    onChange={event => setNewCommentContent(event.target.value)}
                    className="min-h-[60px] resize-none border-0 bg-muted/30 shadow-none focus-visible:ring-0"
                    onClick={event => event.stopPropagation()}
                  />
                  <div className="flex items-center justify-between">
                    <label className="flex items-center gap-2 text-xs text-muted-foreground">
                      <input
                        type="checkbox"
                        checked={commentShouldRepost}
                        onChange={event => setCommentShouldRepost(event.target.checked)}
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
              {previewComments.map(comment => (
                <CommentItem
                  key={comment.id}
                  comment={comment}
                  postId={post.id}
                  isAuthenticated={isAuthenticated}
                  currentUserId={user?.id}
                  commentSort={commentSort}
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
                  onClick={event => {
                    event.preventDefault();
                    event.stopPropagation();
                    navigate(`/post/${post.id}`);
                  }}
                  className="w-full py-2 text-center text-sm text-primary transition-colors hover:text-primary/80"
                >
                  查看所有评论
                </button>
              )}
            </div>
          ) : (
            <p className="py-4 text-center text-sm text-muted-foreground">
              {isAuthenticated
                ? '暂无评论，快来发表第一条评论吧。'
                : '暂无评论，登录后发表你的看法。'}
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
  const isArticle = origin.type === 'article';

  return (
    <div className="mt-3 rounded-md border border-border/70 bg-muted/30 p-3 transition-colors hover:bg-muted/50">
      <Link
        to={`/user/${origin.author_id}`}
        className="text-xs font-medium text-foreground/70 hover:text-primary"
        onClick={event => event.stopPropagation()}
      >
        @{authorName}
      </Link>
      <Link
        to={`/post/${origin.id}`}
        className="mt-1 block break-words text-sm text-foreground/75 hover:text-foreground"
        onClick={event => event.stopPropagation()}
      >
        {isArticle ? (
          <>
            <span className="mb-1 block line-clamp-2 text-base font-semibold text-foreground/85">
              {origin.title || 'Untitled'}
            </span>
            <span className="line-clamp-2 text-xs text-muted-foreground">
              {stripMarkdown(origin.content)}
            </span>
          </>
        ) : (
          <span className="line-clamp-3 whitespace-pre-wrap">{origin.content}</span>
        )}
      </Link>
    </div>
  );
}

function MissingRepostOriginBlock() {
  return (
    <div className="mt-3 rounded-md border border-dashed border-border/80 bg-muted/20 p-3 text-sm text-muted-foreground">
      原内容不存在
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

  const authorByName = new Map(authors.map(author => [author.username, author]));
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
            onClick={event => event.stopPropagation()}
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
  commentSort: CommentSort;
  user: { id: number; username: string } | null;
  replyingTo: { id: number; username: string } | null;
  onReply: (commentId: number, username: string) => void;
  onCancelReply: () => void;
  onReplySuccess: () => void;
  depth: number;
  parentOwner: { id: number; username: string } | null;
  focusedCommentId?: number;
  renderReplies?: boolean;
  visibleReplyLimit?: number;
}

function CommentItem({
  comment,
  postId,
  isAuthenticated,
  currentUserId,
  commentSort,
  user,
  replyingTo,
  onReply,
  onCancelReply,
  onReplySuccess,
  depth,
  parentOwner,
  focusedCommentId,
  renderReplies = true,
  visibleReplyLimit,
}: CommentItemProps) {
  const shouldShowFocusedReply = focusedCommentId
    ? containsComment(comment, focusedCommentId)
    : false;
  const totalReplies = renderReplies ? getReplyCount(comment) : 0;
  const initialVisibleReplyCount = renderReplies
    ? getInitialVisibleReplyCount(comment, focusedCommentId)
    : 0;
  const [showReplies, setShowReplies] = useState(depth === 0 ? shouldShowFocusedReply : true);
  const [visibleReplyCount, setVisibleReplyCount] = useState(initialVisibleReplyCount);
  const toggleCommentLike = useToggleCommentLike(postId, currentUserId, commentSort);
  const deleteComment = useDeleteComment(postId);
  const repost = useRepost();
  const itemRef = useRef<HTMLDivElement>(null);
  const isReplying = replyingTo?.id === comment.id;
  const [isRepostOpen, setIsRepostOpen] = useState(false);
  const [isMoreOpen, setIsMoreOpen] = useState(false);
  const [repostContent, setRepostContent] = useState('');
  const isTopLevel = depth === 0;
  const isSecondLevel = depth === 1;
  const isCurrentUserComment = currentUserId === comment.owner_id;
  const hasReplies = totalReplies > 0;
  const displayedReplyCount = visibleReplyLimit ?? visibleReplyCount;
  const hasMoreRepliesToShow = visibleReplyLimit === undefined && visibleReplyCount < totalReplies;

  const handleDeleteComment = (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    if (!isCurrentUserComment || deleteComment.isPending) return;

    deleteComment.mutate(comment.id, {
      onSuccess: () => setIsMoreOpen(false),
    });
  };

  useEffect(() => {
    if (focusedCommentId && shouldShowFocusedReply) {
      setShowReplies(true);
      setVisibleReplyCount(count => Math.max(count, initialVisibleReplyCount));
    }
  }, [focusedCommentId, initialVisibleReplyCount, shouldShowFocusedReply]);

  useEffect(() => {
    if (visibleReplyLimit !== undefined) return;

    if (visibleReplyCount > totalReplies) {
      setVisibleReplyCount(totalReplies);
    } else if (visibleReplyCount === 0 && totalReplies > 0) {
      setVisibleReplyCount(getNextVisibleReplyCount(0, totalReplies));
    }
  }, [totalReplies, visibleReplyCount, visibleReplyLimit]);

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
        <Avatar
          src={comment.owner?.avatar_url}
          alt={comment.owner?.username || `用户${comment.owner_id}`}
          size="sm"
        />
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
              <Link
                to={`/user/${comment.owner_id}`}
                className="font-medium text-foreground/70 hover:text-primary"
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
          <p className="mt-0.5 whitespace-pre-wrap break-words text-sm text-foreground/85">
            {comment.content}
          </p>

          <div className="comment-action-row ml-1 mt-1 flex items-center gap-4">
            <span className="comment-action-label text-xs text-muted-foreground">
              {formatDate(comment.created_at)}
            </span>
            <button
              onClick={event => {
                event.preventDefault();
                event.stopPropagation();
                toggleCommentLike.mutate({ commentId: comment.id });
              }}
              disabled={toggleCommentLike.isPending}
              className={`comment-icon-action flex items-center gap-1 text-xs transition-colors ${
                comment.is_liked ? 'text-red-500' : 'text-muted-foreground hover:text-red-500'
              }`}
            >
              <Heart className={`h-3 w-3 ${comment.is_liked ? 'fill-current' : ''}`} />
              {comment.like_count > 0 && <span>{comment.like_count}</span>}
            </button>
            {isAuthenticated && !isReplying && (
              <button
                onClick={event => {
                  event.preventDefault();
                  event.stopPropagation();
                  onReply(comment.id, comment.owner?.username || `用户${comment.owner_id}`);
                }}
                className="comment-icon-action flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-primary"
              >
                <MessageCircle className="h-3 w-3" />
              </button>
            )}
            {isAuthenticated && (
              <button
                onClick={event => {
                  event.preventDefault();
                  event.stopPropagation();
                  setIsRepostOpen(value => !value);
                }}
                className={`comment-icon-action flex items-center gap-1 text-xs transition-colors ${
                  isRepostOpen ? 'text-primary' : 'text-muted-foreground hover:text-primary'
                }`}
              >
                <Repeat2 className="h-3 w-3" />
              </button>
            )}
            {comment.owner?.is_ai_agent && (
              <span className="comment-ai-label text-xs text-muted-foreground">AI生成</span>
            )}
            <div className="comment-more-menu relative order-2 ml-auto">
              <button
                className={`flex h-6 w-6 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground ${
                  isMoreOpen ? 'bg-muted text-foreground' : ''
                }`}
                onClick={event => {
                  event.preventDefault();
                  event.stopPropagation();
                  setIsMoreOpen(value => !value);
                }}
                aria-label="更多操作"
              >
                <MoreHorizontal className="h-3.5 w-3.5" />
              </button>
              {isMoreOpen && (
                <div
                  className="absolute bottom-7 right-0 z-20 min-w-28 rounded-md border border-border bg-background p-1 shadow-md"
                  onClick={event => event.stopPropagation()}
                >
                  {isCurrentUserComment && (
                    <button
                      className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-destructive hover:bg-destructive/10"
                      onClick={handleDeleteComment}
                      disabled={deleteComment.isPending}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      删除
                    </button>
                  )}
                </div>
              )}
            </div>
            {isTopLevel && hasReplies && (
              <button
                onClick={event => {
                  event.preventDefault();
                  event.stopPropagation();
                  setShowReplies(!showReplies);
                }}
                className="comment-reply-toggle order-1 flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-primary"
              >
                <CornerDownRight className="h-3 w-3" />
                <span className="reply-toggle-full">
                  {showReplies ? '收起回复' : `查看 ${totalReplies} 条回复`}
                </span>
                <span className="reply-toggle-short">
                  {showReplies ? '收起' : `${totalReplies}回复`}
                </span>
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
              onSubmit={event => {
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
                  }
                );
              }}
              className="mt-3 space-y-2"
            >
              <Textarea
                placeholder="写点什么再转发..."
                value={repostContent}
                onChange={event => setRepostContent(event.target.value)}
                className="min-h-[56px] resize-none border-0 bg-muted/30 shadow-none focus-visible:ring-0"
                onClick={event => event.stopPropagation()}
              />
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={event => {
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
                  isAuthenticated={isAuthenticated}
                  currentUserId={currentUserId}
                  commentSort={commentSort}
                  user={user}
                  replyingTo={replyingTo}
                  onReply={onReply}
                  onCancelReply={onCancelReply}
                  onReplySuccess={onReplySuccess}
                  depth={depth + 1}
                  parentOwner={{
                    id: comment.owner_id,
                    username: comment.owner?.username || `用户${comment.owner_id}`,
                  }}
                  focusedCommentId={focusedCommentId}
                  visibleReplyLimit={childVisibleReplyLimit}
                />
              );
            });
          })()}
          {hasMoreRepliesToShow && (
            <button
              type="button"
              onClick={event => {
                event.preventDefault();
                event.stopPropagation();
                setVisibleReplyCount(count => getNextVisibleReplyCount(count, totalReplies));
              }}
              className="mt-3 text-xs text-primary transition-colors hover:text-primary/80"
            >
              展开更多回复 ({visibleReplyCount}/{totalReplies})
            </button>
          )}
        </div>
      )}
    </div>
  );
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
      }
    );
  };

  return (
    <form onSubmit={handleSubmit} className="mt-3">
      <div className="flex-1 space-y-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>回复 @{replyToUsername}</span>
          <button
            type="button"
            onClick={event => {
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
          onChange={event => setContent(event.target.value)}
          className="min-h-[60px] resize-none border-0 bg-muted/30 shadow-none focus-visible:ring-0"
          onClick={event => event.stopPropagation()}
          autoFocus
        />
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={shouldRepost}
              onChange={event => setShouldRepost(event.target.checked)}
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
