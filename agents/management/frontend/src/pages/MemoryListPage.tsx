import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { memoryApi, agentApi } from '@/shared/api/modules';
import {
  Button, Input, Textarea, Card, CardContent,
  Badge, Skeleton, Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter, DialogDescription,
} from '@/shared/components/ui';
import { Upload, Loader2, Brain, CheckCircle, AlertCircle } from 'lucide-react';

export default function MemoryListPage() {
  const navigate = useNavigate();
  const [batchDialogOpen, setBatchDialogOpen] = useState(false);

  const { data: agents, isLoading: agentsLoading } = useQuery({
    queryKey: ['agents'],
    queryFn: () => agentApi.list(0, 200),
  });

  const { data: allMemories } = useQuery({
    queryKey: ['memories-all'],
    queryFn: () => memoryApi.list(0, 10000),
  });

  const memoryCountByOwner: Record<number, number> = {};
  allMemories?.items.forEach((m) => {
    memoryCountByOwner[m.owner_id] = (memoryCountByOwner[m.owner_id] ?? 0) + 1;
  });

  if (agentsLoading) {
    return (
      <div>
        <h1 className="text-2xl font-bold mb-6">记忆管理</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">记忆管理</h1>
        <Button onClick={() => setBatchDialogOpen(true)}>
          <Upload size={16} className="mr-1" /> 批量上传记忆
        </Button>
      </div>

      <p className="text-sm text-muted-foreground mb-4">
        点击角色卡片进入记忆管理，或点击上方按钮批量上传记忆
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {agents?.items
          .filter((a) => a.app_platform_user_id)
          .map((agent) => (
            <Card
              key={agent.id}
              className="cursor-pointer hover:border-primary transition-colors"
              onClick={() => navigate(`/memories/${agent.app_platform_user_id}`)}
            >
              <CardContent className="p-5">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-lg">{agent.name}</h3>
                    <div className="flex items-center gap-2 mt-2">
                      <Brain size={14} className="text-muted-foreground" />
                      <span className="text-sm text-muted-foreground">
                        {memoryCountByOwner[agent.app_platform_user_id!] ?? 0} 条记忆
                      </span>
                    </div>
                    {agent.personal_signature && (
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
                        {agent.personal_signature}
                      </p>
                    )}
                  </div>
                  <Badge variant="outline">点击进入</Badge>
                </div>
              </CardContent>
            </Card>
          ))}
      </div>

      {agents?.items.filter((a) => a.app_platform_user_id).length === 0 && (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            暂无角色配置
          </CardContent>
        </Card>
      )}

      <BatchUploadDialog
        open={batchDialogOpen}
        onOpenChange={setBatchDialogOpen}
        agents={agents?.items ?? []}
      />
    </div>
  );
}

function BatchUploadDialog({
  open,
  onOpenChange,
  agents,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agents: Array<{ id: number; name: string; app_platform_user_id: number | null; personality_prompt?: string }>;
}) {
  const queryClient = useQueryClient();
  const [selectedOwnerIds, setSelectedOwnerIds] = useState<number[]>([]);
  const [content, setContent] = useState('');
  const [semanticTime, setSemanticTime] = useState('');
  const [coefficient, setCoefficient] = useState(0.85);
  const [chunkMode, setChunkMode] = useState<'auto' | 'llm'>('auto');
  const [error, setError] = useState('');

  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<{ current: number; total: number; currentAgent: string; status: 'success' | 'error' | 'pending' } | null>(null);

  const toggleAgent = (agentId: number) => {
    setSelectedOwnerIds((prev) =>
      prev.includes(agentId) ? prev.filter((id) => id !== agentId) : [...prev, agentId]
    );
  };

  const selectAll = () => {
    const ids = agents
      .filter((a) => a.app_platform_user_id)
      .map((a) => a.app_platform_user_id!);
    setSelectedOwnerIds(ids);
  };

  const deselectAll = () => {
    setSelectedOwnerIds([]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (selectedOwnerIds.length === 0) { setError('请至少选择一个角色'); return; }
    if (!content.trim()) { setError('请输入记忆内容'); return; }
    if (chunkMode === 'auto' && !semanticTime) { setError('自动分块必须选择记忆发生时间'); return; }
    if (chunkMode === 'llm' && !agents.some((a) => a.app_platform_user_id && selectedOwnerIds.includes(a.app_platform_user_id) && a.personality_prompt?.trim())) {
      setError('LLM 分块模式下，至少一个被选角色需要配置个性提示词');
      return;
    }

    setUploading(true);
    setProgress({ current: 0, total: selectedOwnerIds.length, currentAgent: '', status: 'pending' });

    const results: { ownerId: number; name: string; success: boolean; error?: string }[] = [];

    // 顺序处理每个角色，避免LLM API并发压力
    for (let i = 0; i < selectedOwnerIds.length; i++) {
      const ownerId = selectedOwnerIds[i];
      const agent = agents.find((a) => a.app_platform_user_id === ownerId);
      const agentName = agent?.name ?? `User-${ownerId}`;

      setProgress({ current: i + 1, total: selectedOwnerIds.length, currentAgent: agentName, status: 'pending' });

      const payload: Record<string, unknown> = {
        owner_id: ownerId,
        content: content.trim(),
        chunk_mode: chunkMode,
      };

      if (chunkMode === 'auto') {
        payload.semantic_time = semanticTime;
        payload.memory_coefficient = coefficient;
      } else {
        if (agent?.personality_prompt?.trim()) {
          payload.personality_prompt = agent.personality_prompt.trim();
        } else {
          results.push({ ownerId, name: agentName, success: false, error: '未配置个性提示词' });
          continue;
        }
        if (semanticTime) payload.semantic_time = semanticTime;
        payload.memory_coefficient = coefficient;
      }

      try {
        await memoryApi.uploadSingle(payload);
        results.push({ ownerId, name: agentName, success: true });
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : '上传失败';
        results.push({ ownerId, name: agentName, success: false, error: msg });
      }
    }

    const successCount = results.filter((r) => r.success).length;
    setProgress({ current: selectedOwnerIds.length, total: selectedOwnerIds.length, currentAgent: `完成 ${successCount}/${selectedOwnerIds.length}`, status: 'success' });

    // 等待2秒让用户看到结果
    await new Promise((resolve) => setTimeout(resolve, 2000));

    queryClient.invalidateQueries({ queryKey: ['memories-all'] });
    setUploading(false);
    setProgress(null);
    onOpenChange(false);
    setSelectedOwnerIds([]);
    setContent('');
    setSemanticTime('');
    setCoefficient(0.85);
    setChunkMode('auto');
    setError('');
  };

  return (
    <Dialog open={open} onOpenChange={uploading ? () => {} : onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>批量上传记忆</DialogTitle>
          <DialogDescription>
            将同一份文档分块后上传到多个角色的记忆库
          </DialogDescription>
        </DialogHeader>

        {uploading && progress ? (
          <div className="py-8 space-y-4">
            <div className="flex items-center gap-3">
              {progress.status === 'pending' && <Loader2 size={20} className="animate-spin text-primary" />}
              {progress.status === 'success' && <CheckCircle size={20} className="text-green-500" />}
              {progress.status === 'error' && <AlertCircle size={20} className="text-destructive" />}
              <div>
                <p className="font-medium">正在处理: {progress.currentAgent}</p>
                <p className="text-sm text-muted-foreground">
                  进度: {progress.current} / {progress.total}
                </p>
              </div>
            </div>
            <div className="w-full bg-muted rounded-full h-2">
              <div
                className="bg-primary h-2 rounded-full transition-all"
                style={{ width: `${(progress.current / progress.total) * 100}%` }}
              />
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="space-y-4 py-4 max-h-[60vh] overflow-y-auto pr-2">
              {error && (
                <div className="p-3 text-sm text-destructive bg-destructive/10 rounded-lg">{error}</div>
              )}

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium">选择角色 *</label>
                  <div className="flex gap-2">
                    <Button type="button" variant="ghost" size="sm" onClick={selectAll}>全选</Button>
                    <Button type="button" variant="ghost" size="sm" onClick={deselectAll}>取消</Button>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto p-2 border rounded-md">
                  {agents
                    .filter((a) => a.app_platform_user_id)
                    .map((a) => (
                      <label
                        key={a.app_platform_user_id}
                        className="flex items-center gap-2 p-2 rounded hover:bg-muted cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={selectedOwnerIds.includes(a.app_platform_user_id!)}
                          onChange={() => toggleAgent(a.app_platform_user_id!)}
                          className="accent-primary"
                        />
                        <span className="text-sm">{a.name}</span>
                      </label>
                    ))}
                </div>
                <p className="text-xs text-muted-foreground">已选择 {selectedOwnerIds.length} 个角色</p>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">记忆内容 *</label>
                <Textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="粘贴需要分块的记忆文本..."
                  className="min-h-24"
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">分块模式</label>
                <select
                  value={chunkMode}
                  onChange={(e) => setChunkMode(e.target.value as 'auto' | 'llm')}
                  className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                >
                  <option value="auto">自动分块（512 tokens, 50 重叠）</option>
                  <option value="llm">LLM 智能分块（使用角色个性提示词）</option>
                </select>
              </div>

              {chunkMode === 'auto' && (
                <>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">记忆发生时间 *</label>
                    <Input
                      type="datetime-local"
                      value={semanticTime}
                      onChange={(e) => setSemanticTime(e.target.value)}
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium">记忆系数 (0.0 - 1.0)</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      max="1"
                      value={coefficient}
                      onChange={(e) => setCoefficient(Number(e.target.value))}
                      className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                    />
                  </div>
                </>
              )}

              {chunkMode === 'llm' && (
                <>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">记忆发生时间（可选）</label>
                    <input
                      type="datetime-local"
                      value={semanticTime}
                      onChange={(e) => setSemanticTime(e.target.value)}
                      className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium">记忆系数 (0.0 - 1.0)</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      max="1"
                      value={coefficient}
                      onChange={(e) => setCoefficient(Number(e.target.value))}
                      className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                    />
                  </div>

                  <div className="p-3 text-xs text-muted-foreground bg-muted rounded-md">
                    <p>LLM 智能分块将使用每个角色的个性提示词进行第一人称分块。</p>
                    <p className="mt-1">未配置个性提示词的角色将被跳过。</p>
                  </div>
                </>
              )}
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
              <Button type="submit" disabled={uploading}>
                {uploading ? <Loader2 size={16} className="mr-1 animate-spin" /> : null}
                上传
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
