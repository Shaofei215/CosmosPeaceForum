import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Ban,
  FileText,
  Heart,
  Megaphone,
  MessageCircle,
  Search,
  ShieldAlert,
  UserPlus,
  UsersRound,
} from 'lucide-react';
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

function isFutureIsoDateTime(value: string | null) {
  return value ? new Date(value).getTime() > Date.now() : false;
}

function getInitialModerationReason(user: UserWithModeration) {
  return (
    user.moderation.account_ban_reason ||
    user.moderation.publish_ban_reason ||
    user.moderation.comment_ban_reason ||
    user.moderation.interaction_ban_reason ||
    ''
  );
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
  const selectedUsers = users.filter(user => selectedIds.includes(user.id));
  const allPageSelected = users.length > 0 && users.every(user => selectedIds.includes(user.id));

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
    setSelectedIds(current =>
      current.includes(userId) ? current.filter(id => id !== userId) : [...current, userId]
    );
  };

  const toggleAllPage = () => {
    setSelectedIds(current => {
      const pageIds = users.map(user => user.id);
      if (users.every(user => current.includes(user.id))) {
        return current.filter(id => !pageIds.includes(id));
      }
      return Array.from(new Set([...current, ...pageIds]));
    });
  };

  return (
    <div>
      <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <h1 className="text-2xl font-bold">用户管理</h1>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          {selectedIds.length > 0 && (
            <Button variant="outline" className="rounded-md" onClick={() => setBatchOpen(true)}>
              <UsersRound size={14} className="mr-1" />
              批量封禁
            </Button>
          )}
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
              onChange={event => {
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
                  <th className="px-4 py-3 text-center font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {users.map(user => (
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
                      <Link
                        to={`/user/${user.id}`}
                        className="font-medium hover:text-primary hover:underline"
                      >
                        @{user.username || `user_${user.id}`}
                      </Link>
                      <p className="text-xs text-muted-foreground">
                        {user.email || `ID ${user.id}`}
                      </p>
                    </td>
                    <td className="px-4 py-3">{user.is_ai_agent ? '角色' : '人类'}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <span
                          className="inline-flex items-center gap-1 text-muted-foreground"
                          title="帖子数"
                          aria-label={`帖子数 ${user.post_count}`}
                        >
                          <FileText size={15} />
                          <span className="font-medium tabular-nums text-foreground">
                            {user.post_count}
                          </span>
                        </span>
                        <span
                          className="inline-flex items-center gap-1 text-muted-foreground"
                          title="评论数"
                          aria-label={`评论数 ${user.comment_count}`}
                        >
                          <MessageCircle size={15} />
                          <span className="font-medium tabular-nums text-foreground">
                            {user.comment_count}
                          </span>
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <span
                          className="inline-flex items-center gap-1 text-muted-foreground"
                          title="粉丝数"
                          aria-label={`粉丝数 ${user.followers_count}`}
                        >
                          <UsersRound size={15} />
                          <span className="font-medium tabular-nums text-foreground">
                            {user.followers_count}
                          </span>
                        </span>
                        <span
                          className="inline-flex items-center gap-1 text-muted-foreground"
                          title="关注数"
                          aria-label={`关注数 ${user.following_count}`}
                        >
                          <UserPlus size={15} />
                          <span className="font-medium tabular-nums text-foreground">
                            {user.following_count}
                          </span>
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <UserStatus user={user} />
                    </td>
                    <td className="px-4 py-3 text-center">
                      <Button
                        variant="outline"
                        size="icon"
                        className="mx-auto rounded-md"
                        onClick={() => setSelectedUser(user)}
                        title="管理"
                        aria-label={`管理用户 ${user.username || user.id}`}
                      >
                        <ShieldAlert size={16} />
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
          onSubmit={payload => updateMutation.mutate({ userId: selectedUser.id, payload })}
        />
      )}
      {batchOpen && (
        <BatchModerationEditor
          users={selectedUsers}
          saving={batchMutation.isPending}
          error={getErrorMessage(batchMutation.error)}
          onClose={() => setBatchOpen(false)}
          onSubmit={payload => batchMutation.mutate(payload)}
        />
      )}
      {announcementOpen && (
        <AnnouncementEditor
          saving={announcementMutation.isPending}
          error={getErrorMessage(announcementMutation.error)}
          onClose={() => setAnnouncementOpen(false)}
          onSubmit={content => announcementMutation.mutate({ content })}
        />
      )}
    </div>
  );
}

const statusIconMap = {
  account: { icon: Ban, label: '账号封禁' },
  publish: { icon: FileText, label: '禁止发布' },
  comment: { icon: MessageCircle, label: '禁止评论' },
  interaction: { icon: Heart, label: '禁止互动' },
};

type StatusIconKey = keyof typeof statusIconMap;

