import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Bell, Heart, MessageCircle, UserPlus } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { Avatar, Button, Skeleton, Textarea } from '@/shared/components/ui';
import { formatDate } from '@/shared/lib/utils';
import {
  NotificationItem,
  useNotifications,
} from '@/features/notification';
import { useAuthStore } from '@/features/auth';
import { useCreateComment, useToggleCommentLike } from '@/features/comment';
import { useFollowStatus, useToggleFollow } from '@/features/follow';

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
    <div className="bg-white shadow-sm rounded-lg">
      <div className="px-5 py-4 border-b border-border">
        <h1 className="text-xl font-semibold">消息</h1>
      </div>

      {items.length === 0 ? (
        <div className="py-16 text-center text-muted-foreground">
          <Bell className="h-10 w-10 mx-auto mb-3" />
          <p>暂无消息</p>
        </div>
      ) : (
        <div className="divide-y divide-border">
          {items.map((item) => (
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

  const handleOpen = () => {
    navigate(targetPath);
  };

  return (
    <div className="px-5 py-4 hover:bg-muted/30 transition-colors">
      <div className="flex gap-3">
        <Link to={sender ? `/user/${sender.id}` : '#'} onClick={(e) => e.stopPropagation()}>
          <Avatar
            src={sender?.avatar_url}
            alt={sender?.username ?? '用户'}
            size="md"
          />
        </Link>

        <div className="min-w-0 flex-1">
          <button
            type="button"
            onClick={handleOpen}
            className="block w-full text-left"
          >
            <div className="flex items-center gap-2 text-sm">
              <Icon className={`h-4 w-4 ${typeInfo.color}`} />
              <span className="font-medium">
                {sender?.username ?? '有人'}
              </span>
              <span className="text-muted-foreground">{typeInfo.label}</span>
              <span className="ml-auto text-xs text-muted-foreground">
                {formatDate(notification.created_at)}
              </span>
            </div>

            {notification.source_content && (
              <p className="mt-2 text-sm text-foreground/80 line-clamp-2 whitespace-pre-wrap break-words">
                {notification.source_content}
              </p>
            )}
          </button>

          <NotificationActions notification={notification} />
        </div>
      </div>
    </div>
  );
}

function NotificationActions({ notification }: { notification: NotificationItem }) {
  if (notification.type === 'follow' && notification.sender) {
    return <FollowBackButton userId={notification.sender.id} />;
  }

  if (
    (notification.type === 'comment' || notification.type === 'comment_reply' || notification.type === 'comment_like') &&
    notification.post_id &&
    notification.comment_id
  ) {
    return (
      <CommentActionBar
        postId={notification.post_id}
        commentId={notification.comment_id}
      />
    );
  }

  return null;
}

function CommentActionBar({ postId, commentId }: { postId: number; commentId: number }) {
  const { user } = useAuthStore();
  const likeMutation = useToggleCommentLike(postId, user?.id);
  const createComment = useCreateComment(postId);
  const [isReplying, setIsReplying] = useState(false);
  const [content, setContent] = useState('');

  const submitReply = (event: React.FormEvent) => {
    event.preventDefault();
    if (!content.trim()) return;

    createComment.mutate(
      { content: content.trim(), parent_id: commentId },
      {
        onSuccess: () => {
          setContent('');
          setIsReplying(false);
        },
      }
    );
  };

  return (
    <div className="mt-3 space-y-2">
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 rounded-md gap-1"
          onClick={() => likeMutation.mutate({ commentId })}
          disabled={!user || likeMutation.isPending}
        >
          <Heart className="h-3.5 w-3.5" />
          点赞
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 rounded-md gap-1"
          onClick={() => setIsReplying((value) => !value)}
          disabled={!user}
        >
          <MessageCircle className="h-3.5 w-3.5" />
          回复
        </Button>
      </div>

      {isReplying && (
        <form onSubmit={submitReply} className="space-y-2">
          <Textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            rows={2}
            placeholder="写下你的回复..."
            className="border-0 shadow-none bg-muted/30 focus-visible:ring-0"
          />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={() => setIsReplying(false)}>
              取消
            </Button>
            <Button type="submit" size="sm" disabled={!content.trim() || createComment.isPending}>
              回复
            </Button>
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
      variant="outline"
      size="sm"
      className="mt-3 h-7 px-3 rounded-md gap-1"
      onClick={() => toggleFollow.mutate(userId)}
      disabled={toggleFollow.isPending}
    >
      <UserPlus className="h-3.5 w-3.5" />
      回关
    </Button>
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

function getTypeInfo(type: string) {
  const map = {
    post_like: { label: '赞了你的帖子', icon: Heart, color: 'text-red-500' },
    comment_like: { label: '赞了你的评论', icon: Heart, color: 'text-red-500' },
    comment: { label: '评论了你的帖子', icon: MessageCircle, color: 'text-primary' },
    comment_reply: { label: '回复了你', icon: MessageCircle, color: 'text-primary' },
    follow: { label: '关注了你', icon: UserPlus, color: 'text-emerald-600' },
  };

  return map[type as keyof typeof map] ?? { label: '给你发来一条消息', icon: Bell, color: 'text-muted-foreground' };
}

function NotificationSkeleton() {
  return (
    <div className="bg-white shadow-sm rounded-lg p-5 space-y-5">
      <Skeleton className="h-7 w-24" />
      {Array.from({ length: 5 }).map((_, index) => (
        <div key={index} className="flex gap-3">
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
