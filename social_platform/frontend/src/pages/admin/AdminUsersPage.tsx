import { useEffect, useMemo, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Ban,
  Bot,
  Braces,
  CheckCircle,
  FileText,
  Heart,
  KeyRound,
  Megaphone,
  MessageCircle,
  RotateCcw,
  Save,
  ScrollText,
  Search,
  ShieldAlert,
  UserPlus,
  UsersRound,
} from 'lucide-react';
import {
  adminApi,
  adminKeys,
  type ContentModerationLLMPromptConfig,
  type ContentModerationLLMSettings,
  type ContentModerationLLMSettingsUpdate,
  type InvitationCode,
  type InvitationCodeCreateRequest,
  type ModerationAppealItem,
  type ReportedUserItem,
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

function reportedUserToModerationUser(user: ReportedUserItem): UserWithModeration {
  return {
    id: user.id,
    username: user.username,
    email: null,
    bio: user.bio,
    avatar_url: user.avatar_url,
    is_ai_agent: user.is_ai_agent,
    ai_config_id: null,
    created_at: user.created_at,
    following_count: 0,
    followers_count: 0,
    post_count: 0,
    comment_count: 0,
    moderation: {
      account_banned: false,
      account_banned_at: null,
      account_ban_reason: null,
      publish_banned_until: null,
      publish_ban_reason: null,
      comment_banned_until: null,
      comment_ban_reason: null,
      interaction_banned_until: null,
      interaction_ban_reason: null,
      updated_at: null,
    },
  };
}

type UserMode = 'all' | 'reported' | 'appeals' | 'invite';

const userReportPromptPlaceholders = [
  {
    token: '{context_json}',
    description: '被举报用户、最近 5 条帖子、最近 5 条评论和触发审查内容 JSON。',
  },
];

function reportSettingsToForm(
  settings: ContentModerationLLMSettings
): ContentModerationLLMSettingsUpdate {
  return {
    enabled: settings.enabled,
    llm_base_url: settings.llm_base_url || '',
    llm_model_name: settings.llm_model_name || '',
    llm_api_key: settings.llm_api_key || '',
  };
}

function normalizeReportSettingsForm(
  form: ContentModerationLLMSettingsUpdate
): ContentModerationLLMSettingsUpdate {
  return {
    enabled: !!form.enabled,
    llm_base_url: form.llm_base_url || '',
    llm_model_name: form.llm_model_name || '',
    llm_api_key: form.llm_api_key || '',
  };
}

function reportSettingsFormsEqual(
  left: ContentModerationLLMSettingsUpdate,
  right: ContentModerationLLMSettingsUpdate
) {
  return (
    JSON.stringify(normalizeReportSettingsForm(left)) ===
    JSON.stringify(normalizeReportSettingsForm(right))
  );
}

export default function AdminUsersPage() {
  const [mode, setMode] = useState<UserMode>('all');
  const [keyword, setKeyword] = useState('');
  const [selectedUser, setSelectedUser] = useState<UserWithModeration | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [batchOpen, setBatchOpen] = useState(false);
  const [announcementOpen, setAnnouncementOpen] = useState(false);
  const [reportedModerationUser, setReportedModerationUser] = useState<ReportedUserItem | null>(
    null
  );
  const [appealModeration, setAppealModeration] = useState<{
    appeal: ModerationAppealItem;
    user: UserWithModeration;
  } | null>(null);
  const [rejectingAppeal, setRejectingAppeal] = useState<ModerationAppealItem | null>(null);
  const [releasingUserId, setReleasingUserId] = useState<number | null>(null);
  const [reportSettingsForm, setReportSettingsForm] = useState<ContentModerationLLMSettingsUpdate>(
    {}
  );
  const [reportPromptDraft, setReportPromptDraft] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: adminKeys.users(keyword),
    queryFn: () => adminApi.users({ skip: 0, limit: 80, keyword: keyword.trim() || undefined }),
    enabled: mode === 'all',
  });

  const reportedQuery = useQuery({
    queryKey: adminKeys.reportedUsers(keyword),
    queryFn: () =>
      adminApi.reportedUsers({ skip: 0, limit: 100, keyword: keyword.trim() || undefined }),
    enabled: mode === 'reported',
  });

  const moderatedQuery = useQuery({
    queryKey: adminKeys.moderatedUsers(keyword),
    queryFn: () =>
      adminApi.moderatedUsers({ skip: 0, limit: 100, keyword: keyword.trim() || undefined }),
    enabled: mode === 'reported' || mode === 'appeals',
  });

  const appealsQuery = useQuery({
    queryKey: adminKeys.userAppeals(keyword),
    queryFn: () =>
      adminApi.userAppeals({ skip: 0, limit: 100, keyword: keyword.trim() || undefined }),
    enabled: mode === 'appeals',
  });

  const invitationQuery = useQuery({
    queryKey: adminKeys.invitations(keyword),
    queryFn: () =>
      adminApi.invitations({ skip: 0, limit: 100, keyword: keyword.trim() || undefined }),
    enabled: mode === 'invite',
  });

  const { data: reportSettings } = useQuery({
    queryKey: adminKeys.userReportModerationSettings,
    queryFn: adminApi.userReportModerationSettings,
    enabled: mode === 'reported',
  });

  const { data: reportPromptConfig, isLoading: isReportPromptLoading } = useQuery({
    queryKey: adminKeys.userReportModerationPrompt,
    queryFn: adminApi.userReportModerationPrompt,
    enabled: mode === 'reported',
  });

  const users = data?.items ?? [];
  const reportedUsers = reportedQuery.data?.items ?? [];
  const moderatedUsers = moderatedQuery.data?.items ?? [];
  const appealItems = appealsQuery.data?.items ?? [];
  const invitations = invitationQuery.data?.items ?? [];
  const selectedUsers = users.filter(user => selectedIds.includes(user.id));
  const allPageSelected = users.length > 0 && users.every(user => selectedIds.includes(user.id));
  const reportPromptValue = reportPromptDraft ?? reportPromptConfig?.value ?? '';
  const isReportPromptDirty =
    !!reportPromptConfig && reportPromptValue !== reportPromptConfig.value;
  const reportSettingsDirty = useMemo(() => {
    if (!reportSettings) return false;
    return !reportSettingsFormsEqual(reportSettingsForm, reportSettingsToForm(reportSettings));
  }, [reportSettings, reportSettingsForm]);

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

  const createInvitationMutation = useMutation({
    mutationFn: (payload: InvitationCodeCreateRequest) => adminApi.createInvitation(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users', 'invitations'] });
    },
  });

  const releaseReportedUserMutation = useMutation({
    mutationFn: (user: ReportedUserItem) => adminApi.releaseReportedUser(user.id),
    onMutate: user => setReleasingUserId(user.id),
    onSettled: () => setReleasingUserId(null),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users', 'reports'] });
    },
  });

  const moderateReportedUserMutation = useMutation({
    mutationFn: ({
      user,
      payload,
    }: {
      user: ReportedUserItem;
      payload: UserModerationUpdateRequest;
    }) => adminApi.moderateReportedUser(user.id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      setReportedModerationUser(null);
    },
  });

  const approveAppealWithModerationMutation = useMutation({
    mutationFn: async ({
      appeal,
      payload,
    }: {
      appeal: ModerationAppealItem;
      payload: UserModerationUpdateRequest;
    }) => {
      await adminApi.updateUserModeration(appeal.target_id, payload);
      await adminApi.approveUserAppeal(appeal.id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      setAppealModeration(null);
    },
  });

  const rejectAppealMutation = useMutation({
    mutationFn: ({ appeal, reason }: { appeal: ModerationAppealItem; reason: string }) =>
      adminApi.rejectUserAppeal(appeal.id, { reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      setRejectingAppeal(null);
    },
  });

  const saveReportSettingsMutation = useMutation({
    mutationFn: adminApi.updateUserReportModerationSettings,
    onSuccess: nextSettings => {
      queryClient.setQueryData(adminKeys.userReportModerationSettings, nextSettings);
    },
  });

  const updateReportPromptMutation = useMutation({
    mutationFn: (value: string) => adminApi.updateUserReportModerationPrompt(value),
    onSuccess: updated => {
      setReportPromptDraft(updated.value);
      queryClient.setQueryData(adminKeys.userReportModerationPrompt, updated);
    },
  });

  const resetReportPromptMutation = useMutation({
    mutationFn: adminApi.resetUserReportModerationPrompt,
    onSuccess: updated => {
      setReportPromptDraft(updated.value);
      queryClient.setQueryData(adminKeys.userReportModerationPrompt, updated);
    },
  });

  useEffect(() => {
    if (reportSettings) {
      setReportSettingsForm(reportSettingsToForm(reportSettings));
    }
  }, [reportSettings]);

  useEffect(() => {
    if (reportPromptConfig && reportPromptDraft === null) {
      setReportPromptDraft(reportPromptConfig.value);
    }
  }, [reportPromptConfig, reportPromptDraft]);

  useEffect(() => {
    if (!reportSettings || saveReportSettingsMutation.isPending) return;
    const current = normalizeReportSettingsForm(reportSettingsForm);
    const persisted = reportSettingsToForm(reportSettings);
    if (reportSettingsFormsEqual(current, persisted)) return;

    const timeoutId = window.setTimeout(() => {
      saveReportSettingsMutation.mutate(current);
    }, 700);

    return () => window.clearTimeout(timeoutId);
  }, [reportSettings, reportSettingsForm, saveReportSettingsMutation]);

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

  const switchMode = (nextMode: UserMode) => {
    setMode(nextMode);
    setSelectedIds([]);
  };

  return (
    <div>
      <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold">用户管理</h1>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              variant={mode === 'all' ? 'default' : 'outline'}
              size="sm"
              className="rounded-md"
              onClick={() => switchMode('all')}
            >
              <UsersRound size={14} className="mr-1" />
              全部用户
            </Button>
            <Button
              variant={mode === 'reported' ? 'default' : 'outline'}
              size="sm"
              className="rounded-md"
              onClick={() => switchMode('reported')}
            >
              <ShieldAlert size={14} className="mr-1" />
              被举报用户审查
            </Button>
            <Button
              variant={mode === 'appeals' ? 'default' : 'outline'}
              size="sm"
              className="rounded-md"
              onClick={() => switchMode('appeals')}
            >
              <ShieldAlert size={14} className="mr-1" />
              申诉处理
            </Button>
            <Button
              variant={mode === 'invite' ? 'default' : 'outline'}
              size="sm"
              className="rounded-md"
              onClick={() => switchMode('invite')}
            >
              <KeyRound size={14} className="mr-1" />
              邀请码
            </Button>
          </div>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          {mode === 'all' && selectedIds.length > 0 && (
            <Button variant="outline" className="rounded-md" onClick={() => setBatchOpen(true)}>
              <UsersRound size={14} className="mr-1" />
              批量封禁
            </Button>
          )}
          {mode === 'all' && (
            <Button
              variant="outline"
              className="rounded-md"
              onClick={() => setAnnouncementOpen(true)}
            >
              <Megaphone size={14} className="mr-1" />
              发布公告
            </Button>
          )}
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
              placeholder={
                mode === 'reported'
                  ? '搜索被举报用户'
                  : mode === 'appeals'
                    ? '搜索申诉'
                    : mode === 'invite'
                      ? '搜索邮箱、邀请码或使用人'
                      : '搜索用户名或邮箱'
              }
              className="pl-8"
            />
          </div>
        </div>
      </div>

      {mode === 'all' ? (
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
                            title="被关注数"
                            aria-label={`被关注数 ${user.followers_count}`}
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
      ) : mode === 'reported' ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px] xl:items-start">
          <div className="space-y-4">
            <ReportedUsersTable
              items={reportedUsers}
              releasingUserId={releasingUserId}
              releasePending={releaseReportedUserMutation.isPending}
              onRelease={user => releaseReportedUserMutation.mutate(user)}
              onManage={setReportedModerationUser}
            />
            <ModeratedUsersTable items={moderatedUsers} onManage={setSelectedUser} />
          </div>
          <UserReportModerationLLMPanel
            settingsForm={reportSettingsForm}
            settingsDirty={reportSettingsDirty}
            settingsSaving={saveReportSettingsMutation.isPending}
            prompt={reportPromptConfig}
            promptDraft={reportPromptValue}
            promptLoading={isReportPromptLoading}
            promptDirty={isReportPromptDirty}
            promptSaving={updateReportPromptMutation.isPending}
            promptResetting={resetReportPromptMutation.isPending}
            onSettingsChange={setReportSettingsForm}
            onPromptDraftChange={setReportPromptDraft}
            onPromptCancel={() => setReportPromptDraft(reportPromptConfig?.value ?? '')}
            onPromptReset={() => resetReportPromptMutation.mutate()}
            onPromptSave={() => updateReportPromptMutation.mutate(reportPromptValue)}
          />
        </div>
      ) : mode === 'appeals' ? (
        <UserAppealsTable
          items={appealItems}
          moderatedUsers={moderatedUsers}
          onOpenModerated={() => switchMode('reported')}
          onManage={(appeal, user) => setAppealModeration({ appeal, user })}
          onReject={setRejectingAppeal}
        />
      ) : (
        <InvitationCodesPanel
          items={invitations}
          loading={invitationQuery.isLoading}
          creating={createInvitationMutation.isPending}
          error={getErrorMessage(createInvitationMutation.error)}
          onCreate={payload => createInvitationMutation.mutate(payload)}
        />
      )}

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
      {reportedModerationUser && (
        <ModerationEditor
          user={reportedUserToModerationUser(reportedModerationUser)}
          saving={moderateReportedUserMutation.isPending}
          error={getErrorMessage(moderateReportedUserMutation.error)}
          onClose={() => setReportedModerationUser(null)}
          onSubmit={payload =>
            moderateReportedUserMutation.mutate({ user: reportedModerationUser, payload })
          }
        />
      )}
      {appealModeration && (
        <ModerationEditor
          user={appealModeration.user}
          saving={approveAppealWithModerationMutation.isPending}
          error={getErrorMessage(approveAppealWithModerationMutation.error)}
          onClose={() => setAppealModeration(null)}
          onSubmit={payload =>
            approveAppealWithModerationMutation.mutate({
              appeal: appealModeration.appeal,
              payload,
            })
          }
        />
      )}
      {rejectingAppeal && (
        <RejectAppealDialog
          saving={rejectAppealMutation.isPending}
          onClose={() => setRejectingAppeal(null)}
          onConfirm={reason => rejectAppealMutation.mutate({ appeal: rejectingAppeal, reason })}
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

function InvitationCodesPanel({
  items,
  loading,
  creating,
  error,
  onCreate,
}: {
  items: InvitationCode[];
  loading: boolean;
  creating: boolean;
  error: string | null;
  onCreate: (payload: InvitationCodeCreateRequest) => void;
}) {
  const [email, setEmail] = useState('');
  const [prefix, setPrefix] = useState('');
  const [formError, setFormError] = useState('');

  const handleCreate = (event: FormEvent) => {
    event.preventDefault();
    setFormError('');
    const normalizedEmail = email.trim();
    if (!normalizedEmail) {
      setFormError('请输入邮箱');
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)) {
      setFormError('请输入有效的邮箱地址');
      return;
    }
    onCreate({ email: normalizedEmail, prefix: prefix.trim() });
  };

  return (
    <div className="space-y-4">
      <Card className="rounded-lg">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <KeyRound size={17} className="text-primary" />
            生成邀请码
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px_auto]"
            onSubmit={handleCreate}
          >
            <Input
              value={email}
              onChange={event => setEmail(event.target.value)}
              placeholder="绑定邮箱"
              type="email"
              disabled={creating}
              className="shadow-none"
            />
            <Input
              value={prefix}
              onChange={event =>
                setPrefix(
                  event.target.value
                    .replace(/[^A-Za-z0-9_-]/g, '')
                    .toUpperCase()
                    .slice(0, 16)
                )
              }
              placeholder="前缀，可留空"
              disabled={creating}
              maxLength={16}
              className="shadow-none"
            />
            <Button type="submit" className="rounded-md shadow-none" disabled={creating}>
              <KeyRound size={14} className="mr-1" />
              {creating ? '生成中...' : '生成'}
            </Button>
          </form>
          {(formError || error) && (
            <div className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
              {formError || error}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="rounded-lg">
        <CardContent className="p-0">
          <div className="overflow-auto">
            <table className="w-full min-w-[980px] text-sm">
              <thead className="border-b bg-muted/50 text-left text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">邮箱</th>
                  <th className="px-4 py-3 font-medium">邀请码</th>
                  <th className="px-4 py-3 font-medium">状态</th>
                  <th className="px-4 py-3 font-medium">使用用户</th>
                  <th className="px-4 py-3 font-medium">创建人</th>
                  <th className="px-4 py-3 font-medium">时间</th>
                </tr>
              </thead>
              <tbody>
                {items.map(invitation => (
                  <tr key={invitation.id} className="border-b last:border-0">
                    <td className="px-4 py-3">{invitation.email}</td>
                    <td className="px-4 py-3">
                      <span className="rounded-md bg-muted px-2 py-1 font-mono text-xs font-semibold tracking-normal">
                        {invitation.code}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={
                          invitation.status === 'used'
                            ? 'rounded-md bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700'
                            : 'rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground'
                        }
                      >
                        {invitation.status === 'used' ? '已使用' : '未使用'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {invitation.used_by_user_id ? (
                        <Link
                          to={`/user/${invitation.used_by_user_id}`}
                          className="font-medium hover:text-primary hover:underline"
                        >
                          @{invitation.used_by_username || `user_${invitation.used_by_user_id}`}
                        </Link>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {invitation.created_by_admin_username || (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div>{new Date(invitation.created_at).toLocaleString()}</div>
                      {invitation.used_at && (
                        <div className="text-xs text-muted-foreground">
                          使用于 {new Date(invitation.used_at).toLocaleString()}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
                {!loading && items.length === 0 && (
                  <tr>
                    <td className="px-4 py-10 text-center text-muted-foreground" colSpan={6}>
                      暂无邀请码
                    </td>
                  </tr>
                )}
                {loading && (
                  <tr>
                    <td className="px-4 py-10 text-center text-muted-foreground" colSpan={6}>
                      加载中...
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function appealToModerationUser(
  appeal: ModerationAppealItem,
  moderatedUsers: UserWithModeration[]
): UserWithModeration {
  const existing = moderatedUsers.find(user => user.id === appeal.target_id);
  if (existing) return existing;
  return {
    id: appeal.target_id,
    username: appeal.target_label.replace(/^@/, ''),
    email: null,
    bio: appeal.target_content,
    avatar_url: null,
    is_ai_agent: false,
    ai_config_id: null,
    created_at: appeal.created_at,
    following_count: 0,
    followers_count: 0,
    post_count: 0,
    comment_count: 0,
    moderation: {
      account_banned: true,
      account_banned_at: appeal.created_at,
      account_ban_reason: appeal.moderation_reason,
      publish_banned_until: null,
      publish_ban_reason: null,
      comment_banned_until: null,
      comment_ban_reason: null,
      interaction_banned_until: null,
      interaction_ban_reason: null,
      updated_at: appeal.updated_at,
    },
  };
}

function UserAppealsTable({
  items,
  moderatedUsers,
  onOpenModerated,
  onManage,
  onReject,
}: {
  items: ModerationAppealItem[];
  moderatedUsers: UserWithModeration[];
  onOpenModerated: () => void;
  onManage: (appeal: ModerationAppealItem, user: UserWithModeration) => void;
  onReject: (appeal: ModerationAppealItem) => void;
}) {
  return (
    <Card className="rounded-lg">
      <CardContent className="p-0">
        <div className="overflow-auto">
          <table className="w-full min-w-[1120px] text-sm">
            <thead className="border-b bg-muted/50 text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">申诉人</th>
                <th className="px-4 py-3 font-medium">用户</th>
                <th className="px-4 py-3 font-medium">处理操作</th>
                <th className="px-4 py-3 font-medium">处理理由</th>
                <th className="px-4 py-3 font-medium">申诉理由</th>
                <th className="px-4 py-3 text-center font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => {
                const user = appealToModerationUser(item, moderatedUsers);
                return (
                  <tr key={item.id} className="border-b last:border-0">
                    <td className="px-4 py-3">
                      <Link
                        to={`/user/${item.appellant_id}`}
                        className="font-medium hover:text-primary hover:underline"
                      >
                        @{item.appellant_username || `user_${item.appellant_id}`}
                      </Link>
                    </td>
                    <td className="max-w-sm px-4 py-3">
                      <Link
                        to={`/user/${item.target_id}`}
                        className="font-medium hover:text-primary hover:underline"
                      >
                        {item.target_label}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        className="font-medium text-primary hover:underline"
                        onClick={onOpenModerated}
                      >
                        {item.action_label}
                      </button>
                    </td>
                    <td className="max-w-sm px-4 py-3 text-muted-foreground">
                      <p className="line-clamp-3 break-words">
                        {item.moderation_reason || '未填写'}
                      </p>
                    </td>
                    <td className="max-w-sm px-4 py-3 text-muted-foreground">
                      <p className="line-clamp-3 break-words">{item.appeal_reason}</p>
                      <p className="mt-1 text-xs">{new Date(item.updated_at).toLocaleString()}</p>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="rounded-md gap-1"
                          onClick={() => onManage(item, user)}
                        >
                          <ShieldAlert size={14} />
                          处理
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          className="rounded-md"
                          onClick={() => onReject(item)}
                        >
                          拒绝
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
              {items.length === 0 && (
                <tr>
                  <td className="px-4 py-10 text-center text-muted-foreground" colSpan={6}>
                    暂无待处理申诉
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function RejectAppealDialog({
  saving,
  onClose,
  onConfirm,
}: {
  saving: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState('');

  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-lg rounded-lg shadow-xl">
        <CardContent className="space-y-4 p-4">
          <h3 className="text-base font-semibold">拒绝申诉</h3>
          <Textarea
            value={reason}
            onChange={event => setReason(event.target.value)}
            rows={5}
            maxLength={1000}
            placeholder="填写拒绝原因"
          />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              取消
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={!reason.trim() || saving}
              onClick={() => onConfirm(reason.trim())}
            >
              拒绝
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function ReportedUsersTable({
  items,
  releasingUserId,
  releasePending,
  onRelease,
  onManage,
}: {
  items: ReportedUserItem[];
  releasingUserId: number | null;
  releasePending: boolean;
  onRelease: (user: ReportedUserItem) => void;
  onManage: (user: ReportedUserItem) => void;
}) {
  return (
    <Card className="rounded-lg">
      <CardContent className="p-0">
        <div className="overflow-auto">
          <table className="w-full min-w-[980px] text-sm">
            <thead className="border-b bg-muted/50 text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">用户</th>
                <th className="px-4 py-3 font-medium">签名</th>
                <th className="px-4 py-3 font-medium">举报人数</th>
                <th className="px-4 py-3 font-medium">举报原因</th>
                <th className="px-4 py-3 font-medium">最近举报</th>
                <th className="px-4 py-3 text-center font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map(user => (
                <tr key={user.id} className="border-b last:border-0">
                  <td className="px-4 py-3">
                    <Link
                      to={`/user/${user.id}`}
                      className="font-medium hover:text-primary hover:underline"
                    >
                      @{user.username || `user_${user.id}`}
                    </Link>
                    <p className="text-xs text-muted-foreground">
                      {user.is_ai_agent ? '角色' : '人类'} · ID {user.id}
                    </p>
                  </td>
                  <td className="max-w-xs px-4 py-3 text-muted-foreground">
                    <p className="line-clamp-2 break-words">{user.bio || '无签名'}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center rounded-md bg-muted px-2 py-1 font-medium tabular-nums">
                      {user.report_count}
                    </span>
                  </td>
                  <td className="max-w-sm px-4 py-3">
                    <div className="space-y-1.5">
                      {user.report_reasons.map(reason => (
                        <div
                          key={reason.reason}
                          className="flex items-start gap-2 rounded-md bg-muted/40 px-2 py-1.5"
                        >
                          <span className="shrink-0 rounded bg-background px-1.5 py-0.5 text-xs tabular-nums text-muted-foreground">
                            {reason.count}
                          </span>
                          <span className="line-clamp-2 break-words text-muted-foreground">
                            {reason.reason}
                          </span>
                        </div>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">{new Date(user.last_reported_at).toLocaleString()}</td>
                  <td className="px-4 py-3">
                    <div className="flex justify-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="rounded-md gap-1"
                        onClick={() => onRelease(user)}
                        disabled={releasePending && releasingUserId === user.id}
                      >
                        <CheckCircle size={14} />
                        放行
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="rounded-md gap-1"
                        onClick={() => onManage(user)}
                      >
                        <ShieldAlert size={14} />
                        管理
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td className="px-4 py-10 text-center text-muted-foreground" colSpan={6}>
                    暂无待审举报用户
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function ModeratedUsersTable({
  items,
  onManage,
}: {
  items: UserWithModeration[];
  onManage: (user: UserWithModeration) => void;
}) {
  return (
    <Card className="rounded-lg">
      <CardContent className="p-0">
        <div className="border-b px-4 py-3">
          <div className="flex items-center gap-2 font-semibold">
            <Ban size={16} className="text-muted-foreground" />
            已管控用户
          </div>
        </div>
        <div className="overflow-auto">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="border-b bg-muted/50 text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">用户</th>
                <th className="px-4 py-3 font-medium">类型</th>
                <th className="px-4 py-3 font-medium">状态</th>
                <th className="px-4 py-3 font-medium">更新时间</th>
                <th className="px-4 py-3 text-center font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map(user => (
                <tr key={user.id} className="border-b last:border-0">
                  <td className="px-4 py-3">
                    <Link
                      to={`/user/${user.id}`}
                      className="font-medium hover:text-primary hover:underline"
                    >
                      @{user.username || `user_${user.id}`}
                    </Link>
                    <p className="text-xs text-muted-foreground">{user.email || `ID ${user.id}`}</p>
                  </td>
                  <td className="px-4 py-3">{user.is_ai_agent ? '角色' : '人类'}</td>
                  <td className="px-4 py-3">
                    <UserStatus user={user} />
                  </td>
                  <td className="px-4 py-3">
                    {user.moderation.updated_at
                      ? new Date(user.moderation.updated_at).toLocaleString()
                      : '-'}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <Button
                      variant="outline"
                      size="sm"
                      className="rounded-md gap-1"
                      onClick={() => onManage(user)}
                    >
                      <ShieldAlert size={14} />
                      管理
                    </Button>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td className="px-4 py-10 text-center text-muted-foreground" colSpan={5}>
                    暂无已管控用户
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function UserReportModerationLLMPanel({
  settingsForm,
  settingsDirty,
  settingsSaving,
  prompt,
  promptDraft,
  promptLoading,
  promptDirty,
  promptSaving,
  promptResetting,
  onSettingsChange,
  onPromptDraftChange,
  onPromptCancel,
  onPromptReset,
  onPromptSave,
}: {
  settingsForm: ContentModerationLLMSettingsUpdate;
  settingsDirty: boolean;
  settingsSaving: boolean;
  prompt?: ContentModerationLLMPromptConfig;
  promptDraft: string;
  promptLoading: boolean;
  promptDirty: boolean;
  promptSaving: boolean;
  promptResetting: boolean;
  onSettingsChange: (
    updater: (current: ContentModerationLLMSettingsUpdate) => ContentModerationLLMSettingsUpdate
  ) => void;
  onPromptDraftChange: (value: string) => void;
  onPromptCancel: () => void;
  onPromptReset: () => void;
  onPromptSave: () => void;
}) {
  const enabled = !!settingsForm.enabled;

  return (
    <aside className="space-y-4 xl:sticky xl:top-20">
      <Card className="rounded-lg">
        <CardContent className="space-y-4 p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 font-semibold">
              <Bot size={17} className="text-primary" />
              LLM审查
            </div>
            <CompactSwitch
              checked={enabled}
              onChange={checked => onSettingsChange(current => ({ ...current, enabled: checked }))}
            />
          </div>
          {settingsDirty && (
            <div className="text-xs text-muted-foreground">
              {settingsSaving ? '保存中' : '待自动保存'}
            </div>
          )}
          <fieldset className={!enabled ? 'pointer-events-none space-y-3 opacity-50' : 'space-y-3'}>
            <CompactField label="Base URL">
              <Input
                value={settingsForm.llm_base_url || ''}
                onChange={event =>
                  onSettingsChange(current => ({ ...current, llm_base_url: event.target.value }))
                }
                placeholder="OpenAI-compatible API 地址"
              />
            </CompactField>
            <CompactField label="API Key">
              <Input
                value={settingsForm.llm_api_key || ''}
                onChange={event =>
                  onSettingsChange(current => ({ ...current, llm_api_key: event.target.value }))
                }
                placeholder="留空不修改，星号会保留旧值"
                type="password"
              />
            </CompactField>
            <CompactField label="模型名称">
              <Input
                value={settingsForm.llm_model_name || ''}
                onChange={event =>
                  onSettingsChange(current => ({ ...current, llm_model_name: event.target.value }))
                }
                placeholder="例如 gpt-4.1-mini"
              />
            </CompactField>
          </fieldset>
        </CardContent>
      </Card>
      <Card className="rounded-lg">
        <CardContent className="space-y-3 p-4">
          <div className="flex items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2 font-semibold">
              <ScrollText size={17} className="text-muted-foreground" />
              <span className="truncate">{prompt?.name ?? '审查提示词'}</span>
            </div>
            {promptDirty && <CompactBadge>未保存</CompactBadge>}
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Braces size={14} />
            {userReportPromptPlaceholders.map(placeholder => (
              <CompactBadge
                key={placeholder.token}
                title={placeholder.description}
                variant="outline"
              >
                {placeholder.token}
              </CompactBadge>
            ))}
          </div>
          {promptLoading ? (
            <div className="h-40 animate-pulse rounded-md bg-muted" />
          ) : (
            <Textarea
              value={promptDraft}
              onChange={event => onPromptDraftChange(event.target.value)}
              className="min-h-[260px] font-mono text-xs leading-relaxed"
              spellCheck={false}
            />
          )}
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              className="rounded-md"
              onClick={onPromptCancel}
              disabled={!promptDirty || promptSaving || promptResetting}
            >
              取消
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="rounded-md"
              onClick={onPromptReset}
              disabled={promptSaving || promptResetting}
            >
              <RotateCcw size={14} className="mr-1" />
              默认
            </Button>
            <Button
              size="sm"
              className="rounded-md"
              onClick={onPromptSave}
              disabled={!promptDraft.trim() || !promptDirty || promptSaving}
            >
              <Save size={14} className="mr-1" />
              保存
            </Button>
          </div>
        </CardContent>
      </Card>
    </aside>
  );
}

function CompactField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block min-w-0">
      <span className="mb-1 block text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

function CompactSwitch({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      className={
        'relative h-6 w-11 rounded-full transition-colors ' + (checked ? 'bg-zinc-950' : 'bg-muted')
      }
      onClick={() => onChange(!checked)}
    >
      <span
        className={
          'absolute left-1 top-1 h-4 w-4 rounded-full bg-white shadow transition-transform ' +
          (checked ? 'translate-x-5' : 'translate-x-0')
        }
      />
    </button>
  );
}

function CompactBadge({
  children,
  title,
  variant = 'secondary',
}: {
  children: ReactNode;
  title?: string;
  variant?: 'secondary' | 'outline';
}) {
  return (
    <span
      title={title}
      className={
        'inline-flex h-6 items-center rounded-md px-2 text-xs font-medium ' +
        (variant === 'outline'
          ? 'border border-border bg-background font-mono text-muted-foreground'
          : 'bg-muted text-muted-foreground')
      }
    >
      {children}
    </span>
  );
}

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
            封禁账号
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
            封禁账号
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