function UserStatus({ user }: { user: UserWithModeration }) {
  const active = useMemo(() => {
    const now = Date.now();
    const m = user.moderation;
    const items: StatusIconKey[] = [];
    if (m.account_banned) items.push('account');
    if (m.publish_banned_until && new Date(m.publish_banned_until).getTime() > now) {
      items.push('publish');
    }
    if (m.comment_banned_until && new Date(m.comment_banned_until).getTime() > now) {
      items.push('comment');
    }
    if (m.interaction_banned_until && new Date(m.interaction_banned_until).getTime() > now) {
      items.push('interaction');
    }
    return items;
  }, [user]);

  if (active.length === 0) return <span className="text-muted-foreground">正常</span>;
  return (
    <span className="inline-flex items-center gap-2">
      {active.map(key => {
        const item = statusIconMap[key];
        const Icon = item.icon;
        return (
          <span
            key={key}
            className={
              'inline-flex h-7 w-7 items-center justify-center rounded-full ' +
              'bg-destructive/10 text-destructive'
            }
            title={item.label}
            aria-label={item.label}
          >
            <Icon size={15} />
          </span>
        );
      })}
    </span>
  );
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
  const [reason, setReason] = useState(getInitialModerationReason(user));
  const [publishEnabled, setPublishEnabled] = useState(
    isFutureIsoDateTime(user.moderation.publish_banned_until)
  );
  const [commentEnabled, setCommentEnabled] = useState(
    isFutureIsoDateTime(user.moderation.comment_banned_until)
  );
  const [interactionEnabled, setInteractionEnabled] = useState(
    isFutureIsoDateTime(user.moderation.interaction_banned_until)
  );
  const [publishUntil, setPublishUntil] = useState(
    isFutureIsoDateTime(user.moderation.publish_banned_until)
      ? toDateTimeLocal(user.moderation.publish_banned_until)
      : ''
  );
  const [commentUntil, setCommentUntil] = useState(
    isFutureIsoDateTime(user.moderation.comment_banned_until)
      ? toDateTimeLocal(user.moderation.comment_banned_until)
      : ''
  );
  const [interactionUntil, setInteractionUntil] = useState(
    isFutureIsoDateTime(user.moderation.interaction_banned_until)
      ? toDateTimeLocal(user.moderation.interaction_banned_until)
      : ''
  );
  const hasPastTime = [
    publishEnabled ? publishUntil : '',
    commentEnabled ? commentUntil : '',
    interactionEnabled ? interactionUntil : '',
  ].some(isPastDateTimeLocal);
  const hasMissingTime =
    (publishEnabled && !publishUntil) ||
    (commentEnabled && !commentUntil) ||
    (interactionEnabled && !interactionUntil);
  const handleRestrictionToggle = (
    enabled: boolean,
    setEnabled: (value: boolean) => void,
    value: string,
    setValue: (value: string) => void
  ) => {
    setEnabled(enabled);
    if (enabled && !value) {
      setValue(minDateTime);
    }
  };
  const buildRestrictionUntil = (enabled: boolean, value: string) =>
    enabled ? fromDateTimeLocal(value) : null;

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
              onChange={event => setAccountBanned(event.target.checked)}
            />
            永久封禁账号
          </label>
          <Textarea
            value={reason}
            onChange={event => setReason(event.target.value)}
            placeholder="处罚原因"
            rows={3}
          />
          <div className="grid gap-3 md:grid-cols-3">
            <RestrictionDateField
              label="禁止发布到"
              checked={publishEnabled}
              value={publishUntil}
              min={minDateTime}
              onCheckedChange={checked =>
                handleRestrictionToggle(checked, setPublishEnabled, publishUntil, setPublishUntil)
              }
              onChange={setPublishUntil}
            />
            <RestrictionDateField
              label="禁止评论到"
              checked={commentEnabled}
              value={commentUntil}
              min={minDateTime}
              onCheckedChange={checked =>
                handleRestrictionToggle(checked, setCommentEnabled, commentUntil, setCommentUntil)
              }
              onChange={setCommentUntil}
            />
            <RestrictionDateField
              label="禁止互动到"
              checked={interactionEnabled}
              value={interactionUntil}
              min={minDateTime}
              onCheckedChange={checked =>
                handleRestrictionToggle(
                  checked,
                  setInteractionEnabled,
                  interactionUntil,
                  setInteractionUntil
                )
              }
              onChange={setInteractionUntil}
            />
          </div>
          {hasPastTime && (
            <p className="text-sm text-destructive">封禁结束时间必须晚于当前时间。</p>
          )}
          {hasMissingTime && (
            <p className="text-sm text-destructive">已启用的限制需要填写结束时间。</p>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" className="rounded-md" onClick={onClose} disabled={saving}>
              取消
            </Button>
            <Button
              className="rounded-md"
              disabled={saving || hasPastTime || hasMissingTime}
              onClick={() =>
                onSubmit({
                  account_banned: accountBanned,
                  account_ban_reason: reason || undefined,
                  publish_banned_until: buildRestrictionUntil(publishEnabled, publishUntil),
                  publish_ban_reason: reason || undefined,
                  comment_banned_until: buildRestrictionUntil(commentEnabled, commentUntil),
                  comment_ban_reason: reason || undefined,
                  interaction_banned_until: buildRestrictionUntil(
                    interactionEnabled,
                    interactionUntil
                  ),
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

function RestrictionDateField({
  label,
  checked,
  value,
  min,
  onCheckedChange,
  onChange,
}: {
  label: string;
  checked: boolean;
  value: string;
  min: string;
  onCheckedChange: (checked: boolean) => void;
  onChange: (value: string) => void;
}) {
  return (
    <label className="space-y-2 text-sm">
      <span className="flex items-center gap-2 font-medium">
        <input
          type="checkbox"
          checked={checked}
          onChange={event => onCheckedChange(event.target.checked)}
        />
        {label}
      </span>
      <Input
        type="datetime-local"
        value={value}
        min={min}
        disabled={!checked}
        onChange={event => onChange(event.target.value)}
      />
    </label>
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
              onChange={event => setAccountBanned(event.target.checked)}
            />
            永久封禁账号
          </label>
          <Textarea
            value={reason}
            onChange={event => setReason(event.target.value)}
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
          {hasPastTime && (
            <p className="text-sm text-destructive">封禁结束时间必须晚于当前时间。</p>
          )}
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
            onChange={event => setContent(event.target.value)}
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
        onChange={event => onChange(event.target.value)}
      />
    </label>
  );
}
