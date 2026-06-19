/**
 * 用户资料页面
 */

import { useParams, Link, useNavigate } from 'react-router-dom';
import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import { useUpdateUser, useUploadAvatar, useUser } from '@/features/user';
import { useInfiniteUserFeed } from '@/features/feed';
import { useToggleFollow, useFollowStatus } from '@/features/follow';
import { useAuthStore, useLogout } from '@/features/auth';
import { useCreateReport } from '@/features/report';
import { PostCard } from '@/widgets/post-card';
import { Avatar, Skeleton, Button, Input, Textarea } from '@/shared/components/ui';
import { Camera, Flag, MoreVertical, Pencil, Save, X } from 'lucide-react';

const MAX_AVATAR_SIZE = 5 * 1024 * 1024;
const MAX_USERNAME_LENGTH = 30;
const MAX_BIO_LENGTH = 100;

/**
 * 从 API 或运行时错误中提取可展示的中文错误信息。
 */
function extractErrorMessage(err: unknown): string | null {
  if (typeof err === 'object' && err !== null) {
    const e = err as Record<string, unknown>;
    if (typeof e.message === 'string') {
      return e.message;
    }
    if (Array.isArray(e.message)) {
      return (e.message as Array<Record<string, unknown>>)
        .map(item => (typeof item.msg === 'string' ? item.msg : JSON.stringify(item)))
        .join(', ');
    }
  }
  if (err instanceof Error) {
    return err.message;
  }
  return null;
}

/**
 * 用户资料页面组件
 */
