import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Ban, Search, ShieldAlert } from 'lucide-react';
import { adminApi, adminKeys, type UserModerationUpdateRequest, type UserWithModeration } from '@/features/admin';
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Textarea } from '@/shared/components/ui';

function toDateTimeLocal(value: string | null) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function fromDateTimeLocal(value: string) {
  return value ? new Date(value).toISOString() : null;
}

export default function AdminUsersPage() {
  const [keyword, setKeyword] = useState('');
  const [selected, setSelected] = useState<UserWithModeration | null>(null);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: adminKeys.users(keyword),
    queryFn: () => adminApi.users({ skip: 0, limit: 80, keyword: keyword.trim() || undefined }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ userId, payload }: { userId: number; payload: UserModerationUpdateRequest }) =>
      adminApi.updateUserModeration(userId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      setSelected(null);
    },
  });

  return (
    <div>
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold">用户管理</h1>
        <div className="relative w-full sm:w-72">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="搜索用户名或邮箱"
            className="pl-8"
          />
        </div>
      </div>

      <Card className="rounded-lg">
        <CardContent className="p-0">
          <div className="overflow-auto">
            <table className="w-full min-w-[920px] text-sm">
              <thead className="border-b bg-muted/50 text-left text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">用户</th>
                  <th className="px-4 py-3 font-medium">类型</th>
                  <th className="px-4 py-3 font-medium">内容</th>
                  <th className="px-4 py-3 font-medium">关系</th>
                  <th className="px-4 py-3 font-medium">状态</th>
                  <th className="px-4 py-3 font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((user) => (
                  <tr key={user.id} className="border-b last:border-0">
                    <td className="px-4 py-3">
                      <p className="font-medium">@{user.username || `user_${user.id}`}</p>
                      <p className="text-xs text-muted-foreground">{user.email || `ID ${user.id}`}</p>
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
                        onClick={() => setSelected(user)}
                      >
                        <ShieldAlert size={14} className="mr-1" />
                        管理
                      </Button>
                    </td>
                  </tr>
                ))}
                {!isLoading && (!data?.items || data.items.length === 0) && (
                  <tr>
                    <td className="px-4 py-10 text-center text-muted-foreground" colSpan={6}>
                      暂无用户
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {selected && (
        <ModerationEditor
          user={selected}
          saving={updateMutation.isPending}
          onClose={() => setSelected(null)}
          onSubmit={(payload) => updateMutation.mutate({ userId: selected.id, payload })}
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
  onClose,
  onSubmit,
}: {
  user: UserWithModeration;
  saving: boolean;
  onClose: () => void;
  onSubmit: (payload: UserModerationUpdateRequest) => void;
}) {
  const [accountBanned, setAccountBanned] = useState(user.moderation.account_banned);
  const [reason, setReason] = useState(user.moderation.account_ban_reason || '');
  const [publishUntil, setPublishUntil] = useState(toDateTimeLocal(user.moderation.publish_banned_until));
  const [commentUntil, setCommentUntil] = useState(toDateTimeLocal(user.moderation.comment_banned_until));
  const [interactionUntil, setInteractionUntil] = useState(
    toDateTimeLocal(user.moderation.interaction_banned_until)
  );

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
            <DateField label="禁止发布到" value={publishUntil} onChange={setPublishUntil} />
            <DateField label="禁止评论到" value={commentUntil} onChange={setCommentUntil} />
            <DateField label="禁止互动到" value={interactionUntil} onChange={setInteractionUntil} />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" className="rounded-md" onClick={onClose} disabled={saving}>
              取消
            </Button>
            <Button
              className="rounded-md"
              disabled={saving}
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

function DateField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="space-y-2 text-sm">
      <span className="font-medium">{label}</span>
      <Input type="datetime-local" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}
