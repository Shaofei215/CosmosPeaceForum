import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type MouseEvent,
} from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ChevronDown as ExpandIcon,
  ChevronUp,
  Clock,
  CornerDownRight,
  Flag,
  Flame,
  MessageCircle,
  MoreHorizontal,
  Repeat2,
  ThumbsUp,
  Trash2,
} from 'lucide-react';
import type { PostFeedItem } from '@/features/feed';
import type { Poll, PostWithLikeStatus } from '@/features/post';
import { useDeletePost, useRepost, useVotePoll } from '@/features/post';
import { useCreateReport } from '@/features/report';
import type { Comment, CommentSort } from '@/features/comment';
import {
  useComment,
  useComments,
  useCommentReplies,
  useCreateComment,
  useDeleteComment,
  useToggleCommentLike,
} from '@/features/comment';
import { useToggleLike } from '@/features/like';
import { useFollowStatus, useToggleFollow, type FollowStatusResponse } from '@/features/follow';
import { COMMENT_CONTENT_MAX_LENGTH, POST_CONTENT_MAX_LENGTH } from '@/shared/config/contentLimits';
import { useAuthStore } from '@/features/auth';
import { Avatar, Button, Skeleton, Textarea } from '@/shared/components/ui';
import { formatDate } from '@/shared/lib/utils';
import { MarkdownRenderer } from '@/shared/components/markdown/MarkdownRenderer';
import { LinkedMentions as MentionText } from '@/shared/components/mention/LinkedMentions';
import { stripMarkdown } from '@/shared/components/markdown/markdownUtils';
import { hasVisibleContent } from '@/shared/lib/content';
import { copywriting } from '@/shared/config/copywriting';

const CONTENT_PREVIEW_LINES = 10;

interface ContentPreviewMeasurement {
  height: number;
  lineCount: number;
}

/**
 * 测量正文真实文本行，并返回指定行数末行底边对应的预览高度。
 *
 * 相比用固定行高相乘，此方法会纳入 Markdown 标题、列表和段间距，确保裁切点
 * 落在第十行文字的底边，而不是落在某一行中间或段间空白中。
 *
 * @param element 正文内容根元素。
 * @param maximumLines 折叠状态最多展示的文本行数。
 * @returns 正文总行数及折叠预览应使用的像素高度。
 */
