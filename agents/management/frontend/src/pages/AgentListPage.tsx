import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { agentApi } from '@/shared/api/modules';
import {
  Button, Input, Card, CardContent,
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter, DialogDescription, Skeleton,
} from '@/shared/components/ui';
import {
  Plus, Search, Eye, Edit, Trash2, Upload, Loader2, Play, Square,
} from 'lucide-react';
import { ImportDialog } from '@/features/agents/components/ImportDialog';
import { formatDate } from '@/shared/lib/format';

function formatLastLogin(value: string | null): string {
  return value ? formatDate(value) : '未登录';
}

export default function AgentListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [showImport, setShowImport] = useState(false);
  const [deleteAgentId, setDeleteAgentId] = useState<number | null>(null);
  const [stoppingId, setStoppingId] = useState<number | null>(null);
  const [startingId, setStartingId] = useState<number | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [showBatchDelete, setShowBatchDelete] = useState(false);
  const [batchProcessing, setBatchProcessing] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['agents'],
    queryFn: () => agentApi.list(0, 1000),
  });

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

  const filtered = data?.items.filter(
    (a) => a.name.toLowerCase().includes(search.toLowerCase()) ||
           a.username.toLowerCase().includes(search.toLowerCase())
  ) ?? [];

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
          <Button variant="outline" onClick={() => setShowImport(true)}>
            <Upload size={16} className="mr-1" /> 批量导入
          </Button>
          <Button onClick={() => navigate('/agents/new')}>
            <Plus size={16} className="mr-1" /> 创建角色
          </Button>
        </div>
      </div>

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
      <Card className="mb-6">
        <CardContent className="p-4">
          <div className="flex h-10 items-center gap-3">
            <Search size={18} className="shrink-0 text-muted-foreground" />
            <Input
              placeholder="搜索角色名称或用户名..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-10 max-w-md"
            />
          </div>
        </CardContent>
      </Card>

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
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">每月登录</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">ID</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">最后登录时间</th>
                    <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((agent) => (
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
                      <td className="py-3 px-4 text-sm tabular-nums">{agent.monthly_logins}</td>
                      <td className="py-3 px-4 text-sm">{agent.id}</td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {formatLastLogin(agent.last_login_at)}
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
                          {agent.is_active ? (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleStop(agent.id)}
                              disabled={stoppingId === agent.id}
                              title="停止"
                              className="text-orange-600 hover:text-orange-600"
                            >
                              {stoppingId === agent.id ? (
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
                              disabled={startingId === agent.id}
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
                            onClick={() => setDeleteAgentId(agent.id)}
                            title="删除"
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 size={16} />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
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

      {/* Import dialog */}
      <ImportDialog open={showImport} onOpenChange={setShowImport} />
    </div>
  );
}