export default function ProfilePage() {
  const { userId } = useParams<{ userId: string }>();
  const { user: currentUser, isAuthenticated } = useAuthStore();
  const logout = useLogout();
  const navigate = useNavigate();
  const userIdNum = Number(userId);

  const [isEditing, setIsEditing] = useState(false);
  const [draftUsername, setDraftUsername] = useState('');
  const [draftBio, setDraftBio] = useState('');
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreviewUrl, setAvatarPreviewUrl] = useState<string | null>(null);
  const [editError, setEditError] = useState('');
  const [avatarError, setAvatarError] = useState('');
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const [reportReason, setReportReason] = useState('');
  const [reportError, setReportError] = useState('');
  const avatarInputRef = useRef<HTMLInputElement>(null);
  const usernameInputRef = useRef<HTMLInputElement>(null);

  const updateUser = useUpdateUser();
  const uploadAvatar = useUploadAvatar();
  const createReport = useCreateReport();

  const toggleFollow = useToggleFollow();
  const { data: followStatus } = useFollowStatus(userIdNum);

  /**
   * 处理登出
   */
  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleFollow = () => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    toggleFollow.mutate(userIdNum);
  };

  /** 打开用户举报弹窗，未登录用户先进入登录页。 */
  const handleOpenReport = () => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    setReportReason('');
    setReportError('');
    setIsUserMenuOpen(false);
    setReportOpen(true);
  };

  /** 提交用户举报，管理端会在用户审查队列中聚合处理。 */
  const handleSubmitReport = async () => {
    if (!user) return;
    const reason = reportReason.trim();
    if (!reason) {
      setReportError('请填写举报原因');
      return;
    }
    setReportError('');
    try {
      await createReport.mutateAsync({
        target_type: 'user',
        target_id: user.id,
        reason,
      });
      setReportOpen(false);
      setReportReason('');
    } catch (err) {
      setReportError(extractErrorMessage(err) || '举报提交失败，请稍后重试');
    }
  };

  const { data: user, isLoading: isUserLoading } = useUser(userIdNum);
  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading: isFeedLoading,
  } = useInfiniteUserFeed(userIdNum, currentUser?.id);

  const isSaving = updateUser.isPending || uploadAvatar.isPending;

  // 无限滚动监听
  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (user && !isEditing) {
      setDraftUsername(user.username);
      setDraftBio(user.bio ?? '');
      setAvatarFile(null);
      setAvatarPreviewUrl(null);
      setEditError('');
      setAvatarError('');
    }
  }, [isEditing, user]);

  useEffect(() => {
    if (isEditing) {
      usernameInputRef.current?.focus();
      usernameInputRef.current?.select();
    }
  }, [isEditing]);

  useEffect(() => {
    return () => {
      if (avatarPreviewUrl) {
        URL.revokeObjectURL(avatarPreviewUrl);
      }
    };
  }, [avatarPreviewUrl]);

  useEffect(() => {
    if (observerRef.current) {
      observerRef.current.disconnect();
    }

    observerRef.current = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
        fetchNextPage();
      }
    });

    if (loadMoreRef.current) {
      observerRef.current.observe(loadMoreRef.current);
    }

    return () => observerRef.current?.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // 合并所有页面的帖子
  const posts = data?.pages.flatMap(page => page.data) || [];

  /** 进入资料编辑模式，并以当前用户资料初始化草稿。 */
  const handleEnterEdit = () => {
    if (user == null) return;
    setDraftUsername(user.username);
    setDraftBio(user.bio ?? '');
    setAvatarFile(null);
    setAvatarPreviewUrl(null);
    setEditError('');
    setAvatarError('');
    setIsUserMenuOpen(false);
    setIsEditing(true);
  };

  /** 放弃本次编辑并恢复进入编辑前的展示状态。 */
  const handleCancelEdit = () => {
    if (user == null) return;
    setDraftUsername(user.username);
    setDraftBio(user.bio ?? '');
    setAvatarFile(null);
    setAvatarPreviewUrl(null);
    setEditError('');
    setAvatarError('');
    setIsUserMenuOpen(false);
    setIsEditing(false);
  };

  /** 校验头像文件并生成本地预览，真正上传会在保存时执行。 */
  const handleAvatarChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (file == null) return;

    setAvatarError('');
    if (file.type.startsWith('image/') === false) {
      setAvatarError('请选择图片文件');
      return;
    }
    if (file.size > MAX_AVATAR_SIZE) {
      setAvatarError('图片大小不能超过 5MB');
      return;
    }

    setAvatarFile(file);
    setAvatarPreviewUrl(URL.createObjectURL(file));
  };

  /** 保存昵称、签名和头像草稿，并同步远端与本地缓存。 */
  const handleSave = async () => {
    if (user == null) return;

    const username = draftUsername.trim();
    const bio = draftBio.trim();
    const usernamePattern = new RegExp('^[a-zA-Z0-9_\u4e00-\u9fa5]+' + String.fromCharCode(36));
    setEditError('');
    setAvatarError('');

    if (username === '') {
      setEditError('请输入昵称');
      return;
    }
    if (usernamePattern.test(username) === false) {
      setEditError('昵称只能包含字母、数字、下划线和中文');
      return;
    }

    try {
      await updateUser.mutateAsync({
        userId: user.id,
        data: { username, bio },
      });
      if (avatarFile) {
        await uploadAvatar.mutateAsync(avatarFile);
      }
      setAvatarFile(null);
      setAvatarPreviewUrl(null);
      setIsUserMenuOpen(false);
      setIsEditing(false);
    } catch (err) {
      setEditError(extractErrorMessage(err) || '保存失败，请稍后重试');
    }
  };

  if (isUserLoading) {
    return <ProfileSkeleton />;
  }

  if (!user) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">用户不存在</p>
        <Link to="/feed" className="text-primary hover:underline mt-2 inline-block">
          返回主页
        </Link>
      </div>
    );
  }

  const isCurrentUser = currentUser?.id === user.id;

  return (
    <div className="space-y-3">
      {/* 用户资料卡片 */}
      <div className="rounded-lg bg-white p-4 shadow-sm sm:p-5">
        <div className="flex min-h-[84px] items-center gap-3 sm:gap-4">
          <div className="relative shrink-0">
            <button
              type="button"
              onClick={() => isEditing && avatarInputRef.current?.click()}
              disabled={isSaving || isEditing === false}
              className="group relative block rounded-full disabled:cursor-default"
              aria-label="上传头像"
            >
              <Avatar
                src={avatarPreviewUrl ?? user.avatar_url}
                alt={draftUsername || user.username}
                size="xl"
              />
              {isEditing && (
                <span className="absolute inset-0 flex items-center justify-center rounded-full bg-black/45 opacity-0 transition-opacity group-hover:opacity-100">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/90 text-foreground shadow-sm">
                    {isSaving ? (
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                    ) : (
                      <Camera className="h-4 w-4" />
                    )}
                  </span>
                </span>
              )}
            </button>
            <input
              ref={avatarInputRef}
              type="file"
              accept="image/*"
              onChange={handleAvatarChange}
              className="hidden"
              disabled={isSaving}
            />
          </div>
          <div className="min-w-0 flex-1">
            {isEditing ? (
              <Input
                ref={usernameInputRef}
                value={draftUsername}
                onChange={event => setDraftUsername(event.target.value)}
                disabled={isSaving}
                maxLength={MAX_USERNAME_LENGTH}
                aria-label="昵称"
                className="h-auto truncate border-0 bg-transparent px-0 py-0 text-xl font-bold shadow-none focus-visible:ring-1 sm:text-2xl"
              />
            ) : (
              <h1 className="min-w-0 truncate text-xl font-bold sm:text-2xl">{user.username}</h1>
            )}
            {isEditing ? (
              <Input
                value={draftBio}
                onChange={event => setDraftBio(event.target.value)}
                disabled={isSaving}
                maxLength={MAX_BIO_LENGTH}
                aria-label="签名"
                placeholder="写一句签名"
                className="mt-1 h-5 truncate border-0 bg-transparent px-0 py-0 text-sm text-muted-foreground shadow-none focus-visible:ring-1"
              />
            ) : (
              user.bio && (
                <p className="mt-1 line-clamp-1 text-sm text-muted-foreground">{user.bio}</p>
              )
            )}
            {(editError ? editError : avatarError) && (
              <p className="mt-2 text-xs text-destructive">{editError ? editError : avatarError}</p>
            )}
            <div className="mt-3 flex items-center gap-4">
              <Link
                to={'/user/' + user.id + '/following'}
                className="text-sm text-muted-foreground transition-colors hover:text-primary"
              >
                <span className="font-medium text-foreground">{user.following_count ?? 0}</span>{' '}
                关注
              </Link>
              <Link
                to={'/user/' + user.id + '/followers'}
                className="text-sm text-muted-foreground transition-colors hover:text-primary"
              >
                <span className="font-medium text-foreground">{user.followers_count ?? 0}</span>{' '}
                粉丝
              </Link>
            </div>
          </div>
          {isCurrentUser === false && (
            <Button
              variant={followStatus?.is_following ? 'outline' : 'default'}
              size="sm"
              onClick={handleFollow}
              disabled={toggleFollow.isPending}
              className={
                followStatus?.is_following
                  ? 'shrink-0 self-center border-[var(--theme-accent-bg)] px-4 text-[var(--theme-accent-bg)] hover:bg-[var(--theme-subtle-bg)]'
                  : 'shrink-0 self-center px-4'
              }
            >
              {toggleFollow.isPending ? (
                <div className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
              ) : followStatus?.is_mutual ? (
                '互相关注'
              ) : followStatus?.is_following ? (
                '已关注'
              ) : (
                '关注'
              )}
            </Button>
          )}
          <div className="relative flex shrink-0 items-center self-center">
            {isCurrentUser && (
              <div className="flex items-center gap-2">
                {isEditing ? (
                  <>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleSave}
                      disabled={isSaving}
                      className="gap-1 px-2 text-muted-foreground shadow-none hover:bg-transparent hover:text-foreground sm:px-3"
                      aria-label="保存资料"
                    >
                      {isSaving ? (
                        <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent sm:hidden" />
                      ) : (
                        <Save className="h-4 w-4 sm:hidden" />
                      )}
                      <span className="hidden sm:inline">保存</span>
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleCancelEdit}
                      disabled={isSaving}
                      className="gap-1 px-2 text-muted-foreground shadow-none hover:bg-transparent hover:text-foreground sm:px-3"
                      aria-label="退出编辑"
                    >
                      <X className="h-4 w-4 sm:hidden" />
                      <span className="hidden sm:inline">退出</span>
                    </Button>
                  </>
                ) : (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleEnterEdit}
                    className="gap-1 px-2 text-muted-foreground shadow-none hover:bg-transparent hover:text-foreground sm:px-3"
                    aria-label="编辑资料"
                  >
                    <Pencil className="h-4 w-4 sm:hidden" />
                    <span className="hidden sm:inline">编辑</span>
                  </Button>
                )}
              </div>
            )}
            <button
              type="button"
              className="flex h-7 w-7 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-foreground"
              onClick={event => {
                event.preventDefault();
                event.stopPropagation();
                setIsUserMenuOpen(value => !value);
              }}
              aria-label="更多操作"
            >
              <MoreVertical className="h-4 w-4" />
            </button>
            {isUserMenuOpen && (
              <div
                className="absolute right-0 top-8 z-20 min-w-28 rounded-md border border-border bg-background p-1 shadow-md"
                onClick={event => event.stopPropagation()}
              >
                {isCurrentUser === false && (
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
                    onClick={handleOpenReport}
                  >
                    <Flag className="h-3.5 w-3.5" />
                    举报
                  </button>
                )}
                {isCurrentUser && (
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
                    onClick={handleLogout}
                  >
                    登出
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
      {reportOpen && (
        <ReportUserDialog
          username={user.username}
          reason={reportReason}
          error={reportError}
          saving={createReport.isPending}
          onReasonChange={setReportReason}
          onClose={() => setReportOpen(false)}
          onSubmit={handleSubmitReport}
        />
      )}
      {/* 用户帖子列表 - 包含在大容器中 */}
      <div className="overflow-hidden rounded-lg bg-white p-0 shadow-sm">
        <h2 className="text-lg font-semibold px-3 pt-3">
          {isCurrentUser ? '我的帖子' : `${user.username} 的帖子`}
        </h2>

        {isFeedLoading ? (
          <div className="divide-y divide-border/50">
            <PostCardSkeleton />
            <PostCardSkeleton />
          </div>
        ) : posts.length > 0 ? (
          <div className="divide-y divide-border/50">
            {posts.map(post => (
              <PostCard key={post.id} post={post} />
            ))}
          </div>
        ) : (
          <div className="text-center py-10 text-muted-foreground">暂无帖子</div>
        )}

        {/* 加载更多 */}
        <div ref={loadMoreRef} className="py-3 text-center border-t border-border/50">
          {isFetchingNextPage && (
            <div className="flex items-center justify-center gap-2 text-muted-foreground">
              <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
              加载中...
            </div>
          )}
          {!hasNextPage && posts.length > 0 && (
            <span className="text-muted-foreground text-sm">没有更多内容了</span>
          )}
        </div>
      </div>
    </div>
  );
}

function ReportUserDialog({
  username,
  reason,
  error,
  saving,
  onReasonChange,
  onClose,
  onSubmit,
}: {
  username: string;
  reason: string;
  error: string;
  saving: boolean;
  onReasonChange: (value: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  return (
    <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-lg bg-background p-5 shadow-xl">
        <div>
          <h2 className="text-lg font-semibold">举报用户</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            @{username} 的资料和最近内容会进入管理端审查。
          </p>
        </div>
        <Textarea
          value={reason}
          onChange={event => onReasonChange(event.target.value)}
          placeholder="填写举报原因"
          className="mt-4 min-h-28"
          maxLength={1000}
        />
        {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" className="rounded-md" onClick={onClose} disabled={saving}>
            取消
          </Button>
          <Button className="rounded-md" onClick={onSubmit} disabled={saving || !reason.trim()}>
            {saving ? '提交中...' : '提交举报'}
          </Button>
        </div>
      </div>
    </div>
  );
}

/**
 * 用户资料骨架屏
 */
function ProfileSkeleton() {
  return (
    <div className="space-y-4">
      <div className="rounded-lg bg-white shadow-sm p-5">
        <div className="flex items-center gap-4">
          <Skeleton className="h-16 w-16 rounded-full" />
          <div className="flex-1 space-y-3">
            <Skeleton className="h-8 w-32" />
            <Skeleton className="h-4 w-24" />
            <div className="flex gap-4">
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-16" />
            </div>
          </div>
        </div>
      </div>
      <PostCardSkeleton />
      <PostCardSkeleton />
    </div>
  );
}

/**
 * 帖子卡片骨架屏
 */
function PostCardSkeleton() {
  return (
    <div className="space-y-4 rounded-lg bg-card p-3 sm:p-4">
      <div className="flex items-center gap-3">
        <Skeleton className="h-10 w-10 rounded-full" />
        <div className="space-y-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-3 w-16" />
        </div>
      </div>
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-3/4" />
    </div>
  );
}
