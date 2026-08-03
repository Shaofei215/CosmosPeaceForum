/**
 * Agent 列表与管理页面。
 *
 * 公开平台角色登录会把 access/refresh token 一起传给登录桥，确保后续 401 可刷新。
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { agentApi, modelApi } from '@/shared/api/modules';
import { apiClient } from '@/shared/api/client';
import { openAuthenticatedSse } from '@/shared/api/authenticatedSse';
import { API_CONFIG } from '@/shared/config/api';
import {
  Button, Input, Textarea, Card, CardContent,
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter, DialogDescription, Skeleton, Badge, Label,
} from '@/shared/components/ui';
import {
  Plus, Search, Eye, Edit, Trash2, Upload, Download, Loader2, Play, Square, FileText,
  LogIn,
} from 'lucide-react';
import { ImportDialog } from '@/features/agents/components/ImportDialog';
import AgentFormPage from '@/features/agents/components/AgentForm';
import { formatDate } from '@/shared/lib/format';
import { buildAgentExportFilename, downloadBlob } from '@/shared/lib/download';
import type { AgentRuntimeStatus, AgentRuntimeStatusResponse } from '@/shared/types/api';
import { getAccessToken } from '@/features/auth/tokenStorage';

function formatLastLogin(value: string | null): string {
  return value ? formatDate(value) : '未登录';
}

function parseStatusEvent(eventName: string, data: string): AgentRuntimeStatusResponse | null {
  if (eventName !== 'status' || !data) return null;

  try {
    return JSON.parse(data) as AgentRuntimeStatusResponse;
  } catch {
    return null;
  }
}

function getErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof Error) return err.message;
  if (typeof err === 'object' && err !== null && 'message' in err) {
    return String((err as { message?: unknown }).message ?? fallback);
  }
  return fallback;
}

function getRuntimeLabel(status?: AgentRuntimeStatus) {
  if (!status) {
    return { text: '未运行', className: 'bg-muted text-muted-foreground' };
  }

  if (!status.is_alive || status.status === 'stopped') {
    return { text: '已停止', className: 'bg-muted text-muted-foreground' };
  }
  if (status.status === 'stopping') {
    return { text: '停止中', className: 'bg-orange-100 text-orange-700' };
  }
  if (status.status === 'in_session') {
    return { text: '会话中', className: 'bg-blue-100 text-blue-700' };
  }
  return { text: '运行中', className: 'bg-green-100 text-green-700' };
}

export default function AgentListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [showImport, setShowImport] = useState(false);
  const [exportError, setExportError] = useState('');
  const [showCreateAgent, setShowCreateAgent] = useState(false);
  const [deleteAgentId, setDeleteAgentId] = useState<number | null>(null);
  const [stoppingId, setStoppingId] = useState<number | null>(null);
  const [startingId, setStartingId] = useState<number | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [showBatchDelete, setShowBatchDelete] = useState(false);
  const [batchProcessing, setBatchProcessing] = useState(false);
  const [promptInjectionIds, setPromptInjectionIds] = useState<number[] | null>(null);
  const [promptInjectionText, setPromptInjectionText] = useState('');
  const [promptInjectionError, setPromptInjectionError] = useState('');
  const [appLoginAgentId, setAppLoginAgentId] = useState<number | null>(null);
  const [appLoginError, setAppLoginError] = useState('');
  const [runtimeStatuses, setRuntimeStatuses] = useState<Map<number, AgentRuntimeStatus>>(
    new Map(),
  );
  const [schedulerOnline, setSchedulerOnline] = useState(true);

  const { data, isLoading } = useQuery({
    queryKey: ['agents'],
    queryFn: () => agentApi.list(0, 1000),
  });

  const { data: models } = useQuery({
    queryKey: ['models'],
    queryFn: modelApi.list,
  });

  useEffect(() => {
    if (!getAccessToken()) return undefined;

    const controller = new AbortController();
    let retryTimer: number | undefined;

    const scheduleReconnect = () => {
      setSchedulerOnline(false);
      retryTimer = window.setTimeout(connect, 2000);
    };

    async function connect() {
      try {
        await openAuthenticatedSse({
          url: `${API_CONFIG.BASE_URL}/agents/status-stream`,
          signal: controller.signal,
          getAccessToken,
          refreshAccessToken: () => apiClient.refreshAccessToken(),
          onMessage: (message) => {
            const event = parseStatusEvent(message.event, message.data);
            if (!event) return;

            setSchedulerOnline(event.scheduler_online);
            setRuntimeStatuses(new Map(event.agents.map((item) => [item.agent_id, item])));
          },
        });

        if (!controller.signal.aborted) {
          scheduleReconnect();
        }
      } catch {
        if (!controller.signal.aborted) {
          scheduleReconnect();
        }
      }
    }

    connect();

    return () => {
      controller.abort();
      if (retryTimer !== undefined) {
        window.clearTimeout(retryTimer);
      }
    };
  }, []);

  const deleteMutation = useMutation({
    mutationFn: (id: number) => agentApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      setDeleteAgentId(null);
    },
  });

  const stopMutation = useMutation({
    mutationFn: (id: number) => agentApi.stop(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      setStoppingId(null);
    },
  });

  const startMutation = useMutation({
    mutationFn: (id: number) => agentApi.start(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      setStartingId(null);
    },
  });

  const promptInjectionMutation = useMutation({
    mutationFn: ({ ids, content }: { ids: number[]; content: string }) =>
      agentApi.injectPrompt({ agent_ids: ids, content }),
    onSuccess: () => {
      setPromptInjectionIds(null);
      setPromptInjectionText('');
      setPromptInjectionError('');
      setSelectedIds(new Set());
    },
    onError: (err: unknown) => {
      setPromptInjectionError(getErrorMessage(err, '提示词注入失败，请稍后重试'));
    },
  });

  const appLoginMutation = useMutation({
    mutationFn: (id: number) => agentApi.appLogin(id),
    onSuccess: (result) => {
      setAppLoginAgentId(null);
      setAppLoginError('');

      const loginUrl = new URL('/management-login', result.social_platform_frontend_url);
      const hashParams = new URLSearchParams({
        token: result.access_token,
        refresh_token: result.refresh_token,
        redirect: `/user/${result.social_platform_user_id}`,
      });
      loginUrl.hash = hashParams.toString();
      window.location.href = loginUrl.toString();
    },
    onError: (err: unknown) => {
      setAppLoginAgentId(null);
      setAppLoginError(getErrorMessage(err, '登录 social_platform 失败，请稍后重试'));
    },
  });

  const exportMutation = useMutation({
    mutationFn: agentApi.exportAgents,
    onMutate: () => {
      setExportError('');
    },
    onSuccess: (archive) => {
      downloadBlob(archive, buildAgentExportFilename());
    },
    onError: (err: unknown) => {
      setExportError(getErrorMessage(err, '导出配置失败，请稍后重试'));
    },
  });

  const filtered = data?.items.filter(
    (a) => a.name.toLowerCase().includes(search.toLowerCase()) ||
           a.username.toLowerCase().includes(search.toLowerCase())
  ) ?? [];
  const modelById = new Map((models ?? []).map((model) => [model.id, model]));

  const isAllSelected = filtered.length > 0 && selectedIds.size === filtered.length;
  const isSomeSelected = selectedIds.size > 0 && selectedIds.size < filtered.length;

  const toggleSelectAll = () => {
    if (isAllSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filtered.map(a => a.id)));
    }
  };

  const toggleSelectOne = (id: number) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const handleStop = (id: number) => {
    setStoppingId(id);
    stopMutation.mutate(id);
  };

  const handleStart = (id: number) => {
    setStartingId(id);
    startMutation.mutate(id);
  };

  const handleDelete = (id: number) => {
    deleteMutation.mutate(id);
  };

  const handleAppLogin = (id: number) => {
    setAppLoginError('');
    setAppLoginAgentId(id);
    appLoginMutation.mutate(id);
  };

  const openPromptInjection = (ids: number[]) => {
    setPromptInjectionIds(ids);
    setPromptInjectionText('');
    setPromptInjectionError('');
  };

  const closePromptInjection = () => {
    if (promptInjectionMutation.isPending) return;
    setPromptInjectionIds(null);
    setPromptInjectionText('');
    setPromptInjectionError('');
  };

  const handlePromptInjection = () => {
    const ids = promptInjectionIds ?? [];
    const content = promptInjectionText.trim();
    if (ids.length === 0) return;
    if (!content) {
      setPromptInjectionError('请输入要注入的提示词');
      return;
    }

    promptInjectionMutation.mutate({ ids, content });
  };

  const handleBatchStart = () => {
    if (selectedIds.size === 0) return;
    setBatchProcessing(true);
    agentApi.batchStart(Array.from(selectedIds)).then(() => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      setSelectedIds(new Set());
      setBatchProcessing(false);
    }).catch(() => {
      setBatchProcessing(false);
    });
  };

  const handleBatchStop = () => {
    if (selectedIds.size === 0) return;
    setBatchProcessing(true);
    agentApi.batchStop(Array.from(selectedIds)).then(() => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      setSelectedIds(new Set());
      setBatchProcessing(false);
    }).catch(() => {
      setBatchProcessing(false);
    });
  };

  const handleBatchDelete = () => {
    if (selectedIds.size === 0) return;
    setBatchProcessing(true);
    agentApi.batchDelete(Array.from(selectedIds)).then(() => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      setSelectedIds(new Set());
      setShowBatchDelete(false);
      setBatchProcessing(false);
    }).catch(() => {
      setBatchProcessing(false);
    });
  };

  return (
    <div>
      <div className="flex flex-col gap-3 mb-6 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold">角色管理</h1>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={() => exportMutation.mutate()}
            disabled={exportMutation.isPending || isLoading || (data?.total ?? 0) === 0}
          >
            {exportMutation.isPending ? (
              <Loader2 size={16} className="mr-1 animate-spin" />
            ) : (
              <Download size={16} className="mr-1" />
            )}
            {exportMutation.isPending ? '导出中' : '导出配置'}
          </Button>
          <Button variant="outline" onClick={() => setShowImport(true)}>
            <Upload size={16} className="mr-1" /> 批量导入
          </Button>
          <Button onClick={() => setShowCreateAgent(true)}>
            <Plus size={16} className="mr-1" /> 创建角色
          </Button>
        </div>
      </div>

      {!schedulerOnline && (
        <div className="mb-4 rounded-md border border-orange-200 bg-orange-50 px-4 py-3 text-sm text-orange-700">
          Scheduler 未连接，运行状态暂不可用。
        </div>
      )}

      {appLoginError && (
        <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {appLoginError}
        </div>
      )}

      {exportError && (
        <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {exportError}
        </div>
      )}

      {selectedIds.size > 0 && (
        <Card className="mb-4 border-primary/20 bg-primary/5">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm">已选择 {selectedIds.size} 个角色</span>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={handleBatchStart}
                  disabled={batchProcessing}
                >
                  {batchProcessing ? <Loader2 size={14} className="animate-spin mr-1" /> : <Play size={14} className="mr-1" />}
                  批量启动
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleBatchStop}
                  disabled={batchProcessing}
                >
                  {batchProcessing ? <Loader2 size={14} className="animate-spin mr-1" /> : <Square size={14} className="mr-1" />}
                  批量停止
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => openPromptInjection(Array.from(selectedIds))}
                  disabled={batchProcessing}
                >
                  <FileText size={14} className="mr-1" />
                  提示词注入
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => setShowBatchDelete(true)}
                  disabled={batchProcessing}
                >
                  <Trash2 size={14} className="mr-1" />
                  批量删除
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Search */}
      <div className="relative mb-6 max-w-md">
        <Search
          size={18}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          placeholder="搜索角色名称或用户名..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground w-12">
                      <input
                        type="checkbox"
                        checked={isAllSelected}
                        ref={el => {
                          if (el) el.indeterminate = isSomeSelected;
                        }}
                        onChange={toggleSelectAll}
                        className="h-4 w-4 rounded border-gray-300"
                      />
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">角色</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">用户名</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">模型</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">每月登录</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">最后登录时间</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">运行状态</th>
                    <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((agent) => {
                    const runtime = runtimeStatuses.get(agent.id);
                    const runtimeLabel = getRuntimeLabel(runtime);
                    const isStopping = stoppingId === agent.id || runtime?.status === 'stopping';
                    const model = modelById.get(agent.model_config_id ?? -1);

                    return (
                      <tr key={agent.id} className="border-b border-border hover:bg-muted/50 transition-colors">
                        <td className="py-3 px-4">
                          <input
                            type="checkbox"
                            checked={selectedIds.has(agent.id)}
                            onChange={() => toggleSelectOne(agent.id)}
                            className="h-4 w-4 rounded border-gray-300"
                          />
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-medium">{agent.name}</span>
                        </td>
                        <td className="py-3 px-4 text-sm">{agent.username}</td>
                        <td className="py-3 px-4">
                          {model ? (
                            <Badge
                              variant="outline"
                              className="px-4"
                              style={{
                                backgroundColor: model.color,
                                borderColor: model.color,
                                color: '#FFFFFF',
                              }}
                            >
                              {model.name}
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-muted-foreground">
                              未分配
                            </Badge>
                          )}
                        </td>
                        <td className="py-3 px-4 text-sm tabular-nums">{agent.monthly_logins}</td>
                        <td className="py-3 px-4 text-sm text-muted-foreground">
                          {formatLastLogin(agent.last_login_at)}
                        </td>
                        <td className="py-3 px-4">
                          <Badge variant="outline" className={runtimeLabel.className}>
                            {runtimeLabel.text}
                          </Badge>
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => navigate(`/agents/${agent.id}`)}
                              title="查看详情"
                            >
                              <Eye size={16} />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => navigate(`/agents/${agent.id}/edit`)}
                              title="编辑"
                            >
                              <Edit size={16} />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleAppLogin(agent.id)}
                              disabled={appLoginAgentId === agent.id}
                              title="登录公开平台账号"
                              className="text-blue-600 hover:text-blue-600"
                            >
                              {appLoginAgentId === agent.id ? (
                                <Loader2 size={16} className="animate-spin" />
                              ) : (
                                <LogIn size={16} />
                              )}
                            </Button>
                            {agent.is_active ? (
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleStop(agent.id)}
                                disabled={isStopping}
                                title="停止"
                                className="text-orange-600 hover:text-orange-600"
                              >
                                {isStopping ? (
                                  <Loader2 size={16} className="animate-spin" />
                                ) : (
                                  <Square size={16} />
                                )}
                              </Button>
                            ) : (
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleStart(agent.id)}
                                disabled={startingId === agent.id || runtime?.status === 'stopping'}
                                title="启动"
                                className="text-green-600 hover:text-green-600"
                              >
                                {startingId === agent.id ? (
                                  <Loader2 size={16} className="animate-spin" />
                                ) : (
                                  <Play size={16} />
                                )}
                              </Button>
                            )}
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => openPromptInjection([agent.id])}
                              title="提示词注入"
                            >
                              <FileText size={16} />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => setDeleteAgentId(agent.id)}
                              title="删除"
                              className="text-destructive hover:text-destructive"
                            >
                              <Trash2 size={16} />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {filtered.length === 0 && (
                <div className="py-12 text-center text-muted-foreground">
                  {search ? '未找到匹配的角色' : '暂无角色，点击「创建角色」添加'}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete confirm dialog */}
      <Dialog open={deleteAgentId !== null} onOpenChange={() => setDeleteAgentId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>
              确定要删除此角色吗？此操作不可撤销。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteAgentId(null)}>取消</Button>
            <Button
              variant="destructive"
              onClick={() => deleteAgentId && handleDelete(deleteAgentId)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? '删除中...' : '删除'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Batch delete confirm dialog */}
      <Dialog open={showBatchDelete} onOpenChange={() => setShowBatchDelete(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认批量删除</DialogTitle>
            <DialogDescription>
              确定要删除选中的 {selectedIds.size} 个角色吗？此操作不可撤销。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowBatchDelete(false)}>取消</Button>
            <Button
              variant="destructive"
              onClick={handleBatchDelete}
              disabled={batchProcessing}
            >
              {batchProcessing ? '删除中...' : '删除'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Prompt injection dialog */}
      <Dialog
        open={promptInjectionIds !== null}
        onOpenChange={(open) => {
          if (!open) closePromptInjection();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>提示词注入</DialogTitle>
            <DialogDescription>
              将文本注入到选中 {promptInjectionIds?.length ?? 0} 个角色的下一次登录会话中，仅生效一次。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="prompt-injection-text">注入文本</Label>
            <Textarea
              id="prompt-injection-text"
              value={promptInjectionText}
              onChange={(e) => {
                setPromptInjectionText(e.target.value);
                if (promptInjectionError) setPromptInjectionError('');
              }}
              maxLength={8000}
              rows={8}
              placeholder="输入临时信息或操作倾向..."
              className="min-h-[180px]"
            />
            <div className="flex items-center justify-between text-xs">
              <span className="text-destructive">{promptInjectionError}</span>
              <span className="text-muted-foreground">{promptInjectionText.length}/8000</span>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={closePromptInjection}
              disabled={promptInjectionMutation.isPending}
            >
              取消
            </Button>
            <Button
              onClick={handlePromptInjection}
              disabled={promptInjectionMutation.isPending || !promptInjectionText.trim()}
            >
              {promptInjectionMutation.isPending ? (
                <Loader2 size={14} className="mr-1 animate-spin" />
              ) : (
                <FileText size={14} className="mr-1" />
              )}
              注入
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Import dialog */}
      <ImportDialog open={showImport} onOpenChange={setShowImport} />

      <Dialog open={showCreateAgent} onOpenChange={setShowCreateAgent}>
        <DialogContent className="max-h-[calc(100vh-2rem)] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>创建角色</DialogTitle>
          </DialogHeader>
          <AgentFormPage
            mode="create"
            embedded
            onCancel={() => setShowCreateAgent(false)}
            onSuccess={() => setShowCreateAgent(false)}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
