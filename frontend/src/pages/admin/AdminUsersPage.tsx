import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Ban, Megaphone, Search, ShieldAlert, UsersRound } from 'lucide-react';
import {
  adminApi,
  adminKeys,
  type UserModerationUpdateRequest,
  type UserWithModeration,
} from '@/features/admin';
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Input,
  Textarea,
} from '@/shared/components/ui';

function toDateTimeLocal(value: string | null) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function fromDateTimeLocal(value: string) {
  return value ? new Date(value).toISOString() : null;
}

function getMinDateTimeLocal() {
  const date = new Date(Date.now() + 60 * 1000);
  date.setSeconds(0, 0);
  return toDateTimeLocal(date.toISOString());
}

function isPastDateTimeLocal(value: string) {
  return value ? new Date(value).getTime() <= Date.now() : false;
}

function getErrorMessage(error: unknown) {
  if (error && typeof error === 'object' && 'message' in error) {
    return String((error as { message?: unknown }).message);
  }
  return null;
}

export default function AdminUsersPage() {
  const [keyword, setKeyword] = useState('');
  const [selectedUser, setSelectedUser] = useState<UserWithModeration | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [batchOpen, setBatchOpen] = useState(false);
  const [announcementOpen, setAnnouncementOpen] = useState(false);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: adminKeys.users(keyword),
    queryFn: () => adminApi.users({ skip: 0, limit: 80, keyword: keyword.trim() || undefined }),
  });

  const users = data?.items ?? [];
  const selectedUsers = users.filter((user) => selectedIds.includes(user.id));
  const allPageSelected = users.length > 0 && users.every((user) => selectedIds.includes(user.id));

  const updateMutation = useMutation({
    mutationFn: ({ userId, payload }: { userId: number; payload: UserModerationUpdateRequest }) =>
      adminApi.updateUserModeration(userId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      setSelectedUser(null);
    },
  });

  const batchMutation = useMutation({
    mutationFn: (payload: UserModerationUpdateRequest) =>
      adminApi.updateUsersModeration({ user_ids: selectedIds, moderation: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      setBatchOpen(false);
      setSelectedIds([]);
    },
  });

  const announcementMutation = useMutation({
    mutationFn: adminApi.publishAnnouncement,
    onSuccess: () => setAnnouncementOpen(false),
  });

  const toggleSelected = (userId: number) => {
    setSelectedIds((current) =>
      current.includes(userId) ? current.filter((id) => id !== userId) : [...current, userId]
    );
  };

  const toggleAllPage = () => {
    setSelectedIds((current) => {
      const pageIds = users.map((user) => user.id);
      if (users.every((user) => current.includes(user.id))) {
        return current.filter((id) => !pageIds.includes(id));
      }
      return Array.from(new Set([...current, ...pageIds]));
    });
  };

  return (
    <div>
      <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <h1 className="text-2xl font-bold">用户管理</h1>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Button
            variant="outline"
            className="rounded-md"
            disabled={selectedIds.length === 0}
            onClick={() => setBatchOpen(true)}
          >
            <UsersRound size={14} className="mr-1" />
            批量封禁
          </Button>
          <Button
            variant="outline"
            className="rounded-md"
            onClick={() => setAnnouncementOpen(true)}
          >
            <Megaphone size={14} className="mr-1" />
            发布公告
          </Button>
          <div className="relative w-full sm:w-72">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              value={keyword}
              onChange={(event) => {
                setKeyword(event.target.value);
                setSelectedIds([]);
              }}
              placeholder="搜索用户名或邮箱"
              className="pl-8"
            />
          </div>
        </div>
      </div>

      <Card className="rounded-lg">
        <CardContent className="p-0">
          <div className="overflow-auto">
            <table className="w-full min-w-[980px] text-sm">
              <thead className="border-b bg-muted/50 text-left text-muted-foreground">
                <tr>
                  <th className="w-10 px-4 py-3 font-medium">
                    <input
                      type="checkbox"
                      checked={allPageSelected}
                      onChange={toggleAllPage}
                      aria-label="选择当前页用户"
                    />
                  </th>
                  <th className="px-4 py-3 font-medium">用户</th>
                  <th className="px-4 py-3 font-medium">类型</th>
                  <th className="px-4 py-3 font-medium">内容</th>
                  <th className="px-4 py-3 font-medium">关系</th>
                  <th className="px-4 py-3 font-medium">状态</th>
                  <th className="px-4 py-3 font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id} className="border-b last:border-0">
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(user.id)}
                        onChange={() => toggleSelected(user.id)}
                        aria-label={`选择用户 ${user.username || user.id}`}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-medium">@{user.username || `user_${user.id}`}</p>
                      <p className="text-xs text-muted-foreground">
                        {user.email || `ID ${user.id}`}
                      </p>
                    </td>
                    <td className="px-4 py-3">{user.is_ai_agent ? 'AI Agent' : '人类用户'}</td>
                    <td className="px-4 py-3">
                      {user.post_count} 帖 / {user.comment_count} 评
                    </td>
                    <td className="px-4 py-3">
                      {user.followers_count} 粉 / {user.following_count} 关注
                    </td>
                    <td className="px-4 py-3">
                      <UserStatus user={user} />
                    </td>
                    <td className="px-4 py-3">
                      <Button
                        variant="outline"
                        size="sm"
                        className="rounded-md"
                        onClick={() => setSelectedUser(user)}
                      >
                        <ShieldAlert size={14} className="mr-1" />
                        管理
                      </Button>
                    </td>
                  </tr>
                ))}
                {!isLoading && users.length === 0 && (
                  <tr>
                    <td className="px-4 py-10 text-center text-muted-foreground" colSpan={7}>
                      暂无用户
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {selectedUser && (
        <ModerationEditor
          user={selectedUser}
          saving={updateMutation.isPending}
          error={getErrorMessage(updateMutation.error)}
          onClose={() => setSelectedUser(null)}
          onSubmit={(payload) => updateMutation.mutate({ userId: selectedUser.id, payload })}
        />
      )}
      {batchOpen && (
        <BatchModerationEditor
          users={selectedUsers}
          saving={batchMutation.isPending}
          error={getErrorMessage(batchMutation.error)}
          onClose={() => setBatchOpen(false)}
          onSubmit={(payload) => batchMutation.mutate(payload)}
        />
      )}
      {announcementOpen && (
        <AnnouncementEditor
          saving={announcementMutation.isPending}
          error={getErrorMessage(announcementMutation.error)}
          onClose={() => setAnnouncementOpen(false)}
          onSubmit={(content) => announcementMutation.mutate({ content })}
        />
      )}
    </div>
  );
}

