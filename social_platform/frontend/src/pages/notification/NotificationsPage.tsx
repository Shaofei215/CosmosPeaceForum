import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  AtSign,
  Bell,
  FileText,
  Info,
  MessageCircle,
  Repeat2,
  ShieldAlert,
  ThumbsUp,
  UserPlus,
} from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { Avatar, Button, Skeleton, Textarea } from '@/shared/components/ui';
import { formatDate } from '@/shared/lib/utils';
import { PLATFORM_DISPLAY_NAME } from '@/shared/config/branding';
import { BrandImage } from '@/shared/components/BrandImage';
import { COMMENT_CONTENT_MAX_LENGTH } from '@/shared/config/contentLimits';
import {
  NotificationItem,
  useNotifications,
  useSubmitModerationAppeal,
} from '@/features/notification';
import { useAuthStore } from '@/features/auth';
import { useCommentLikeStatus, useCreateComment, useToggleCommentLike } from '@/features/comment';
import { useFollowStatus, useToggleFollow } from '@/features/follow';
import { useLikeStatus, useToggleLike } from '@/features/like';
import { hasVisibleContent } from '@/shared/lib/content';
import { copywriting } from '@/shared/config/copywriting';

export default function NotificationsPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useNotifications({ limit: 50 });

  useEffect(() => {
    if (data) {
      queryClient.invalidateQueries({ queryKey: ['notifications', 'unread-count'] });
      queryClient.invalidateQueries({ queryKey: ['notifications', 'summary'] });
    }
  }, [data, queryClient]);

  if (isLoading) {
    return <NotificationSkeleton />;
  }

  const items = data?.items ?? [];

  return (
    <div className="overflow-hidden rounded-lg bg-white p-0 shadow-sm">
      <h2 className="text-lg font-semibold px-3 pt-3">
        {copywriting('notifications.title', '消息')}
      </h2>

      {items.length === 0 ? (
        <div className="py-10 text-center text-muted-foreground">
          <Bell className="h-10 w-10 mx-auto mb-3" />
          <p>{copywriting('notifications.empty', '暂无消息')}</p>
        </div>
      ) : (
        <div className="divide-y divide-border/50">
          {items.map(item => (
            <NotificationRow key={item.id} notification={item} />
          ))}
        </div>
      )}
    </div>
  );
}