function measureContentPreview(
  element: HTMLElement,
  maximumLines: number
): ContentPreviewMeasurement {
  const elementTop = element.getBoundingClientRect().top;
  const textRectangles: DOMRect[] = [];
  const treeWalker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
  let textNode = treeWalker.nextNode();

  while (textNode) {
    if (textNode.textContent?.length) {
      const range = document.createRange();
      range.selectNodeContents(textNode);
      textRectangles.push(...Array.from(range.getClientRects()).filter(rect => rect.height > 0));
      range.detach();
    }
    textNode = treeWalker.nextNode();
  }

  textRectangles.sort((left, right) => left.top - right.top || left.left - right.left);
  const lines: Array<{ top: number; bottom: number }> = [];

  for (const rectangle of textRectangles) {
    const currentLine = lines[lines.length - 1];
    if (currentLine && Math.abs(currentLine.top - rectangle.top) <= 2) {
      currentLine.bottom = Math.max(currentLine.bottom, rectangle.bottom);
      continue;
    }
    lines.push({ top: rectangle.top, bottom: rectangle.bottom });
  }

  if (lines.length <= maximumLines) {
    return { height: element.scrollHeight, lineCount: lines.length };
  }

  const lastVisibleLine = lines[maximumLines - 1];
  return {
    height: Math.min(element.scrollHeight, Math.ceil(lastVisibleLine.bottom - elementTop)),
    lineCount: lines.length,
  };
}

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
  const createReport = useCreateReport();

  const [isCommentsExpanded, setIsCommentsExpanded] = useState(expanded);
  const [isContentExpanded, setIsContentExpanded] = useState(expanded);
  const [isContentTruncated, setIsContentTruncated] = useState(false);
  const [expandedContentHeight, setExpandedContentHeight] = useState<number>();
  const [previewContentHeight, setPreviewContentHeight] = useState<number>();
  const [newCommentContent, setNewCommentContent] = useState('');
  // 评论排序是每张帖子卡片自己的状态，避免展开多个帖子时互相影响。
  const [commentSort, setCommentSort] = useState<CommentSort>('default');
  const [commentShouldRepost, setCommentShouldRepost] = useState(false);
  const [replyingTo, setReplyingTo] = useState<{ id: number; username: string } | null>(null);
  const [isRepostOpen, setIsRepostOpen] = useState(false);
  const [isMoreOpen, setIsMoreOpen] = useState(false);
  const [isReportOpen, setIsReportOpen] = useState(false);
  const [reportError, setReportError] = useState('');
  const [repostContent, setRepostContent] = useState('');
  const articleContentRef = useRef<HTMLDivElement>(null);
  const postContentRef = useRef<HTMLParagraphElement>(null);
  const contentToggleRef = useRef<HTMLButtonElement>(null);
  const collapseViewportCleanupRef = useRef<(() => void) | null>(null);

  const authorName =
    'author_name' in post
      ? post.author_name
      : post.author?.username ||
        copywriting('post.fallback_user', '用户{user_id}', { user_id: post.author_id });
  const authorAvatar =
    'author_avatar' in post ? post.author_avatar : post.author?.avatar_url || null;
  const authorBio = 'author_bio' in post ? post.author_bio : post.author?.bio || null;
  const isLiked = 'is_liked' in post ? post.is_liked : post.is_liked_by_current_user;
  const isCurrentUser = user?.id === post.author_id;
  const isArticle = post.type === 'article';
  const mentionUsers = post.mention_users || post.repost_chain_authors || [];
  const topicMentions = post.topic_mentions || [];
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

  /**
   * 处理文章预览区域点击：点击链接时保留链接自身行为，其它区域进入详情页。
   *
   * @param event 文章预览容器点击事件。
   */
  const handleArticlePreviewClick = (event: MouseEvent<HTMLDivElement>): void => {
    if (event.target instanceof Element && event.target.closest('a')) {
      return;
    }

    navigate(`/post/${post.id}`);
  };

  /**
   * 让文章预览容器具备键盘进入详情页的能力。
   *
   * @param event 文章预览容器键盘事件。
   */
  const handleArticlePreviewKeyDown = (event: KeyboardEvent<HTMLDivElement>): void => {
    if (event.key !== 'Enter' && event.key !== ' ') {
      return;
    }

    event.preventDefault();
    navigate(`/post/${post.id}`);
  };
  const { data: followStatus } = useFollowStatus(post.author_id, {
    enabled: !hasAuthorFollowStatus && !isCurrentUser,
    initialData: initialFollowStatus,
  });

  useLayoutEffect(() => {
    const contentElement = isArticle ? articleContentRef.current : postContentRef.current;
    if (!contentElement || expanded) return;

    const updateTruncation = (): void => {
      const naturalHeight = contentElement.scrollHeight;
      const previewMeasurement = measureContentPreview(contentElement, CONTENT_PREVIEW_LINES);
      setExpandedContentHeight(naturalHeight);
      setPreviewContentHeight(previewMeasurement.height);
      setIsContentTruncated(previewMeasurement.lineCount > CONTENT_PREVIEW_LINES);
    };

    updateTruncation();
    const resizeObserver = new ResizeObserver(updateTruncation);
    resizeObserver.observe(contentElement);
    return () => resizeObserver.disconnect();
  }, [expanded, isArticle, post.content, post.title]);

  useEffect(
    () => () => {
      collapseViewportCleanupRef.current?.();
    },
    []
  );

  /**
   * 切换长内容的展开状态，并在收起期间锚定操作按钮的视口位置。
   *
   * 内容高度缩小时，按按钮相对视口的位移同步上滑页面，避免读者停留在后续帖子中。
   * 浏览器若已完成原生滚动锚定，按钮位置不变，因此不会产生重复补偿。
   *
   * @param event 展开或收起按钮的点击事件。
   */
  const handleContentExpansionToggle = (event: MouseEvent<HTMLButtonElement>): void => {
    event.preventDefault();
    event.stopPropagation();

    collapseViewportCleanupRef.current?.();

    if (!isContentExpanded) {
      setIsContentExpanded(true);
      return;
    }

    const contentElement = isArticle ? articleContentRef.current : postContentRef.current;
    const toggleElement = contentToggleRef.current;
    if (!contentElement || !toggleElement) {
      setIsContentExpanded(false);
      return;
    }

    const anchorTop = toggleElement.getBoundingClientRect().top;

    const resizeObserver = new ResizeObserver(() => {
      const viewportOffset = toggleElement.getBoundingClientRect().top - anchorTop;
      if (Math.abs(viewportOffset) < 0.5) return;

      window.scrollBy({ top: viewportOffset, left: 0, behavior: 'auto' });
    });

    const stopViewportTracking = (): void => {
      resizeObserver.disconnect();
      contentElement.removeEventListener('transitionend', handleTransitionEnd);
      window.clearTimeout(timeoutId);
      if (collapseViewportCleanupRef.current === stopViewportTracking) {
        collapseViewportCleanupRef.current = null;
      }
    };

    const handleTransitionEnd = (transitionEvent: TransitionEvent): void => {
      if (
        transitionEvent.target !== contentElement ||
        transitionEvent.propertyName !== 'max-height'
      ) {
        return;
      }
      stopViewportTracking();
    };

    resizeObserver.observe(contentElement);
    contentElement.addEventListener('transitionend', handleTransitionEnd);
    const timeoutId = window.setTimeout(stopViewportTracking, 350);
    collapseViewportCleanupRef.current = stopViewportTracking;
    setIsContentExpanded(false);
  };

  const { data: commentsData, isLoading: isCommentsLoading } = useComments(
    post.id,
    user?.id,
    commentSort,
    { enabled: isCommentsExpanded }
  );
  const { data: focusedComment } = useComment(post.id, focusedCommentId, user?.id, {
    enabled: isCommentsExpanded && !!focusedCommentId,
  });
  const topLevelComments = commentsData?.items || [];
  const previewComments = expanded ? topLevelComments : topLevelComments.slice(0, 5);
  const hasMoreComments = !expanded && topLevelComments.length > 5;
  const focusedThreadRootId = focusedComment?.root_comment_id ?? focusedComment?.id;

  const requireLogin = () => {
    if (isAuthenticated) return true;
    navigate('/login');
    return false;
  };

  const handleSubmitNewComment = (event: React.FormEvent) => {
    event.preventDefault();
    event.stopPropagation();
    if (!hasVisibleContent(newCommentContent) || createComment.isPending) return;

    createComment.mutate(
      { content: newCommentContent, repost: commentShouldRepost },
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
        content: hasVisibleContent(repostContent) ? repostContent : undefined,
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

  const handleOpenPostReport = (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    if (!requireLogin()) return;
    setReportError('');
    setIsReportOpen(true);
  };

  const handleSubmitPostReport = (reason: string) => {
    setReportError('');
    createReport.mutate(
      { target_type: 'post', target_id: post.id, reason },
      {
        onSuccess: () => {
          setIsReportOpen(false);
          setIsMoreOpen(false);
        },
        onError: error => {
          const message =
            error instanceof Error
              ? error.message
              : copywriting('report.submit_failed', '举报提交失败，请稍后重试');
          setReportError(message);
        },
      }
    );
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
            {post.created_by_agent && (
              <>
                <span className="text-xs text-muted-foreground">·</span>
                <p className="shrink-0 text-xs text-muted-foreground">
                  {copywriting('common.ai_generated', 'AI生成')}
                </p>
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
            className="h-7 shrink-0 border-zinc-950 bg-white px-3 text-xs text-zinc-950 hover:bg-zinc-100/80"
          >
            {toggleFollow.isPending ? (
              <div className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
            ) : (
              copywriting('common.follow', '关注')
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
              <MarkdownRenderer
                content={post.content}
                mentionUsers={mentionUsers}
                topicMentions={topicMentions}
              />
            </div>
          ) : (
            <div
              role="link"
              tabIndex={0}
              onClick={handleArticlePreviewClick}
              onKeyDown={handleArticlePreviewKeyDown}
              className="block cursor-pointer rounded-md transition-colors hover:bg-muted/20 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <div className="space-y-4">
                <h1 className="text-xl font-semibold leading-8 text-foreground sm:text-2xl sm:leading-9">
                  {post.title}
                </h1>
                <div className="relative">
                  <div
                    ref={articleContentRef}
                    className={`content-expansion-transition ${
                      isContentExpanded ? '' : 'article-content-preview'
                    } ${!isContentExpanded && isContentTruncated ? 'content-preview-faded' : ''}`}
                    style={
                      {
                        '--content-preview-lines': CONTENT_PREVIEW_LINES,
                        maxHeight:
                          isContentExpanded && expandedContentHeight
                            ? `${expandedContentHeight}px`
                            : previewContentHeight
                              ? `${previewContentHeight}px`
                              : undefined,
                      } as React.CSSProperties
                    }
                  >
                    <MarkdownRenderer
                      content={post.content}
                      mentionUsers={mentionUsers}
                      topicMentions={topicMentions}
                    />
                  </div>
                </div>
              </div>
            </div>
          )
        ) : (
          <>
            {post.title && (
              <Link to={`/post/${post.id}`}>
                <h3 className="mb-2 line-clamp-2 text-lg font-semibold">{post.title}</h3>
              </Link>
            )}
            <div className="relative">
              <p
                ref={postContentRef}
                className={`content-expansion-transition whitespace-pre-wrap break-words text-foreground/90 ${
                  isContentExpanded ? '' : 'post-content-preview'
                } ${!isContentExpanded && isContentTruncated ? 'content-preview-faded' : ''}`}
                style={
                  {
                    '--content-preview-lines': CONTENT_PREVIEW_LINES,
                    maxHeight:
                      isContentExpanded && expandedContentHeight
                        ? `${expandedContentHeight}px`
                        : previewContentHeight
                          ? `${previewContentHeight}px`
                          : undefined,
                  } as React.CSSProperties
                }
              >
                <MentionText
                  text={post.content}
                  users={mentionUsers}
                  topics={topicMentions}
                  onMentionClick={event => event.stopPropagation()}
                  onTopicClick={event => event.stopPropagation()}
                />
              </p>
            </div>
          </>
        )}
        {post.poll && <PollBlock postId={post.id} poll={post.poll} requireLogin={requireLogin} />}
        {post.repost_origin && <RepostOriginBlock origin={post.repost_origin} />}
        {!post.repost_origin && post.repost_origin_missing && <MissingRepostOriginBlock />}
        {!expanded && isContentTruncated && (
          <button
            ref={contentToggleRef}
            onClick={handleContentExpansionToggle}
            className="mt-2 flex items-center gap-1 text-sm text-zinc-950 transition-colors hover:opacity-80"
          >
            {isContentExpanded ? (
              <>
                <ChevronUp className="h-3 w-3" />
                {copywriting('post.collapse', '收起')}
              </>
            ) : (
              <>
                <ExpandIcon className="h-3 w-3" />
                {copywriting('post.expand', '展开')}
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
          <ThumbsUp className={`h-4 w-4 ${isLiked ? 'fill-current' : ''}`} />
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
            aria-label={copywriting('common.more_actions', '更多操作')}
          >
            <MoreHorizontal className="h-4 w-4" />
          </button>
          {isMoreOpen && (
            <div
              className="auth-menu-enter menu-origin-bottom-right absolute bottom-8 right-0 z-20 min-w-28 rounded-md border border-border bg-background p-1 shadow-md"
              onClick={event => event.stopPropagation()}
            >
              {isCurrentUser && (
                <button
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-destructive hover:bg-destructive/10"
                  onClick={handleDeletePost}
                  disabled={deletePost.isPending}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  {copywriting('common.delete', '删除')}
                </button>
              )}
              {!isCurrentUser && (
                <button
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
                  onClick={handleOpenPostReport}
                >
                  <Flag className="h-3.5 w-3.5" />
                  {copywriting('common.report', '举报')}
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {isRepostOpen && isAuthenticated && (
        <form onSubmit={handleSubmitRepost} className="mt-3">
          <Textarea
            placeholder={copywriting('post.repost_placeholder', '写点什么再转发...')}
            value={repostContent}
            onChange={event => setRepostContent(event.target.value)}
            maxLength={POST_CONTENT_MAX_LENGTH}
            className="min-h-[60px] resize-none border-0 bg-muted/30 shadow-none focus-visible:ring-0"
            onClick={event => event.stopPropagation()}
          />
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={() => setIsRepostOpen(false)}>
              {copywriting('common.cancel', '取消')}
            </Button>
            <Button type="submit" size="sm" disabled={repost.isPending}>
              {copywriting('common.repost', '转发')}
            </Button>
          </div>
        </form>
      )}

      {isReportOpen && (
        <ReportDialog
          targetLabel={
            post.type === 'article'
              ? copywriting('post.article', '文章')
              : copywriting('search.posts', '帖子')
          }
          saving={createReport.isPending}
          error={reportError}
          onClose={() => setIsReportOpen(false)}
          onConfirm={handleSubmitPostReport}
        />
      )}

      {isCommentsExpanded && (
        <div className="mt-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-foreground/80">
              {copywriting('post.comments', '评论')}
            </span>
            <div
              className="comment-sort-segmented relative grid grid-cols-2 rounded-md bg-muted/50 p-1"
              data-active={commentSort}
            >
              <span className="auth-sort-slider absolute left-1 top-1 h-[calc(100%-0.5rem)] w-[calc(50%-0.25rem)] rounded bg-background shadow-sm transition-transform duration-200 ease-out" />
              <button
                type="button"
                onClick={event => {
                  event.preventDefault();
                  event.stopPropagation();
                  setCommentSort('default');
                }}
                className={`relative z-10 flex items-center gap-1 rounded px-1.5 py-1 text-xs transition-colors sm:px-2 ${
                  commentSort === 'default'
                    ? 'text-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Flame className="h-3 w-3" />
                {copywriting('post.comment_sort_default', '默认')}
              </button>
              <button
                type="button"
                onClick={event => {
                  event.preventDefault();
                  event.stopPropagation();
                  setCommentSort('latest');
                }}
                className={`relative z-10 flex items-center gap-1 rounded px-1.5 py-1 text-xs transition-colors sm:px-2 ${
                  commentSort === 'latest'
                    ? 'text-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Clock className="h-3 w-3" />
                {copywriting('post.comment_sort_latest', '最新')}
              </button>
            </div>
          </div>

          {isAuthenticated && !replyingTo && (
            <form onSubmit={handleSubmitNewComment} className="mb-4">
              <div className="flex gap-2">
                <Avatar
                  src={user?.avatar_url || null}
                  alt={user?.username || copywriting('common.user', '用户')}
                  size="sm"
                />
                <div className="flex-1 space-y-2">
                  <Textarea
                    placeholder={copywriting('post.comment_placeholder', '写下你的评论...')}
                    value={newCommentContent}
                    onChange={event => setNewCommentContent(event.target.value)}
                    maxLength={COMMENT_CONTENT_MAX_LENGTH}
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
                      {copywriting('post.comment_with_repost', '同时转发')}
                    </label>
                    <Button
                      type="submit"
                      size="sm"
                      disabled={!hasVisibleContent(newCommentContent) || createComment.isPending}
                    >
                      {copywriting('post.comments', '评论')}
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
                  autoExpandReplies={
                    !!focusedComment?.root_comment_id && focusedThreadRootId === comment.id
                  }
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
                  {copywriting('post.view_all_comments', '查看所有评论')}
                </button>
              )}
            </div>
          ) : (
            <p className="py-4 text-center text-sm text-muted-foreground">
              {isAuthenticated
                ? copywriting(
                    'post.empty_comments_authenticated',
                    '暂无评论，快来发表第一条评论吧。'
                  )
                : copywriting('post.empty_comments_guest', '暂无评论，登录后发表你的看法。')}
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
  const authorName =
    origin.author?.username ||
    copywriting('post.fallback_user', '用户{user_id}', { user_id: origin.author_id });
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
      {copywriting('post.original_missing', '原内容不存在')}
    </div>
  );
}

function PollBlock({
  postId,
  poll,
  requireLogin,
}: {
  postId: number;
  poll: Poll;
  requireLogin: () => boolean;
}) {
  const votePoll = useVotePoll(postId);
  const [currentPoll, setCurrentPoll] = useState(poll);
  const [animateProgress, setAnimateProgress] = useState(false);
  const showResults = currentPoll.has_voted;

  useEffect(() => {
    setCurrentPoll(poll);
  }, [poll]);

  useEffect(() => {
    if (!showResults) {
      setAnimateProgress(false);
      return;
    }

    setAnimateProgress(false);
    const frame = window.requestAnimationFrame(() => {
      setAnimateProgress(true);
    });

    return () => window.cancelAnimationFrame(frame);
  }, [showResults, currentPoll.selected_option_id]);

  const handleVote = (optionId: number) => {
    if (currentPoll.has_voted || votePoll.isPending) return;
    if (!requireLogin()) return;

    votePoll.mutate(optionId, {
      onSuccess: data => {
        setCurrentPoll(data);
      },
    });
  };

  return (
    <div className="mt-3 space-y-2">
      {currentPoll.options.map(option => {
        const isSelected = currentPoll.selected_option_id === option.id;
        return (
          <button
            key={option.id}
            type="button"
            onClick={event => {
              event.preventDefault();
              event.stopPropagation();
              handleVote(option.id);
            }}
            disabled={currentPoll.has_voted || votePoll.isPending}
            className="group relative min-h-10 w-full overflow-hidden rounded-lg border-0 bg-slate-100 px-3 py-2 text-left text-sm transition-colors hover:bg-slate-200 disabled:cursor-default disabled:hover:bg-slate-100"
          >
            {showResults && (
              <span
                className={`absolute inset-y-0 left-0 transition-[width] duration-500 ease-out ${
                  isSelected ? 'bg-sky-300' : 'bg-sky-100'
                }`}
                style={{ width: animateProgress ? `${option.percentage}%` : 0 }}
              />
            )}
            <span className="relative flex items-center justify-between gap-3">
              <span className="break-words text-foreground">{option.text}</span>
              {showResults && (
                <span
                  className={`shrink-0 text-xs ${isSelected ? 'text-sky-800' : 'text-slate-500'}`}
                >
                  {option.percentage}%
                </span>
              )}
            </span>
          </button>
        );
      })}
      {showResults && (
        <p className="px-1 text-xs text-muted-foreground">
          {copywriting('post.vote_count', '{count} 票', { count: currentPoll.total_votes })}
        </p>
      )}
    </div>
  );
}

function ReportDialog({
  targetLabel,
  saving,
  error,
  onClose,
  onConfirm,
}: {
  targetLabel: string;
  saving: boolean;
  error: string;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState('');
  const trimmedReason = reason.trim();

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={event => event.stopPropagation()}
    >
      <div className="w-full max-w-lg rounded-lg border border-border bg-background p-5 shadow-xl">
        <div>
          <h2 className="text-lg font-semibold">
            {copywriting('report.title', '举报{target}', { target: targetLabel })}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {copywriting('report.description', '请填写违规类型及举报原因，确认违规后将被处理。')}
          </p>
        </div>
        <Textarea
          value={reason}
          onChange={event => setReason(event.target.value)}
          placeholder={copywriting('report.reason_placeholder', '填写举报原因')}
          rows={4}
          className="mt-4"
          autoFocus
        />
        {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" className="rounded-md" onClick={onClose} disabled={saving}>
            {copywriting('common.cancel', '取消')}
          </Button>
          <Button
            className="rounded-md"
            disabled={saving || !trimmedReason}
            onClick={() => onConfirm(trimmedReason)}
          >
            {saving
              ? copywriting('report.submitting', '提交中...')
              : copywriting('report.submit', '提交举报')}
          </Button>
        </div>
      </div>
    </div>
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
  threadRootId?: number;
  autoExpandReplies?: boolean;
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
  threadRootId,
  autoExpandReplies = false,
}: CommentItemProps) {
  const navigate = useNavigate();
  const [showReplies, setShowReplies] = useState(false);
  const toggleCommentLike = useToggleCommentLike(postId, currentUserId, commentSort);
  const deleteComment = useDeleteComment(postId);
  const repost = useRepost();
  const createReport = useCreateReport();
  const {
    data: repliesData,
    fetchNextPage: fetchNextReplyPage,
    hasNextPage: hasNextReplyPage,
    isFetchingNextPage: isFetchingNextReplyPage,
    isLoading: isRepliesLoading,
  } = useCommentReplies(postId, comment.id, currentUserId, commentSort, {
    enabled: depth === 0 && showReplies && comment.reply_count > 0,
  });
  const itemRef = useRef<HTMLDivElement>(null);
  const isReplying = replyingTo?.id === comment.id;
  const [isRepostOpen, setIsRepostOpen] = useState(false);
  const [isMoreOpen, setIsMoreOpen] = useState(false);
  const [isReportOpen, setIsReportOpen] = useState(false);
  const [reportError, setReportError] = useState('');
  const [repostContent, setRepostContent] = useState('');
  const isTopLevel = depth === 0;
  const rootId = threadRootId ?? comment.root_comment_id ?? comment.id;
  const isCurrentUserComment = currentUserId === comment.owner_id;
  const loadedReplies = useMemo(
    () => repliesData?.pages.flatMap(page => page.items) || comment.children || [],
    [comment.children, repliesData?.pages]
  );
  const totalReplies = repliesData?.pages[0]?.total ?? comment.reply_count ?? loadedReplies.length;
  const hasReplies = isTopLevel && totalReplies > 0;
  const replyTargetOwner =
    !isTopLevel && comment.parent_id !== rootId ? comment.parent?.owner : null;
  const replyTargetUsername =
    replyTargetOwner?.username || parentOwner?.username || comment.owner?.username;
  const replyTargetId = replyTargetOwner?.id || parentOwner?.id || comment.owner_id;

  useEffect(() => {
    if (autoExpandReplies) {
      setShowReplies(true);
    }
  }, [autoExpandReplies]);

  useEffect(() => {
    if (!isTopLevel || !showReplies || !focusedCommentId) return;
    if (loadedReplies.some(reply => reply.id === focusedCommentId)) return;
    if (!hasNextReplyPage || isFetchingNextReplyPage) return;

    fetchNextReplyPage();
  }, [
    fetchNextReplyPage,
    focusedCommentId,
    hasNextReplyPage,
    isFetchingNextReplyPage,
    isTopLevel,
    loadedReplies,
    showReplies,
  ]);

  const handleDeleteComment = (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    if (!isCurrentUserComment || deleteComment.isPending) return;

    deleteComment.mutate(comment.id, {
      onSuccess: () => setIsMoreOpen(false),
    });
  };

  const handleOpenCommentReport = (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    setReportError('');
    setIsReportOpen(true);
  };

  const handleSubmitCommentReport = (reason: string) => {
    setReportError('');
    createReport.mutate(
      { target_type: 'comment', target_id: comment.id, reason },
      {
        onSuccess: () => {
          setIsReportOpen(false);
          setIsMoreOpen(false);
        },
        onError: error => {
          const message =
            error instanceof Error
              ? error.message
              : copywriting('report.submit_failed', '举报提交失败，请稍后重试');
          setReportError(message);
        },
      }
    );
  };

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
          alt={
            comment.owner?.username ||
            copywriting('comments.fallback_user', '用户{user_id}', {
              user_id: comment.owner_id,
            })
          }
          size="sm"
        />
        <div className="min-w-0 flex-1">
          {!replyTargetOwner ? (
            <Link
              to={`/user/${comment.owner_id}`}
              className="text-sm font-medium text-foreground/70 hover:text-primary"
            >
              {comment.owner?.username ||
                copywriting('comments.fallback_user', '用户{user_id}', {
                  user_id: comment.owner_id,
                })}
            </Link>
          ) : (
            <div className="flex items-center gap-1 text-sm">
              <Link
                to={`/user/${comment.owner_id}`}
                className="font-medium text-foreground/70 hover:text-primary"
              >
                {comment.owner?.username ||
                  copywriting('comments.fallback_user', '用户{user_id}', {
                    user_id: comment.owner_id,
                  })}
              </Link>
              <span className="text-muted-foreground">{copywriting('common.reply', '回复')}</span>
              <Link
                to={`/user/${replyTargetId}`}
                className="text-muted-foreground hover:text-primary"
              >
                @{replyTargetUsername}
              </Link>
            </div>
          )}
          <p className="mt-0.5 whitespace-pre-wrap break-words text-sm text-foreground/85">
            <MentionText
              text={comment.content}
              users={comment.mention_users || []}
              onMentionClick={event => event.stopPropagation()}
            />
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
              <ThumbsUp className={`h-3 w-3 ${comment.is_liked ? 'fill-current' : ''}`} />
              {comment.like_count > 0 && <span>{comment.like_count}</span>}
            </button>
            {isAuthenticated && !isReplying && (
              <button
                onClick={event => {
                  event.preventDefault();
                  event.stopPropagation();
                  onReply(
                    comment.id,
                    comment.owner?.username ||
                      copywriting('comments.fallback_user', '用户{user_id}', {
                        user_id: comment.owner_id,
                      })
                  );
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
            {comment.created_by_agent && (
              <span className="comment-ai-label text-xs text-muted-foreground">
                {copywriting('common.ai_generated', 'AI生成')}
              </span>
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
                aria-label={copywriting('common.more_actions', '更多操作')}
              >
                <MoreHorizontal className="h-3.5 w-3.5" />
              </button>
              {isMoreOpen && (
                <div
                  className="auth-menu-enter menu-origin-bottom-right absolute bottom-7 right-0 z-20 min-w-28 rounded-md border border-border bg-background p-1 shadow-md"
                  onClick={event => event.stopPropagation()}
                >
                  {isCurrentUserComment && (
                    <button
                      className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-destructive hover:bg-destructive/10"
                      onClick={handleDeleteComment}
                      disabled={deleteComment.isPending}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      {copywriting('common.delete', '删除')}
                    </button>
                  )}
                  {!isCurrentUserComment && (
                    <button
                      className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
                      onClick={handleOpenCommentReport}
                    >
                      <Flag className="h-3.5 w-3.5" />
                      {copywriting('common.report', '举报')}
                    </button>
                  )}
                </div>
              )}
            </div>
            {hasReplies && (
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
                  {showReplies
                    ? copywriting('comments.collapse_replies', '收起回复')
                    : copywriting('comments.view_replies', '查看 {count} 条回复', {
                        count: totalReplies,
                      })}
                </span>
                <span className="reply-toggle-short">
                  {showReplies
                    ? copywriting('post.collapse', '收起')
                    : copywriting('comments.reply_count', '{count}回复', {
                        count: totalReplies,
                      })}
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
                    content: hasVisibleContent(repostContent) ? repostContent : undefined,
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
                placeholder={copywriting('post.repost_placeholder', '写点什么再转发...')}
                value={repostContent}
                onChange={event => setRepostContent(event.target.value)}
                maxLength={POST_CONTENT_MAX_LENGTH}
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
                  {copywriting('common.cancel', '取消')}
                </Button>
                <Button type="submit" size="sm" disabled={repost.isPending}>
                  {copywriting('common.repost', '转发')}
                </Button>
              </div>
            </form>
          )}
        </div>
      </div>

      {isReportOpen && (
        <ReportDialog
          targetLabel={copywriting('post.comments', '评论')}
          saving={createReport.isPending}
          error={reportError}
          onClose={() => setIsReportOpen(false)}
          onConfirm={handleSubmitCommentReport}
        />
      )}

      {showReplies && hasReplies && (
        <div className={isTopLevel ? 'pl-8' : 'pl-0'}>
          {isRepliesLoading ? (
            <div className="py-2">
              <CommentSkeleton />
            </div>
          ) : (
            loadedReplies.map(child => (
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
                  username:
                    comment.owner?.username ||
                    copywriting('comments.fallback_user', '用户{user_id}', {
                      user_id: comment.owner_id,
                    }),
                }}
                focusedCommentId={focusedCommentId}
                threadRootId={comment.id}
                autoExpandReplies={false}
              />
            ))
          )}
          {hasNextReplyPage && (
            <button
              type="button"
              onClick={event => {
                event.preventDefault();
                event.stopPropagation();
                fetchNextReplyPage();
              }}
              disabled={isFetchingNextReplyPage}
              className="mt-3 text-xs text-primary transition-colors hover:text-primary/80"
            >
              {isFetchingNextReplyPage
                ? copywriting('common.loading', '加载中...')
                : copywriting('comments.expand_more', '展开更多回复 ({visible}/{total})', {
                    visible: loadedReplies.length,
                    total: totalReplies,
                  })}
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
    if (!hasVisibleContent(content) || createComment.isPending) return;

    createComment.mutate(
      {
        content,
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
          <span>
            {copywriting('comments.reply_to', '回复 @{username}', {
              username: replyToUsername,
            })}
          </span>
          <button
            type="button"
            onClick={event => {
              event.stopPropagation();
              onCancel();
            }}
            className="text-primary hover:text-primary/80"
          >
            {copywriting('common.cancel', '取消')}
          </button>
        </div>
        <Textarea
          placeholder={copywriting('comments.reply_placeholder', '写下你的回复...')}
          value={content}
          onChange={event => setContent(event.target.value)}
          maxLength={COMMENT_CONTENT_MAX_LENGTH}
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
            {copywriting('post.comment_with_repost', '同时转发')}
          </label>
          <Button
            type="submit"
            size="sm"
            disabled={!hasVisibleContent(content) || createComment.isPending}
          >
            {copywriting('post.comments', '评论')}
          </Button>
        </div>
      </div>
    </form>
  );
}
