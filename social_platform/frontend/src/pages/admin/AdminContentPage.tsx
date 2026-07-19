import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Archive,
  ArchiveRestore,
  Bot,
  Braces,
  CheckCircle,
  FileText,
  Heart,
  MessageCircle,
  RotateCcw,
  Save,
  ScrollText,
  Search,
  ShieldAlert,
} from 'lucide-react';
import {
  adminApi,
  adminKeys,
  type ContentItem,
  type ContentModerationLLMPromptConfig,
  type ContentModerationLLMSettings,
  type ContentModerationLLMSettingsUpdate,
  type ModerationAppealItem,
  type ReportedContentItem,
} from '@/features/admin';
import { Button, Card, CardContent, Input, Textarea } from '@/shared/components/ui';
import { AdminPagination } from './AdminPagination';

type ContentMode = 'all' | 'reported' | 'appeals';
const PAGE_SIZE = 50;

function getContentKey(item: ContentItem) {
  return item.type + '-' + item.id;
}

function getReviewTargetType(item: ContentItem) {
  return item.type === 'comment' ? 'comment' : 'post';
}

const reportPromptPlaceholders = [
  {
    token: '{context_json}',
    description: '被举报内容、举报原因、所属帖子和父评论 JSON；处理后会归档。',
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

function getContentPath(item: ContentItem, includeArchived = false): string | null {
  if (!includeArchived && item.moderation_status === 'archived') {
    return null;
  }
  if (item.type === 'comment' && item.post_id) {
    return '/post/' + item.post_id + '?commentId=' + item.id;
  }
  if (item.type !== 'comment') {
    return '/post/' + item.id;
  }
  return null;
}

function ContentPreview({
  item,
  includeArchived = false,
}: {
  item: ContentItem;
  includeArchived?: boolean;
}) {
  const targetPath = getContentPath(item, includeArchived);
  const content = (
    <>
      {item.title && <p className="mb-1 font-medium">{item.title}</p>}
      <p className="line-clamp-2 text-muted-foreground group-hover:text-primary">{item.content}</p>
    </>
  );

  if (!targetPath) {
    return <div>{content}</div>;
  }

  return (
    <Link to={targetPath} className="group block hover:text-primary">
      {content}
    </Link>
  );
}

export default function AdminContentPage() {
  const [mode, setMode] = useState<ContentMode>('all');
  const [page, setPage] = useState(0);
  const [keyword, setKeyword] = useState('');
  const [type, setType] = useState('');
  const [deleting, setDeleting] = useState<ContentItem | null>(null);
  const [deletingReported, setDeletingReported] = useState<ReportedContentItem | null>(null);
  const [rejectingAppeal, setRejectingAppeal] = useState<ModerationAppealItem | null>(null);
  const [batchDeleting, setBatchDeleting] = useState(false);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [releasingKey, setReleasingKey] = useState<string | null>(null);
  const [reportSettingsForm, setReportSettingsForm] = useState<ContentModerationLLMSettingsUpdate>(
    {}
  );
  const [reportPromptDraft, setReportPromptDraft] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const contentQuery = useQuery({
    queryKey: [...adminKeys.content(type, keyword), page],
    queryFn: () =>
      adminApi.content({
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
        type: type || undefined,
        keyword: keyword.trim() || undefined,
      }),
    enabled: mode === 'all',
  });

  const reportedQuery = useQuery({
    queryKey: [...adminKeys.reportedContent(type, keyword), page],
    queryFn: () =>
      adminApi.reportedContent({
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
        type: type || undefined,
        keyword: keyword.trim() || undefined,
      }),
    enabled: mode === 'reported',
  });

  const appealsQuery = useQuery({
    queryKey: [...adminKeys.contentAppeals(keyword), page],
    queryFn: () =>
      adminApi.contentAppeals({
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
        keyword: keyword.trim() || undefined,
      }),
    enabled: mode === 'appeals',
  });

  const archivedQuery = useQuery({
    queryKey: [...adminKeys.archivedContent(type, keyword), page],
    queryFn: () =>
      adminApi.archivedContent({
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
        type: type || undefined,
        keyword: keyword.trim() || undefined,
      }),
    enabled: mode === 'reported',
  });

  const { data: reportSettings } = useQuery({
    queryKey: adminKeys.reportModerationSettings,
    queryFn: adminApi.reportModerationSettings,
    enabled: mode === 'reported',
  });

  const { data: reportPromptConfig, isLoading: isReportPromptLoading } = useQuery({
    queryKey: adminKeys.reportModerationPrompt,
    queryFn: adminApi.reportModerationPrompt,
    enabled: mode === 'reported',
  });

  const items = contentQuery.data?.items ?? [];
  const reportedItems = reportedQuery.data?.items ?? [];
  const archivedItems = archivedQuery.data?.items ?? [];
  const appealItems = appealsQuery.data?.items ?? [];
  const selectedItems = items.filter(item => selectedKeys.includes(getContentKey(item)));
  const allPageSelected =
    items.length > 0 && items.every(item => selectedKeys.includes(getContentKey(item)));
  const reportPromptValue = reportPromptDraft ?? reportPromptConfig?.value ?? '';
  const isReportPromptDirty =
    !!reportPromptConfig && reportPromptValue !== reportPromptConfig.value;
  const reportSettingsDirty = useMemo(() => {
    if (!reportSettings) return false;
    return !reportSettingsFormsEqual(reportSettingsForm, reportSettingsToForm(reportSettings));
  }, [reportSettings, reportSettingsForm]);

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

  const deleteMutation = useMutation({
    mutationFn: ({ item, reason }: { item: ContentItem; reason: string }) => {
      const payload = { reason: reason || undefined, notify_author: true };
      return item.type === 'comment'
        ? adminApi.deleteComment(item.id, payload)
        : adminApi.deletePost(item.id, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'content'] });
      if (deleting) {
        setSelectedKeys(current => current.filter(key => key !== getContentKey(deleting)));
      }
      setDeleting(null);
    },
  });

  const batchDeleteMutation = useMutation({
    mutationFn: async ({
      items: targetItems,
      reason,
    }: {
      items: ContentItem[];
      reason: string;
    }) => {
      const payload = { reason: reason || undefined, notify_author: true };
      const orderedItems = [...targetItems].sort((a, b) => {
        if (a.type === b.type) return 0;
        return a.type === 'comment' ? -1 : 1;
      });
      for (const item of orderedItems) {
        if (item.type === 'comment') {
          await adminApi.deleteComment(item.id, payload);
        } else {
          await adminApi.deletePost(item.id, payload);
        }
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'content'] });
      setBatchDeleting(false);
      setSelectedKeys([]);
    },
  });

  const releaseMutation = useMutation({
    mutationFn: (item: ReportedContentItem) =>
      adminApi.releaseReportedContent(getReviewTargetType(item), item.id),
    onMutate: item => {
      setReleasingKey(getContentKey(item));
    },
    onSettled: () => {
      setReleasingKey(null);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'content', 'reports'] });
    },
  });

  const deleteReportedMutation = useMutation({
    mutationFn: ({ item, reason }: { item: ReportedContentItem; reason: string }) => {
      const payload = { reason: reason || undefined, notify_author: true };
      return adminApi.deleteReportedContent(getReviewTargetType(item), item.id, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'content'] });
      setDeletingReported(null);
    },
  });

  const restoreMutation = useMutation({
    mutationFn: (item: ContentItem) =>
      item.type === 'comment' ? adminApi.restoreComment(item.id) : adminApi.restorePost(item.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'content'] });
    },
  });

  const approveAppealMutation = useMutation({
    mutationFn: (appeal: ModerationAppealItem) => adminApi.approveContentAppeal(appeal.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'content'] });
    },
  });

  const rejectAppealMutation = useMutation({
    mutationFn: ({ appeal, reason }: { appeal: ModerationAppealItem; reason: string }) =>
      adminApi.rejectContentAppeal(appeal.id, { reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'content'] });
      setRejectingAppeal(null);
    },
  });

  const saveReportSettingsMutation = useMutation({
    mutationFn: adminApi.updateReportModerationSettings,
    onSuccess: data => {
      queryClient.setQueryData(adminKeys.reportModerationSettings, data);
    },
  });

  const updateReportPromptMutation = useMutation({
    mutationFn: (value: string) => adminApi.updateReportModerationPrompt(value),
    onSuccess: updated => {
      setReportPromptDraft(updated.value);
      queryClient.setQueryData(adminKeys.reportModerationPrompt, updated);
    },
  });

  const resetReportPromptMutation = useMutation({
    mutationFn: adminApi.resetReportModerationPrompt,
    onSuccess: updated => {
      setReportPromptDraft(updated.value);
      queryClient.setQueryData(adminKeys.reportModerationPrompt, updated);
    },
  });

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

  const toggleSelected = (item: ContentItem) => {
    const key = getContentKey(item);
    setSelectedKeys(current =>
      current.includes(key) ? current.filter(itemKey => itemKey !== key) : [...current, key]
    );
  };

  const toggleAllPage = () => {
    setSelectedKeys(current => {
      const pageKeys = items.map(getContentKey);
      if (items.every(item => current.includes(getContentKey(item)))) {
        return current.filter(key => !pageKeys.includes(key));
      }
      return Array.from(new Set([...current, ...pageKeys]));
    });
  };

  const switchMode = (nextMode: ContentMode) => {
    setMode(nextMode);
    setPage(0);
    setSelectedKeys([]);
  };

  return (
    <div>
      <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold">内容管理</h1>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              variant={mode === 'all' ? 'default' : 'outline'}
              size="sm"
              className="rounded-md"
              onClick={() => switchMode('all')}
            >
              <FileText size={14} className="mr-1" />
              全部内容
            </Button>
            <Button
              variant={mode === 'reported' ? 'default' : 'outline'}
              size="sm"
              className="rounded-md"
              onClick={() => switchMode('reported')}
            >
              <ShieldAlert size={14} className="mr-1" />
              被举报内容审查
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
          </div>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          {mode === 'all' && selectedKeys.length > 0 && (
            <Button
              variant="destructive"
              className="rounded-md"
              onClick={() => setBatchDeleting(true)}
            >
              <Archive size={14} className="mr-1" />
              批量归档
            </Button>
          )}
          <select
            value={type}
            onChange={event => {
              setType(event.target.value);
              setPage(0);
              setSelectedKeys([]);
            }}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="">全部内容</option>
            <option value="post">帖子/文章</option>
            <option value="comment">评论</option>
          </select>
          <div className="relative w-full sm:w-72">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              value={keyword}
              onChange={event => {
                setKeyword(event.target.value);
                setPage(0);
                setSelectedKeys([]);
              }}
              placeholder={
                mode === 'reported'
                  ? '搜索被举报内容'
                  : mode === 'appeals'
                    ? '搜索申诉'
                    : '搜索内容'
              }
              className="pl-8"
            />
          </div>
        </div>
      </div>

      {mode === 'all' ? (
        <AllContentTable
          items={items}
          selectedKeys={selectedKeys}
          allPageSelected={allPageSelected}
          onToggleSelected={toggleSelected}
          onToggleAllPage={toggleAllPage}
          onDelete={setDeleting}
        />
      ) : mode === 'reported' ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px] xl:items-start">
          <div className="space-y-4">
            <ReportedContentTable
              items={reportedItems}
              releasingKey={releasingKey}
              releasePending={releaseMutation.isPending}
              onRelease={item => releaseMutation.mutate(item)}
              onDelete={setDeletingReported}
            />
            <ArchivedContentTable
              items={archivedItems}
              restoringId={restoreMutation.variables?.id ?? null}
              restoring={restoreMutation.isPending}
              onRestore={item => restoreMutation.mutate(item)}
            />
          </div>
          <ReportModerationLLMPanel
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
      ) : (
        <ContentAppealsTable
          items={appealItems}
          approvingId={approveAppealMutation.variables?.id ?? null}
          approving={approveAppealMutation.isPending}
          onOpenArchived={appeal => {
            setType(appeal.target_type === 'comment' ? 'comment' : 'post');
            switchMode('reported');
          }}
          onApprove={appeal => approveAppealMutation.mutate(appeal)}
          onReject={setRejectingAppeal}
        />
      )}

      <AdminPagination
        page={page}
        pageSize={PAGE_SIZE}
        total={
          mode === 'all'
            ? (contentQuery.data?.total ?? 0)
            : mode === 'appeals'
              ? (appealsQuery.data?.total ?? 0)
              : Math.max(reportedQuery.data?.total ?? 0, archivedQuery.data?.total ?? 0)
        }
        onPageChange={nextPage => {
          setSelectedKeys([]);
          setPage(nextPage);
        }}
      />

      {deleting && (
        <DeleteContentDialog
          item={deleting}
          saving={deleteMutation.isPending}
          onClose={() => setDeleting(null)}
          onConfirm={reason => deleteMutation.mutate({ item: deleting, reason })}
        />
      )}
      {batchDeleting && (
        <BatchDeleteContentDialog
          items={selectedItems}
          saving={batchDeleteMutation.isPending}
          onClose={() => setBatchDeleting(false)}
          onConfirm={reason => batchDeleteMutation.mutate({ items: selectedItems, reason })}
        />
      )}
      {deletingReported && (
        <DeleteContentDialog
          item={deletingReported}
          saving={deleteReportedMutation.isPending}
          onClose={() => setDeletingReported(null)}
          onConfirm={reason => deleteReportedMutation.mutate({ item: deletingReported, reason })}
        />
      )}
      {rejectingAppeal && (
        <RejectAppealDialog
          title="拒绝申诉"
          saving={rejectAppealMutation.isPending}
          onClose={() => setRejectingAppeal(null)}
          onConfirm={reason => rejectAppealMutation.mutate({ appeal: rejectingAppeal, reason })}
        />
      )}
    </div>
  );
}