function NotificationRow({ notification }: { notification: NotificationItem }) {
  const navigate = useNavigate();
  const typeInfo = getTypeInfo(notification.type);
  const Icon = typeInfo.icon;
  const sender = notification.sender;
  const targetPath = getTargetPath(notification);
  const isArticle = notification.source_post_type === 'article';
  const isPlatformSystem = isPlatformSystemNotification(notification);
  const senderName =
    sender?.username ??
    (isPlatformSystem ? PLATFORM_DISPLAY_NAME : copywriting('common.someone', '有人'));
  const shouldShowFullContent =
    notification.type === 'moderation' || notification.type === 'announcement';

  const handleOpen = () => {
    navigate(targetPath);
  };

  return (
    <div className="p-3 transition-colors hover:bg-muted/30 sm:p-4">
      <div className="flex gap-2 sm:gap-3">
        {sender ? (
          <Link to={`/user/${sender.id}`} onClick={e => e.stopPropagation()}>
            <Avatar
              src={sender.avatar_url}
              alt={sender.username ?? copywriting('common.user', '用户')}
              size="md"
            />
          </Link>
        ) : isPlatformSystem ? (
          <div className="relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full">
            <BrandImage
              name="logo"
              alt={senderName}
              className="aspect-square h-full w-full object-cover"
            />
          </div>
        ) : (
          <Avatar alt={senderName} size="md" />
        )}

        <div className="min-w-0 flex-1">
          <button type="button" onClick={handleOpen} className="block w-full text-left">
            <div className="flex items-start gap-2 text-sm">
              <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${typeInfo.color}`} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                  <span className="font-medium truncate">{senderName}</span>
                  <span className="text-muted-foreground shrink-0">{typeInfo.label}</span>
                  <span className="text-xs text-muted-foreground sm:ml-auto shrink-0">
                    {formatDate(notification.created_at)}
                  </span>
                </div>
              </div>
            </div>

            {notification.source_content && (
              <div className="mt-2 flex min-w-0 gap-2 rounded-md bg-muted/30 px-3 py-2">
                {isArticle && <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />}
                <p
                  className={`min-w-0 max-w-full text-sm whitespace-pre-wrap break-words [overflow-wrap:anywhere] ${
                    shouldShowFullContent ? '' : 'line-clamp-2'
                  } ${isArticle ? 'text-muted-foreground' : 'text-foreground/85'}`}
                >
                  {notification.source_content}
                </p>
              </div>
            )}
          </button>

          <NotificationActions notification={notification} />
        </div>
      </div>
    </div>
  );
}

function NotificationActions({ notification }: { notification: NotificationItem }) {
  if (notification.type === 'moderation') {
    return <ModerationAppealAction notification={notification} />;
  }

  if (notification.type === 'follow' && notification.sender) {
    return <FollowBackButton userId={notification.sender.id} />;
  }

  if (
    (notification.type === 'comment' ||
      notification.type === 'comment_reply' ||
      notification.type === 'comment_like' ||
      (notification.type === 'mention' && notification.resource_type === 'comment')) &&
    notification.post_id &&
    notification.comment_id
  ) {
    return <CommentActionBar postId={notification.post_id} commentId={notification.comment_id} />;
  }

  if (
    (notification.type === 'post_like' ||
      notification.type === 'repost' ||
      (notification.type === 'mention' && notification.resource_type === 'post')) &&
    notification.post_id
  ) {
    return <PostActionBar postId={notification.post_id} />;
  }

  return null;
}

function ModerationAppealAction({ notification }: { notification: NotificationItem }) {
  const submitAppeal = useSubmitModerationAppeal();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const canAppeal = Boolean(notification.can_appeal);
  const statusText =
    notification.appeal_status === 'pending'
      ? copywriting('notifications.appeal_pending', '申诉待处理')
      : notification.appeal_status === 'approved'
        ? copywriting('notifications.appeal_approved', '申诉已通过')
        : notification.appeal_status === 'rejected'
          ? copywriting('notifications.appeal_rejected', '申诉已拒绝')
          : null;

  if (!canAppeal) {
    return null;
  }

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const value = reason.trim();
    if (!value) {
      setError(copywriting('notifications.appeal_reason_required', '请填写申诉理由'));
      return;
    }
    setError('');
    submitAppeal.mutate(
      { notificationId: notification.id, reason: value },
      {
        onSuccess: () => {
          setReason('');
          setOpen(false);
        },
        onError: error => {
          const message =
            error && typeof error === 'object' && 'message' in error
              ? String((error as { message?: unknown }).message)
              : copywriting('notifications.appeal_submit_failed', '提交失败，请稍后重试');
          setError(message);
        },
      }
    );
  };

  return (
    <div className="mt-2">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 rounded-md gap-1 text-muted-foreground hover:text-primary"
          onClick={() => setOpen(true)}
          disabled={notification.appeal_status === 'approved'}
        >
          <ShieldAlert className="h-3.5 w-3.5" />
          {copywriting('notifications.appeal_action', '申诉')}
        </Button>
        {statusText && <span className="text-xs text-muted-foreground">{statusText}</span>}
      </div>
      {open && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4">
          <form
            onSubmit={submit}
            className="w-full max-w-lg rounded-lg bg-white p-4 shadow-xl"
            onClick={event => event.stopPropagation()}
          >
            <div className="mb-3">
              <h3 className="text-base font-semibold">
                {copywriting('notifications.appeal_dialog_title', '提交申诉')}
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {notification.appeal_status === 'pending'
                  ? copywriting(
                      'notifications.appeal_replace_hint',
                      '再次提交会覆盖当前待处理申诉理由。'
                    )
                  : copywriting('notifications.appeal_hint', '说明你认为本次处理需要复核的原因。')}
              </p>
            </div>
            <Textarea
              value={reason}
              onChange={event => setReason(event.target.value)}
              rows={5}
              maxLength={1000}
              placeholder={copywriting('notifications.appeal_placeholder', '填写申诉理由')}
            />
            {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
            <div className="mt-4 flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                {copywriting('common.cancel', '取消')}
              </Button>
              <Button type="submit" disabled={!reason.trim() || submitAppeal.isPending}>
                {copywriting('common.submit', '提交')}
              </Button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function CommentActionBar({ postId, commentId }: { postId: number; commentId: number }) {
  const { user } = useAuthStore();
  const { data: likeStatus } = useCommentLikeStatus(postId, commentId, !!user);
  const likeMutation = useToggleCommentLike(postId, user?.id);
  const createComment = useCreateComment(postId);
  const [isReplying, setIsReplying] = useState(false);
  const [content, setContent] = useState('');
  const [shouldRepost, setShouldRepost] = useState(false);
  const isLiked = likeStatus?.is_liked ?? false;

  const submitReply = (event: React.FormEvent) => {
    event.preventDefault();
    if (!hasVisibleContent(content)) return;

    createComment.mutate(
      { content, parent_id: commentId, repost: shouldRepost },
      {
        onSuccess: () => {
          setContent('');
          setIsReplying(false);
          setShouldRepost(false);
        },
      }
    );
  };

  return (
    <div className="mt-2 space-y-2">
      <div className="flex flex-wrap items-center gap-2 sm:gap-4">
        <Button
          variant="ghost"
          size="sm"
          className={`h-7 px-2 rounded-md gap-1 ${
            isLiked ? 'text-red-500 hover:text-red-500' : 'text-muted-foreground hover:text-red-500'
          }`}
          onClick={() => likeMutation.mutate({ commentId })}
          disabled={!user || likeMutation.isPending}
        >
          <ThumbsUp className={`h-3.5 w-3.5 ${isLiked ? 'fill-current' : ''}`} />
          {copywriting('common.like', '点赞')}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className={`h-7 px-2 rounded-md gap-1 ${
            isReplying
              ? 'text-primary hover:text-primary'
              : 'text-muted-foreground hover:text-primary'
          }`}
          onClick={() => setIsReplying(value => !value)}
          disabled={!user}
        >
          <MessageCircle className="h-3.5 w-3.5" />
          {copywriting('common.reply', '回复')}
        </Button>
      </div>

      {isReplying && (
        <form onSubmit={submitReply} className="space-y-2">
          <Textarea
            value={content}
            onChange={event => setContent(event.target.value)}
            maxLength={COMMENT_CONTENT_MAX_LENGTH}
            rows={2}
            placeholder={copywriting('notifications.reply_placeholder', '写下你的回复...')}
            className="border-0 shadow-none bg-muted/30 focus-visible:ring-0"
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
            <div className="flex gap-2">
              <Button type="button" variant="ghost" size="sm" onClick={() => setIsReplying(false)}>
                {copywriting('common.cancel', '取消')}
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={!hasVisibleContent(content) || createComment.isPending}
              >
                {copywriting('common.reply', '回复')}
              </Button>
            </div>
          </div>
        </form>
      )}
    </div>
  );
}

function FollowBackButton({ userId }: { userId: number }) {
  const { user } = useAuthStore();
  const { data: status } = useFollowStatus(userId);
  const toggleFollow = useToggleFollow();

  if (!user || user.id === userId || status?.is_following) {
    return null;
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      className="mt-2 h-7 gap-1 rounded-md px-2 text-muted-foreground hover:text-foreground"
      onClick={() => toggleFollow.mutate(userId)}
      disabled={toggleFollow.isPending}
    >
      <UserPlus className="h-3.5 w-3.5" />
      {copywriting('notifications.follow_back', '回关')}
    </Button>
  );
}

function PostActionBar({ postId }: { postId: number }) {
  const { user } = useAuthStore();
  const { data: likeStatus } = useLikeStatus(postId, !!user);
  const likeMutation = useToggleLike();
  const createComment = useCreateComment(postId);
  const [isReplying, setIsReplying] = useState(false);
  const [content, setContent] = useState('');
  const [shouldRepost, setShouldRepost] = useState(false);
  const isLiked = likeStatus?.is_liked ?? false;

  const submitReply = (event: React.FormEvent) => {
    event.preventDefault();
    if (!hasVisibleContent(content)) return;

    createComment.mutate(
      { content, repost: shouldRepost },
      {
        onSuccess: () => {
          setContent('');
          setIsReplying(false);
          setShouldRepost(false);
        },
      }
    );
  };

  return (
    <div className="mt-2 space-y-2">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          className={`h-7 px-2 rounded-md gap-1 ${
            isLiked ? 'text-red-500 hover:text-red-500' : 'text-muted-foreground hover:text-red-500'
          }`}
          onClick={() => likeMutation.mutate(postId)}
          disabled={!user || likeMutation.isPending}
        >
          <ThumbsUp className={`h-3.5 w-3.5 ${isLiked ? 'fill-current' : ''}`} />
          {copywriting('common.like', '点赞')}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className={`h-7 px-2 rounded-md gap-1 ${
            isReplying
              ? 'text-primary hover:text-primary'
              : 'text-muted-foreground hover:text-primary'
          }`}
          onClick={() => setIsReplying(value => !value)}
          disabled={!user}
        >
          <MessageCircle className="h-3.5 w-3.5" />
          {copywriting('common.reply', '回复')}
        </Button>
      </div>

      {isReplying && (
        <form onSubmit={submitReply} className="space-y-2">
          <Textarea
            value={content}
            onChange={event => setContent(event.target.value)}
            maxLength={COMMENT_CONTENT_MAX_LENGTH}
            rows={2}
            placeholder={copywriting('notifications.reply_placeholder', '写下你的回复...')}
            className="border-0 shadow-none bg-muted/30 focus-visible:ring-0"
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
            <div className="flex gap-2">
              <Button type="button" variant="ghost" size="sm" onClick={() => setIsReplying(false)}>
                {copywriting('common.cancel', '取消')}
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={!hasVisibleContent(content) || createComment.isPending}
              >
                {copywriting('common.reply', '回复')}
              </Button>
            </div>
          </div>
        </form>
      )}
    </div>
  );
}

function getTargetPath(notification: NotificationItem): string {
  if (notification.type === 'follow' && notification.sender) {
    return `/user/${notification.sender.id}`;
  }
  if (notification.post_id && notification.comment_id) {
    return `/post/${notification.post_id}?commentId=${notification.comment_id}`;
  }
  if (notification.post_id) {
    return `/post/${notification.post_id}`;
  }
  if (notification.sender) {
    return `/user/${notification.sender.id}`;
  }
  return '/feed';
}

function isPlatformSystemNotification(notification: NotificationItem): boolean {
  return (
    !notification.sender &&
    (notification.type === 'moderation' || notification.type === 'announcement')
  );
}

function getTypeInfo(type: string) {
  const map = {
    repost: {
      label: copywriting('notifications.repost', '转发了你的内容'),
      icon: Repeat2,
      color: 'text-primary',
    },
    post_like: {
      label: copywriting('notifications.post_like', '赞了你的帖子'),
      icon: ThumbsUp,
      color: 'text-primary',
    },
    comment_like: {
      label: copywriting('notifications.comment_like', '赞了你的评论'),
      icon: ThumbsUp,
      color: 'text-primary',
    },
    comment: {
      label: copywriting('notifications.comment', '评论了你的帖子'),
      icon: MessageCircle,
      color: 'text-primary',
    },
    comment_reply: {
      label: copywriting('notifications.comment_reply', '回复了你'),
      icon: MessageCircle,
      color: 'text-primary',
    },
    mention: {
      label: copywriting('notifications.mention', '提及了你'),
      icon: AtSign,
      color: 'text-primary',
    },
    follow: {
      label: copywriting('notifications.follow', '关注了你'),
      icon: UserPlus,
      color: 'text-emerald-600',
    },
    moderation: {
      label: copywriting('notifications.moderation', '发来一条管理通知'),
      icon: Info,
      color: 'text-destructive',
    },
    announcement: {
      label: copywriting('notifications.announcement', '发布了一条公告'),
      icon: Bell,
      color: 'text-primary',
    },
  };

  return (
    map[type as keyof typeof map] ?? {
      label: copywriting('notifications.direct_message', '给你发来一条消息'),
      icon: Info,
      color: 'text-sky-600',
    }
  );
}

function NotificationSkeleton() {
  return (
    <div className="rounded-lg bg-white shadow-sm p-0">
      <Skeleton className="ml-3 mt-3 h-6 w-20" />
      {Array.from({ length: 5 }).map((_, index) => (
        <div key={index} className="flex gap-3 p-4 border-b border-border/50 last:border-b-0">
          <Skeleton className="h-10 w-10 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-full" />
          </div>
        </div>
      ))}
    </div>
  );
}