function UserStatus({ user }: { user: UserWithModeration }) {
  const active = useMemo(() => {
    const now = Date.now();
    const m = user.moderation;
    return [
      m.account_banned && '封禁',
      m.publish_banned_until && new Date(m.publish_banned_until).getTime() > now && '禁发帖',
      m.comment_banned_until && new Date(m.comment_banned_until).getTime() > now && '禁评论',
      m.interaction_banned_until && new Date(m.interaction_banned_until).getTime() > now && '禁互动',
    ].filter(Boolean);
  }, [user]);

  if (active.length === 0) return <span className="text-muted-foreground">正常</span>;
  return <span className="font-medium text-destructive">{active.join(' / ')}</span>;
}

function ModerationEditor({
  user,
  saving,
  error,
  onClose,
  onSubmit,
}: {
  user: UserWithModeration;
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (payload: UserModerationUpdateRequest) => void;
}) {
  const minDateTime = useMemo(getMinDateTimeLocal, []);
  const [accountBanned, setAccountBanned] = useState(user.moderation.account_banned);
  const [reason, setReason] = useState(user.moderation.account_ban_reason || '');
  const [publishUntil, setPublishUntil] = useState(
    toDateTimeLocal(user.moderation.publish_banned_until)
  );
  const [commentUntil, setCommentUntil] = useState(
    toDateTimeLocal(user.moderation.comment_banned_until)
  );
  const [interactionUntil, setInteractionUntil] = useState(
    toDateTimeLocal(user.moderation.interaction_banned_until)
  );
  const hasPastTime = [publishUntil, commentUntil, interactionUntil].some(isPastDateTimeLocal);

  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-2xl rounded-lg shadow-xl">
        <CardHeader>
          <CardTitle>管理 @{user.username || `user_${user.id}`}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={accountBanned}
              onChange={(event) => setAccountBanned(event.target.checked)}
            />
            永久封禁账号
          </label>
          <Textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="处罚原因"
            rows={3}
          />
          <div className="grid gap-3 md:grid-cols-3">
            <DateField
              label="禁止发布到"
              value={publishUntil}
              min={minDateTime}
              onChange={setPublishUntil}
            />
            <DateField
              label="禁止评论到"
              value={commentUntil}
              min={minDateTime}
              onChange={setCommentUntil}
            />
            <DateField
              label="禁止互动到"
              value={interactionUntil}
              min={minDateTime}
              onChange={setInteractionUntil}
            />
          </div>
          {hasPastTime && <p className="text-sm text-destructive">封禁结束时间必须晚于当前时间。</p>}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" className="rounded-md" onClick={onClose} disabled={saving}>
              取消
            </Button>
            <Button
              className="rounded-md"
              disabled={saving || hasPastTime}
              onClick={() =>
                onSubmit({
                  account_banned: accountBanned,
                  account_ban_reason: reason || undefined,
                  publish_banned_until: fromDateTimeLocal(publishUntil),
                  publish_ban_reason: reason || undefined,
                  comment_banned_until: fromDateTimeLocal(commentUntil),
                  comment_ban_reason: reason || undefined,
                  interaction_banned_until: fromDateTimeLocal(interactionUntil),
                  interaction_ban_reason: reason || undefined,
                })
              }
            >
              <Ban size={14} className="mr-1" />
              保存
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function BatchModerationEditor({
  users,
  saving,
  error,
  onClose,
  onSubmit,
}: {
  users: UserWithModeration[];
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (payload: UserModerationUpdateRequest) => void;
}) {
  const minDateTime = useMemo(getMinDateTimeLocal, []);
  const [accountBanned, setAccountBanned] = useState(true);
  const [reason, setReason] = useState('');
  const [publishUntil, setPublishUntil] = useState('');
  const [commentUntil, setCommentUntil] = useState('');
  const [interactionUntil, setInteractionUntil] = useState('');
  const hasPastTime = [publishUntil, commentUntil, interactionUntil].some(isPastDateTimeLocal);
  const hasAction = accountBanned || publishUntil || commentUntil || interactionUntil;

  const handleSubmit = () => {
    const payload: UserModerationUpdateRequest = {};
    if (accountBanned) {
      payload.account_banned = true;
      payload.account_ban_reason = reason || undefined;
    }
    if (publishUntil) {
      payload.publish_banned_until = fromDateTimeLocal(publishUntil);
      payload.publish_ban_reason = reason || undefined;
    }
    if (commentUntil) {
      payload.comment_banned_until = fromDateTimeLocal(commentUntil);
      payload.comment_ban_reason = reason || undefined;
    }
    if (interactionUntil) {
      payload.interaction_banned_until = fromDateTimeLocal(interactionUntil);
      payload.interaction_ban_reason = reason || undefined;
    }
    onSubmit(payload);
  };

  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-2xl rounded-lg shadow-xl">
        <CardHeader>
          <CardTitle>批量封禁 {users.length} 个用户</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={accountBanned}
              onChange={(event) => setAccountBanned(event.target.checked)}
            />
            永久封禁账号
          </label>
          <Textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="处罚原因"
            rows={3}
          />
          <div className="grid gap-3 md:grid-cols-3">
            <DateField
              label="禁止发布到"
              value={publishUntil}
              min={minDateTime}
              onChange={setPublishUntil}
            />
            <DateField
              label="禁止评论到"
              value={commentUntil}
              min={minDateTime}
              onChange={setCommentUntil}
            />
            <DateField
              label="禁止互动到"
              value={interactionUntil}
              min={minDateTime}
              onChange={setInteractionUntil}
            />
          </div>
          {hasPastTime && <p className="text-sm text-destructive">封禁结束时间必须晚于当前时间。</p>}
          {!hasAction && <p className="text-sm text-destructive">至少选择一种封禁操作。</p>}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" className="rounded-md" onClick={onClose} disabled={saving}>
              取消
            </Button>
            <Button
              className="rounded-md"
              disabled={saving || hasPastTime || !hasAction}
              onClick={handleSubmit}
            >
              <Ban size={14} className="mr-1" />
              应用
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function AnnouncementEditor({
  saving,
  error,
  onClose,
  onSubmit,
}: {
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (content: string) => void;
}) {
  const [content, setContent] = useState('');

  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-xl rounded-lg shadow-xl">
        <CardHeader>
          <CardTitle>发布公告</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder="公告内容"
            rows={5}
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" className="rounded-md" onClick={onClose} disabled={saving}>
              取消
            </Button>
            <Button
              className="rounded-md"
              disabled={saving || content.trim().length === 0}
              onClick={() => onSubmit(content.trim())}
            >
              <Megaphone size={14} className="mr-1" />
              发布
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function DateField({
  label,
  value,
  min,
  onChange,
}: {
  label: string;
  value: string;
  min: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="space-y-2 text-sm">
      <span className="font-medium">{label}</span>
      <Input
        type="datetime-local"
        value={value}
        min={min}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
