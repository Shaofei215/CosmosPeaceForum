/**
 * 平台管理员热门话题页面。
 *
 * 生成事件流从管理员 tokenStorage 读取最新 access token，配合 refresh 轮换后的登录态。
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Bot,
  Braces,
  Check,
  Flame,
  Loader2,
  Play,
  RotateCcw,
  Save,
  ScrollText,
  Search,
  Trash2,
} from 'lucide-react';
import {
  adminApi,
  adminKeys,
  type HotTopic,
  type HotTopicGenerationRunResponse,
  type HotTopicPromptConfig,
  type HotTopicPublishPolicy,
  type HotTopicRequest,
  type HotTopicSettings,
  type HotTopicSettingsUpdate,
} from '@/features/admin';
import { Button, Card, CardContent, Input, Textarea } from '@/shared/components/ui';
import { getAdminAccessToken } from '@/features/admin/tokenStorage';
import { cn } from '@/shared/lib/utils';

const emptyTopic: HotTopicRequest = {
  title: '',
  search_query: '',
  summary: '',
  source: 'manual',
  status: 'active',
  rank: 1,
};

const promptPlaceholders = [
  { token: '{context_json}', description: '当前站内热帖、已有热榜和历史生成记录 JSON。' },
];

function settingsToForm(settings: HotTopicSettings): HotTopicSettingsUpdate {
  return {
    agent_enabled: settings.agent_enabled,
    agent_interval_minutes: settings.agent_interval_minutes,
    publish_policy: settings.publish_policy,
    llm_base_url: settings.llm_base_url || '',
    llm_model_name: settings.llm_model_name || '',
    llm_api_key: settings.llm_api_key || '',
    web_search_enabled: settings.web_search_enabled,
    tavily_api_key: settings.tavily_api_key || '',
    history_limit: settings.history_limit,
    max_llm_rounds: settings.max_llm_rounds,
  };
}

function normalizeSettingsForm(form: HotTopicSettingsUpdate): HotTopicSettingsUpdate {
  return {
    agent_enabled: !!form.agent_enabled,
    agent_interval_minutes: Number(form.agent_interval_minutes || 180),
    publish_policy: form.publish_policy || 'draft',
    llm_base_url: form.llm_base_url || '',
    llm_model_name: form.llm_model_name || '',
    llm_api_key: form.llm_api_key || '',
    web_search_enabled: !!form.web_search_enabled,
    tavily_api_key: form.tavily_api_key || '',
    history_limit: Number(form.history_limit ?? 3),
    max_llm_rounds: Number(form.max_llm_rounds || 6),
  };
}

function settingsFormsEqual(left: HotTopicSettingsUpdate, right: HotTopicSettingsUpdate) {
  const normalizedLeft = normalizeSettingsForm(left);
  const normalizedRight = normalizeSettingsForm(right);
  return JSON.stringify(normalizedLeft) === JSON.stringify(normalizedRight);
}

export default function AdminHotTopicsPage() {
  const [editing, setEditing] = useState<HotTopic | null>(null);
  const [form, setForm] = useState<HotTopicRequest>(emptyTopic);
  const [settingsForm, setSettingsForm] = useState<HotTopicSettingsUpdate>({});
  const [promptDraft, setPromptDraft] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const generateEventSourceRef = useRef<EventSource | null>(null);
  const queryClient = useQueryClient();

  const { data: activeTopicsData } = useQuery({
    queryKey: adminKeys.hotTopics('active', ''),
    queryFn: () => adminApi.hotTopics({ skip: 0, limit: 200, status: 'active' }),
  });

  const { data: settings } = useQuery({
    queryKey: adminKeys.hotTopicSettings,
    queryFn: adminApi.hotTopicSettings,
  });

  const { data: agentDraftsData } = useQuery({
    queryKey: adminKeys.hotTopics('draft', 'agent'),
    queryFn: () =>
      adminApi.hotTopics({
        skip: 0,
        limit: 200,
        status: 'draft',
        source: 'agent',
      }),
    enabled: settingsForm.publish_policy === 'draft',
  });

  const { data: promptConfig, isLoading: isPromptLoading } = useQuery({
    queryKey: adminKeys.hotTopicPrompt,
    queryFn: adminApi.hotTopicPrompt,
  });

  useEffect(() => {
    if (settings) {
      setSettingsForm(settingsToForm(settings));
    }
  }, [settings]);

  useEffect(() => {
    if (promptConfig && promptDraft === null) {
      setPromptDraft(promptConfig.value);
    }
  }, [promptConfig, promptDraft]);

  useEffect(() => {
    return () => {
      generateEventSourceRef.current?.close();
    };
  }, []);

  const invalidateHotTopics = () => {
    queryClient.invalidateQueries({ queryKey: ['admin', 'hot-topics'] });
    queryClient.invalidateQueries({ queryKey: ['hot-topics'] });
  };

  const saveTopicMutation = useMutation({
    mutationFn: (payload: HotTopicRequest) =>
      editing ? adminApi.updateHotTopic(editing.id, payload) : adminApi.createHotTopic(payload),
    onSuccess: () => {
      invalidateHotTopics();
      setEditing(null);
      setForm(emptyTopic);
    },
  });

  const deleteTopicMutation = useMutation({
    mutationFn: adminApi.deleteHotTopic,
    onSuccess: invalidateHotTopics,
  });

  const publishTopicMutation = useMutation({
    mutationFn: adminApi.publishHotTopic,
    onSuccess: invalidateHotTopics,
  });

  const saveSettingsMutation = useMutation({
    mutationFn: adminApi.updateHotTopicSettings,
    onSuccess: data => {
      queryClient.setQueryData(adminKeys.hotTopicSettings, data);
      queryClient.invalidateQueries({ queryKey: adminKeys.hotTopics('draft', 'agent') });
    },
  });

  const updatePromptMutation = useMutation({
    mutationFn: (value: string) => adminApi.updateHotTopicPrompt(value),
    onSuccess: updated => {
      setPromptDraft(updated.value);
      queryClient.setQueryData(adminKeys.hotTopicPrompt, updated);
    },
  });

  const resetPromptMutation = useMutation({
    mutationFn: adminApi.resetHotTopicPrompt,
    onSuccess: updated => {
      setPromptDraft(updated.value);
      queryClient.setQueryData(adminKeys.hotTopicPrompt, updated);
    },
  });

  const saveSettings = saveSettingsMutation.mutate;
  const settingsSavePending = saveSettingsMutation.isPending;

  useEffect(() => {
    if (!settings || settingsSavePending) return;
    const current = normalizeSettingsForm(settingsForm);
    const persisted = settingsToForm(settings);
    if (settingsFormsEqual(current, persisted)) return;

    const timeoutId = window.setTimeout(() => {
      saveSettings(current);
    }, 700);

    return () => window.clearTimeout(timeoutId);
  }, [settings, settingsForm, settingsSavePending, saveSettings]);

  const agentEnabled = !!settingsForm.agent_enabled;
  const publishPolicy = settingsForm.publish_policy || 'draft';
  const activeTopics = activeTopicsData?.items ?? [];
  const agentDrafts = publishPolicy === 'draft' ? (agentDraftsData?.items ?? []) : [];
  const promptValue = promptDraft ?? promptConfig?.value ?? '';
  const isPromptDirty = !!promptConfig && promptValue !== promptConfig.value;
  const settingsDirty = useMemo(() => {
    if (!settings) return false;
    return !settingsFormsEqual(settingsForm, settingsToForm(settings));
  }, [settings, settingsForm]);

  const closeGenerateStream = () => {
    generateEventSourceRef.current?.close();
    generateEventSourceRef.current = null;
    setIsGenerating(false);
  };

  const startGenerate = () => {
    const token = getAdminAccessToken();
    if (!token) {
      setGenerationError('管理员登录已失效，请重新登录');
      return;
    }

    generateEventSourceRef.current?.close();
    setGenerationError(null);
    setIsGenerating(true);

    const eventSource = new EventSource(adminApi.getHotTopicGenerateEventsUrl(token));
    generateEventSourceRef.current = eventSource;

    const handleCompleted = (event: MessageEvent<string>) => {
      try {
        JSON.parse(event.data) as HotTopicGenerationRunResponse;
      } catch {
        // 收到完成事件后仍以列表刷新作为最终状态来源。
      }
      invalidateHotTopics();
      queryClient.invalidateQueries({ queryKey: adminKeys.hotTopicGenerations });
      closeGenerateStream();
    };

    const handleFailed = (event: MessageEvent<string>) => {
      try {
        const data = JSON.parse(event.data) as { error?: string };
        setGenerationError(data.error || '热榜生成失败，请检查后端日志');
      } catch {
        setGenerationError('热榜生成失败，请检查后端日志');
      }
      invalidateHotTopics();
      closeGenerateStream();
    };

    eventSource.addEventListener('hot-topics.generate.completed', handleCompleted);
    eventSource.addEventListener('hot-topics.generate.failed', handleFailed);
    eventSource.onerror = () => {
      if (generateEventSourceRef.current === eventSource) {
        setGenerationError('热榜生成连接中断，请稍后重试');
        closeGenerateStream();
      }
    };
  };

  const startEdit = (topic: HotTopic) => {
    setEditing(topic);
    setForm({
      title: topic.title,
      search_query: topic.search_query,
      summary: topic.summary || '',
      source: 'manual',
      status: 'active',
      rank: topic.rank,
    });
  };

  const submitTopic = (event: FormEvent) => {
    event.preventDefault();
    saveTopicMutation.mutate({
      ...form,
      source: 'manual',
      status: 'active',
      rank: Number(form.rank || 1),
    });
  };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold">热点管理</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          人工维护当前热榜，或让 LLM 生成候选后审批发布
        </p>
      </div>

      <div className="grid gap-5 xl:grid-cols-2 xl:items-start">
        <section className="space-y-5 xl:border-r xl:border-border xl:pr-5">
          <Card className="rounded-lg">
            <CardContent className="p-4">
              <form onSubmit={submitTopic} className="space-y-3">
                <div className="flex items-center gap-2 font-semibold">
                  <Flame size={17} className="text-orange-500" />
                  {editing ? '编辑热点' : '新增热点'}
                </div>
                <Field label="热点标题">
                  <Input
                    value={form.title}
                    onChange={event =>
                      setForm(current => ({ ...current, title: event.target.value }))
                    }
                    placeholder="展示在热榜里的标题"
                    required
                  />
                </Field>
                <Field label="搜索关键词" hint="用户点击该热点时，会用这个关键词进入站内搜索。">
                  <Input
                    value={form.search_query}
                    onChange={event =>
                      setForm(current => ({ ...current, search_query: event.target.value }))
                    }
                    placeholder="用于搜索召回相关内容"
                    required
                  />
                </Field>
                <Field label="摘要">
                  <Textarea
                    value={form.summary || ''}
                    onChange={event =>
                      setForm(current => ({ ...current, summary: event.target.value }))
                    }
                    placeholder="可选，说明热点背景"
                    rows={3}
                  />
                </Field>
                <Field label="排序位" hint="从 1 开始；数值越小越靠前。">
                  <Input
                    type="number"
                    min={1}
                    value={form.rank ?? 1}
                    onChange={event =>
                      setForm(current => ({ ...current, rank: Number(event.target.value) }))
                    }
                  />
                </Field>
                <div className="flex gap-2">
                  <Button
                    type="submit"
                    className="rounded-md"
                    disabled={saveTopicMutation.isPending}
                  >
                    <Save size={15} className="mr-1" />
                    发布
                  </Button>
                  {editing && (
                    <Button
                      type="button"
                      variant="ghost"
                      className="rounded-md"
                      onClick={() => {
                        setEditing(null);
                        setForm(emptyTopic);
                      }}
                    >
                      取消
                    </Button>
                  )}
                </div>
              </form>
            </CardContent>
          </Card>

          <HotTopicPanel
            title="当前热榜"
            topics={activeTopics}
            emptyText="暂无公开热点"
            action={topic => (
              <div className="flex gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="rounded-md"
                  onClick={() => startEdit(topic)}
                >
                  编辑
                </Button>
                <IconButton title="删除" onClick={() => deleteTopicMutation.mutate(topic.id)}>
                  <Trash2 size={15} />
                </IconButton>
              </div>
            )}
          />
        </section>

        <section className="space-y-5 xl:pl-1">
          <Card className="rounded-lg">
            <CardContent className="p-4">
              <div className="space-y-4">
                <div className="flex flex-col gap-3 border-b pb-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 font-semibold">
                      <Bot size={17} className="text-primary" />
                      LLM生成配置
                    </div>
                    <Switch
                      checked={agentEnabled}
                      onChange={checked =>
                        setSettingsForm(current => ({ ...current, agent_enabled: checked }))
                      }
                    />
                    {settingsDirty && (
                      <span className="text-xs text-muted-foreground">
                        {saveSettingsMutation.isPending ? '保存中' : '待自动保存'}
                      </span>
                    )}
                  </div>
                  <Button
                    type="button"
                    className="rounded-md"
                    onClick={startGenerate}
                    disabled={!agentEnabled || isGenerating}
                  >
                    {isGenerating ? (
                      <Loader2 size={15} className="mr-1 animate-spin" />
                    ) : (
                      <Play size={15} className="mr-1" />
                    )}
                    {isGenerating ? '生成中' : '立即生成'}
                  </Button>
                </div>

                {generationError && (
                  <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                    {generationError}
                  </div>
                )}

                <fieldset
                  disabled={!agentEnabled}
                  className={cn(
                    'space-y-3 transition-opacity',
                    !agentEnabled && 'pointer-events-none opacity-45 grayscale'
                  )}
                >
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="发布策略">
                      <select
                        value={publishPolicy}
                        onChange={event =>
                          setSettingsForm(current => ({
                            ...current,
                            publish_policy: event.target.value as HotTopicPublishPolicy,
                          }))
                        }
                        className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                      >
                        <option value="draft">生成草稿，人工审批</option>
                        <option value="auto">自动发布</option>
                      </select>
                    </Field>
                    <Field label="生成间隔" hint="单位：分钟。180 表示每 3 小时生成一次。">
                      <Input
                        type="number"
                        value={settingsForm.agent_interval_minutes ?? 180}
                        onChange={event =>
                          setSettingsForm(current => ({
                            ...current,
                            agent_interval_minutes: Number(event.target.value),
                          }))
                        }
                      />
                    </Field>
                    <Field label="历史热榜注入次数" hint="默认 3；填 0 表示不注入历史热榜。">
                      <Input
                        type="number"
                        min={0}
                        max={10}
                        value={settingsForm.history_limit ?? 3}
                        onChange={event =>
                          setSettingsForm(current => ({
                            ...current,
                            history_limit: Number(event.target.value),
                          }))
                        }
                      />
                    </Field>
                    <Field label="最大对话轮数" hint="默认 6；最后一轮会要求模型提交结果。">
                      <Input
                        type="number"
                        min={1}
                        max={20}
                        value={settingsForm.max_llm_rounds ?? 6}
                        onChange={event =>
                          setSettingsForm(current => ({
                            ...current,
                            max_llm_rounds: Number(event.target.value),
                          }))
                        }
                      />
                    </Field>
                    <Field label="模型名称">
                      <Input
                        value={settingsForm.llm_model_name || ''}
                        onChange={event =>
                          setSettingsForm(current => ({
                            ...current,
                            llm_model_name: event.target.value,
                          }))
                        }
                        placeholder="例如 gpt-4.1-mini"
                      />
                    </Field>
                  </div>
                  <Field label="Base URL">
                    <Input
                      value={settingsForm.llm_base_url || ''}
                      onChange={event =>
                        setSettingsForm(current => ({
                          ...current,
                          llm_base_url: event.target.value,
                        }))
                      }
                      placeholder="OpenAI-compatible API 地址"
                    />
                  </Field>
                  <Field label="API Key">
                    <Input
                      value={settingsForm.llm_api_key || ''}
                      onChange={event =>
                        setSettingsForm(current => ({
                          ...current,
                          llm_api_key: event.target.value,
                        }))
                      }
                      placeholder="留空不修改，显示星号时会保留旧值"
                      type="password"
                    />
                  </Field>
                  <label className="flex h-9 items-center gap-2 rounded-md border border-input px-3 text-sm">
                    <input
                      type="checkbox"
                      checked={!!settingsForm.web_search_enabled}
                      onChange={event =>
                        setSettingsForm(current => ({
                          ...current,
                          web_search_enabled: event.target.checked,
                        }))
                      }
                    />
                    启用联网搜索
                  </label>
                  <Field label="Tavily API Key" hint="仅在启用联网搜索时使用。">
                    <Input
                      value={settingsForm.tavily_api_key || ''}
                      onChange={event =>
                        setSettingsForm(current => ({
                          ...current,
                          tavily_api_key: event.target.value,
                        }))
                      }
                      placeholder="留空不修改，显示星号时会保留旧值"
                      type="password"
                    />
                  </Field>
                </fieldset>
              </div>
            </CardContent>
          </Card>

          {publishPolicy === 'draft' && (
            <HotTopicPanel
              title="LLM 生成待审批"
              topics={agentDrafts}
              emptyText="暂无待审批草稿"
              action={topic => (
                <div className="flex gap-1">
                  <IconButton
                    title="通过并发布"
                    onClick={() => publishTopicMutation.mutate(topic.id)}
                  >
                    <Check size={15} />
                  </IconButton>
                  <IconButton title="删除" onClick={() => deleteTopicMutation.mutate(topic.id)}>
                    <Trash2 size={15} />
                  </IconButton>
                </div>
              )}
            />
          )}

          <PromptTemplatePanel
            prompt={promptConfig}
            draft={promptValue}
            isLoading={isPromptLoading}
            isDirty={isPromptDirty}
            isSaving={updatePromptMutation.isPending}
            isResetting={resetPromptMutation.isPending}
            onDraftChange={setPromptDraft}
            onCancel={() => setPromptDraft(promptConfig?.value ?? '')}
            onReset={() => resetPromptMutation.mutate()}
            onSave={() => updatePromptMutation.mutate(promptValue)}
          />
        </section>
      </div>
    </div>
  );
}

function HotTopicPanel({
  title,
  topics,
  emptyText,
  action,
}: {
  title: string;
  topics: HotTopic[];
  emptyText: string;
  action: (topic: HotTopic) => ReactNode;
}) {
  return (
    <Card className="overflow-hidden rounded-lg">
      <CardContent className="p-0">
        <div className="flex items-center gap-2 border-b border-border/50 p-4">
          <Flame className="h-5 w-5 text-orange-500" />
          <h2 className="font-semibold">{title}</h2>
        </div>
        {topics.length > 0 ? (
          <div className="divide-y divide-border/50">
            {topics.map((topic, index) => (
              <div key={topic.id} className="flex gap-3 p-4 transition-colors hover:bg-muted/40">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded bg-muted text-sm font-semibold text-muted-foreground">
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex min-w-0 items-start justify-between gap-3">
                    <Link
                      to={`/search?type=content&q=${encodeURIComponent(topic.search_query)}`}
                      className="min-w-0 flex-1 hover:text-primary"
                    >
                      <p className="truncate font-medium">{topic.title}</p>
                      {topic.summary && (
                        <p className="mt-1 whitespace-pre-wrap break-words text-sm text-muted-foreground">
                          {topic.summary}
                        </p>
                      )}
                      <p className="mt-2 inline-flex items-center gap-1 text-xs text-muted-foreground">
                        <Search className="h-3.5 w-3.5" />
                        {topic.search_query}
                      </p>
                    </Link>
                    <div className="shrink-0">{action(topic)}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-12 text-center text-muted-foreground">{emptyText}</div>
        )}
      </CardContent>
    </Card>
  );
}

function PromptTemplatePanel({
  prompt,
  draft,
  isLoading,
  isDirty,
  isSaving,
  isResetting,
  onDraftChange,
  onCancel,
  onReset,
  onSave,
}: {
  prompt?: HotTopicPromptConfig;
  draft: string;
  isLoading: boolean;
  isDirty: boolean;
  isSaving: boolean;
  isResetting: boolean;
  onDraftChange: (value: string) => void;
  onCancel: () => void;
  onReset: () => void;
  onSave: () => void;
}) {
  if (isLoading) {
    return (
      <Card>
        <CardContent className="space-y-3 p-4">
          <div className="h-4 w-1/4 animate-pulse rounded bg-muted" />
          <div className="h-36 animate-pulse rounded bg-muted" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="space-y-4 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <ScrollText size={18} className="text-muted-foreground" />
              <h2 className="text-lg font-semibold">{prompt?.name ?? '热榜生成提示词'}</h2>
              {isDirty && <Badge variant="secondary">未保存</Badge>}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Button
              variant="outline"
              onClick={onCancel}
              disabled={!isDirty || isSaving || isResetting}
            >
              取消
            </Button>
            <Button variant="outline" onClick={onReset} disabled={isSaving || isResetting}>
              <RotateCcw size={15} className="mr-1.5" />
              恢复默认
            </Button>
            <Button onClick={onSave} disabled={!draft.trim() || !isDirty || isSaving}>
              <Save size={15} className="mr-1.5" />
              保存
            </Button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Braces size={14} />
          {promptPlaceholders.map(placeholder => (
            <Badge
              key={placeholder.token}
              variant="outline"
              className="font-mono"
              title={placeholder.description}
            >
              {placeholder.token}
            </Badge>
          ))}
        </div>

        <Textarea
          value={draft}
          onChange={event => onDraftChange(event.target.value)}
          className="min-h-[340px] font-mono leading-relaxed"
          spellCheck={false}
        />
      </CardContent>
    </Card>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block min-w-0">
      <span className="mb-1 block text-xs font-medium text-muted-foreground">{label}</span>
      {children}
      {hint && (
        <span className="mt-1 block text-[11px] leading-4 text-muted-foreground">{hint}</span>
      )}
    </label>
  );
}

function Switch({ checked, onChange }: { checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      className={cn(
        'relative h-6 w-11 rounded-full transition-colors',
        checked ? 'bg-zinc-950' : 'bg-muted'
      )}
      onClick={() => onChange(!checked)}
    >
      <span
        className={cn(
          'absolute left-1 top-1 h-4 w-4 rounded-full bg-white shadow transition-transform',
          checked ? 'translate-x-5' : 'translate-x-0'
        )}
      />
    </button>
  );
}

function Badge({
  variant = 'secondary',
  className,
  children,
  title,
}: {
  variant?: 'secondary' | 'outline';
  className?: string;
  children: ReactNode;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex h-6 items-center rounded-md px-2 text-xs font-medium',
        variant === 'outline'
          ? 'border border-border bg-background text-muted-foreground'
          : 'bg-muted text-muted-foreground',
        className
      )}
    >
      {children}
    </span>
  );
}

function IconButton({
  title,
  onClick,
  children,
}: {
  title: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className="rounded-md"
      title={title}
      aria-label={title}
      onClick={onClick}
    >
      {children}
    </Button>
  );
}