function AllContentTable({
  items,
  selectedKeys,
  allPageSelected,
  onToggleSelected,
  onToggleAllPage,
  onDelete,
}: {
  items: ContentItem[];
  selectedKeys: string[];
  allPageSelected: boolean;
  onToggleSelected: (item: ContentItem) => void;
  onToggleAllPage: () => void;
  onDelete: (item: ContentItem) => void;
}) {
  return (
    <Card className="rounded-lg">
      <CardContent className="p-0">
        <div className="overflow-auto">
          <table className="w-full min-w-[920px] text-sm">
            <thead className="border-b bg-muted/50 text-left text-muted-foreground">
              <tr>
                <th className="w-10 px-4 py-3 font-medium">
                  <input
                    type="checkbox"
                    checked={allPageSelected}
                    onChange={onToggleAllPage}
                    aria-label="选择当前页内容"
                  />
                </th>
                <th className="px-4 py-3 font-medium">内容</th>
                <th className="px-4 py-3 font-medium">作者</th>
                <th className="px-4 py-3 font-medium">类型</th>
                <th className="px-4 py-3 font-medium">互动</th>
                <th className="px-4 py-3 font-medium">时间</th>
                <th className="px-4 py-3 text-center font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={getContentKey(item)} className="border-b last:border-0">
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selectedKeys.includes(getContentKey(item))}
                      onChange={() => onToggleSelected(item)}
                      aria-label={
                        '选择' + (item.type === 'comment' ? '评论' : '帖子') + ' ' + item.id
                      }
                    />
                  </td>
                  <td className="max-w-xl px-4 py-3">
                    <ContentPreview item={item} />
                  </td>
                  <td className="px-4 py-3">
                    <AuthorLink item={item} />
                  </td>
                  <td className="px-4 py-3">
                    <ContentTypeIcon item={item} />
                  </td>
                  <td className="px-4 py-3">
                    <InteractionStats item={item} />
                  </td>
                  <td className="px-4 py-3">{new Date(item.created_at).toLocaleString()}</td>
                  <td className="px-4 py-3 text-center">
                    <Button
                      variant="destructive"
                      size="icon"
                      className="mx-auto rounded-md"
                      onClick={() => onDelete(item)}
                      title="归档"
                      aria-label={
                        '归档' + (item.type === 'comment' ? '评论' : '帖子') + ' ' + item.id
                      }
                    >
                      <Archive size={16} />
                    </Button>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td className="px-4 py-10 text-center text-muted-foreground" colSpan={7}>
                    暂无内容
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

function ReportedContentTable({
  items,
  releasingKey,
  releasePending,
  onRelease,
  onDelete,
}: {
  items: ReportedContentItem[];
  releasingKey: string | null;
  releasePending: boolean;
  onRelease: (item: ReportedContentItem) => void;
  onDelete: (item: ReportedContentItem) => void;
}) {
  return (
    <Card className="rounded-lg">
      <CardContent className="p-0">
        <div className="overflow-auto">
          <table className="w-full min-w-[1080px] text-sm">
            <thead className="border-b bg-muted/50 text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">内容</th>
                <th className="px-4 py-3 font-medium">作者</th>
                <th className="px-4 py-3 font-medium">类型</th>
                <th className="px-4 py-3 font-medium">举报人数</th>
                <th className="px-4 py-3 font-medium">举报原因</th>
                <th className="px-4 py-3 font-medium">最近举报</th>
                <th className="px-4 py-3 text-center font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={getContentKey(item)} className="border-b last:border-0">
                  <td className="max-w-md px-4 py-3">
                    <ContentPreview item={item} />
                  </td>
                  <td className="px-4 py-3">
                    <AuthorLink item={item} />
                  </td>
                  <td className="px-4 py-3">
                    <ContentTypeIcon item={item} />
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center rounded-md bg-muted px-2 py-1 font-medium tabular-nums">
                      {item.report_count}
                    </span>
                  </td>
                  <td className="max-w-sm px-4 py-3">
                    <div className="space-y-1.5">
                      {item.report_reasons.map(reason => (
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
                  <td className="px-4 py-3">{new Date(item.last_reported_at).toLocaleString()}</td>
                  <td className="px-4 py-3">
                    <div className="flex justify-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="rounded-md gap-1"
                        onClick={() => onRelease(item)}
                        disabled={releasePending && releasingKey === getContentKey(item)}
                      >
                        <CheckCircle size={14} />
                        放行
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        className="rounded-md gap-1"
                        onClick={() => onDelete(item)}
                      >
                        <Archive size={14} />
                        归档
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td className="px-4 py-10 text-center text-muted-foreground" colSpan={7}>
                    暂无待审举报内容
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

function ArchivedContentTable({
  items,
  restoringId,
  restoring,
  onRestore,
}: {
  items: ContentItem[];
  restoringId: number | null;
  restoring: boolean;
  onRestore: (item: ContentItem) => void;
}) {
  return (
    <Card className="rounded-lg">
      <CardContent className="p-0">
        <div className="border-b px-4 py-3">
          <div className="flex items-center gap-2 font-semibold">
            <ArchiveRestore size={16} className="text-muted-foreground" />
            已归档内容
          </div>
        </div>
        <div className="overflow-auto">
          <table className="w-full min-w-[980px] text-sm">
            <thead className="border-b bg-muted/50 text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">内容</th>
                <th className="px-4 py-3 font-medium">作者</th>
                <th className="px-4 py-3 font-medium">类型</th>
                <th className="px-4 py-3 font-medium">归档原因</th>
                <th className="px-4 py-3 font-medium">归档时间</th>
                <th className="px-4 py-3 text-center font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={getContentKey(item)} className="border-b last:border-0">
                  <td className="max-w-md px-4 py-3">
                    <ContentPreview item={item} />
                  </td>
                  <td className="px-4 py-3">
                    <AuthorLink item={item} />
                  </td>
                  <td className="px-4 py-3">
                    <ContentTypeIcon item={item} />
                  </td>
                  <td className="max-w-sm px-4 py-3 text-muted-foreground">
                    <p className="line-clamp-2 break-words">{item.archive_reason || '未填写'}</p>
                  </td>
                  <td className="px-4 py-3">
                    {item.archived_at ? new Date(item.archived_at).toLocaleString() : '-'}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <Button
                      variant="outline"
                      size="sm"
                      className="rounded-md gap-1"
                      onClick={() => onRestore(item)}
                      disabled={restoring && restoringId === item.id}
                    >
                      <ArchiveRestore size={14} />
                      恢复
                    </Button>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td className="px-4 py-10 text-center text-muted-foreground" colSpan={6}>
                    暂无已归档内容
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

function ContentAppealsTable({
  items,
  approvingId,
  approving,
  onOpenArchived,
  onApprove,
  onReject,
}: {
  items: ModerationAppealItem[];
  approvingId: number | null;
  approving: boolean;
  onOpenArchived: (appeal: ModerationAppealItem) => void;
  onApprove: (appeal: ModerationAppealItem) => void;
  onReject: (appeal: ModerationAppealItem) => void;
}) {
  return (
    <Card className="rounded-lg">
      <CardContent className="p-0">
        <div className="overflow-auto">
          <table className="w-full min-w-[1180px] text-sm">
            <thead className="border-b bg-muted/50 text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">申诉人</th>
                <th className="px-4 py-3 font-medium">内容</th>
                <th className="px-4 py-3 font-medium">处理操作</th>
                <th className="px-4 py-3 font-medium">处理理由</th>
                <th className="px-4 py-3 font-medium">申诉理由</th>
                <th className="px-4 py-3 text-center font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
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
                    <button
                      type="button"
                      className="line-clamp-2 text-left break-words text-muted-foreground hover:text-primary hover:underline"
                      onClick={() => onOpenArchived(item)}
                    >
                      {item.target_content || '-'}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      className="font-medium text-primary hover:underline"
                      onClick={() => onOpenArchived(item)}
                    >
                      {item.action_label}
                    </button>
                  </td>
                  <td className="max-w-sm px-4 py-3 text-muted-foreground">
                    <p className="line-clamp-3 break-words">{item.moderation_reason || '未填写'}</p>
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
                        onClick={() => onApprove(item)}
                        disabled={approving && approvingId === item.id}
                      >
                        <ArchiveRestore size={14} />
                        恢复
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
              ))}
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
  title,
  saving,
  onClose,
  onConfirm,
}: {
  title: string;
  saving: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState('');

  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-lg rounded-lg shadow-xl">
        <CardContent className="space-y-4 p-4">
          <h3 className="text-base font-semibold">{title}</h3>
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

function ReportModerationLLMPanel({
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
                type="password"
              />
            </CompactField>
            <CompactField label="模型名称">
              <Input
                value={settingsForm.llm_model_name || ''}
                onChange={event =>
                  onSettingsChange(current => ({ ...current, llm_model_name: event.target.value }))
                }
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
            {reportPromptPlaceholders.map(placeholder => (
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
        'relative h-6 w-11 overflow-hidden rounded-[9999px] transition-colors ' +
        (checked ? 'bg-zinc-950' : 'bg-muted')
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

function AuthorLink({ item }: { item: ContentItem }) {
  return (
    <Link to={'/user/' + item.author_id} className="font-medium hover:text-primary hover:underline">
      @{item.author_username || item.author_id}
    </Link>
  );
}

function ContentTypeIcon({ item }: { item: ContentItem }) {
  return (
    <span
      className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-muted text-muted-foreground"
      title={item.type === 'comment' ? '评论' : '帖子'}
      aria-label={item.type === 'comment' ? '评论' : '帖子'}
    >
      {item.type === 'comment' ? <MessageCircle size={15} /> : <FileText size={15} />}
    </span>
  );
}

function InteractionStats({ item }: { item: ContentItem }) {
  return (
    <div className="flex items-center gap-3">
      <span className="inline-flex items-center gap-1 text-muted-foreground" title="点赞数">
        <Heart size={15} />
        <span className="font-medium tabular-nums text-foreground">{item.like_count}</span>
      </span>
      {item.comment_count !== null && (
        <span className="inline-flex items-center gap-1 text-muted-foreground" title="评论数">
          <MessageCircle size={15} />
          <span className="font-medium tabular-nums text-foreground">{item.comment_count}</span>
        </span>
      )}
    </div>
  );
}

function DeleteContentDialog({
  item,
  saving,
  onClose,
  onConfirm,
}: {
  item: ContentItem;
  saving: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState('');

  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-lg rounded-lg shadow-xl">
        <CardContent className="space-y-4 p-5">
          <div>
            <h2 className="text-lg font-semibold">归档内容</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {item.type === 'comment' ? '评论' : '帖子'} #{item.id}
            </p>
          </div>
          <Textarea
            value={reason}
            onChange={event => setReason(event.target.value)}
            placeholder="归档原因，会通过通知发送给作者"
            rows={4}
          />
          <div className="flex justify-end gap-2">
            <Button variant="outline" className="rounded-md" onClick={onClose} disabled={saving}>
              取消
            </Button>
            <Button
              variant="destructive"
              className="rounded-md"
              disabled={saving}
              onClick={() => onConfirm(reason)}
            >
              归档
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function BatchDeleteContentDialog({
  items,
  saving,
  onClose,
  onConfirm,
}: {
  items: ContentItem[];
  saving: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState('');
  const commentCount = items.filter(item => item.type === 'comment').length;
  const postCount = items.length - commentCount;

  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-lg rounded-lg shadow-xl">
        <CardContent className="space-y-4 p-5">
          <div>
            <h2 className="text-lg font-semibold">批量归档内容</h2>
            <p className="mt-1 flex items-center gap-3 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <FileText size={14} />
                {postCount} 帖
              </span>
              <span className="inline-flex items-center gap-1">
                <MessageCircle size={14} />
                {commentCount} 评论
              </span>
            </p>
          </div>
          <Textarea
            value={reason}
            onChange={event => setReason(event.target.value)}
            placeholder="归档原因，会通过通知发送给作者"
            rows={4}
          />
          <div className="flex justify-end gap-2">
            <Button variant="outline" className="rounded-md" onClick={onClose} disabled={saving}>
              取消
            </Button>
            <Button
              variant="destructive"
              className="rounded-md"
              disabled={saving || items.length === 0}
              onClick={() => onConfirm(reason)}
            >
              归档
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
