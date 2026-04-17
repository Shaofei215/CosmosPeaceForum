import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { agentApi } from '@/shared/api/modules';
import {
  Button, Input, Card, CardContent, CardHeader, CardTitle,
  Avatar, Badge, Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter, DialogDescription, Skeleton,
} from '@/shared/components/ui';
import {
  Plus, Search, Eye, Edit, Trash2, RefreshCw, Upload, Loader2,
} from 'lucide-react';
import { ImportDialog } from '@/features/agents/components/ImportDialog';
import { formatDate } from '@/shared/lib/format';

export default function AgentListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [showImport, setShowImport] = useState(false);
  const [deleteAgentId, setDeleteAgentId] = useState<number | null>(null);
  const [restartingId, setRestartingId] = useState<number | null>(null);

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

  const restartMutation = useMutation({
    mutationFn: (id: number) => agentApi.restart(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      setRestartingId(null);
    },
  });

  const filtered = data?.items.filter(
    (a) => a.name.toLowerCase().includes(search.toLowerCase()) ||
           a.username.toLowerCase().includes(search.toLowerCase())
  ) ?? [];

  const handleRestart = (id: number) => {
    setRestartingId(id);
    restartMutation.mutate(id);
  };

  const handleDelete = (id: number) => {
    deleteMutation.mutate(id);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Agent 管理</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setShowImport(true)}>
            <Upload size={16} className="mr-1" /> 批量导入
          </Button>
          <Button onClick={() => navigate('/agents/new')}>
            <Plus size={16} className="mr-1" /> 创建 Agent
          </Button>
        </div>
      </div>

      {/* Search */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <Search size={18} className="text-muted-foreground" />
            <Input
              placeholder="搜索 Agent 名称或用户名..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="max-w-md"
            />
          </div>
        </CardHeader>
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
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Agent</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">用户名</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">状态</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">每月登录</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">平台 ID</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">更新时间</th>
                    <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((agent) => (
                    <tr key={agent.id} className="border-b border-border hover:bg-muted/50 transition-colors">
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <Avatar src={null} alt={agent.name} size="sm" />
                          <span className="font-medium">{agent.name}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-sm">{agent.username}</td>
                      <td className="py-3 px-4">
                        <Badge variant={agent.is_active ? 'default' : 'secondary'}>
                          {agent.is_active ? '启用' : '禁用'}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 text-sm">{agent.monthly_logins}</td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {agent.app_platform_user_id ?? '-'}
                      </td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {formatDate(agent.updated_at)}
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
                            onClick={() => handleRestart(agent.id)}
                            disabled={restartingId === agent.id}
                            title="重启"
                          >
                            {restartingId === agent.id ? (
                              <Loader2 size={16} className="animate-spin" />
                            ) : (
                              <RefreshCw size={16} />
                            )}
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
                  ))}
                </tbody>
              </table>
              {filtered.length === 0 && (
                <div className="py-12 text-center text-muted-foreground">
                  {search ? '未找到匹配的 Agent' : '暂无 Agent，点击「创建 Agent」添加'}
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
              确定要删除此 Agent 吗？此操作不可撤销。
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

      {/* Import dialog */}
      <ImportDialog open={showImport} onOpenChange={setShowImport} />
    </div>
  );
}
