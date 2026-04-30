import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { memoryApi, agentApi } from '@/shared/api/modules';
import type { AgentConfig, MemoryUploadRequest } from '@/shared/types/api';
import {
  Button, Input, Textarea, Card, CardContent,
  Badge, Skeleton, Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter, DialogDescription,
} from '@/shared/components/ui';
import { Upload, Loader2, Brain, CheckCircle, AlertCircle, Clock } from 'lucide-react';

type UploadResult = {
  ownerId: number;
  name: string;
  success: boolean;
  message?: string;
};

function getErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === 'object' && err !== null && 'message' in err) {
    return String((err as { message?: unknown }).message ?? '上传失败');
  }
  return '上传失败';
}

function formatTimestamp(ts: number): string {
  if (!ts || ts < 1000000) return 'N/A';
  return new Date(ts * 1000).toLocaleString('zh-CN');
}

export default function MemoryListPage() {
  const navigate = useNavigate();
  const [batchDialogOpen, setBatchDialogOpen] = useState(false);

  const { data: agents, isLoading: agentsLoading } = useQuery({
    queryKey: ['agents'],
    queryFn: () => agentApi.list(0, 500),
  });

  const { data: memoryOwners, isLoading: ownersLoading } = useQuery({
    queryKey: ['memory-owners'],
    queryFn: () => memoryApi.listOwners(),
  });

  const configuredAgents = agents?.items.filter((a) => a.app_platform_user_id) ?? [];
  const totalMemories = memoryOwners?.items.reduce((sum, owner) => sum + owner.memory_count, 0) ?? 0;

  if (agentsLoading || ownersLoading) {
    return (
      <div>
        <h1 className="text-2xl font-bold mb-6">记忆管理</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold">记忆管理</h1>
          <p className="text-sm text-muted-foreground mt-1">
            当前记忆库共有 {memoryOwners?.total ?? 0} 个 owner，{totalMemories} 条记忆
          </p>
        </div>
        <Button onClick={() => setBatchDialogOpen(true)}>
          <Upload size={16} className="mr-1" /> 批量上传记忆
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {memoryOwners?.items.map((owner) => (
          <Card
            key={owner.owner_id}
            className="cursor-pointer hover:border-primary transition-colors"
            onClick={() => navigate(`/memories/${owner.owner_id}`)}
          >
            <CardContent className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-semibold text-lg truncate">{owner.owner_username}</h3>
                  <div className="flex items-center gap-2 mt-2">
                    <Brain size={14} className="text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">{owner.memory_count} 条记忆</span>
                  </div>
                  <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                    <Clock size={12} />
                    <span>最近: {formatTimestamp(owner.latest_semantic_timestamp || owner.latest_system_timestamp)}</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">owner_id: {owner.owner_id}</p>
                </div>
                <Badge variant={owner.has_agent_config ? 'outline' : 'secondary'}>
                  {owner.has_agent_config ? 'Agent' : '无配置'}
                </Badge>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {memoryOwners?.items.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            记忆库暂无记录，可通过批量上传或进入指定 owner 页面添加
          </CardContent>
        </Card>
      )}

      <BatchUploadDialog
        open={batchDialogOpen}
        onOpenChange={setBatchDialogOpen}
        agents={configuredAgents}
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
  agents: Array<Pick<AgentConfig, 'id' | 'name' | 'app_platform_user_id' | 'personality_prompt'>>;
}) {
  const queryClient = useQueryClient();
  const [selectedOwnerIds, setSelectedOwnerIds] = useState<number[]>([]);
  const [content, setContent] = useState('');
  const [semanticTime, setSemanticTime] = useState('');
  const [coefficient, setCoefficient] = useState(0.85);
  const [chunkMode, setChunkMode] = useState<'auto' | 'llm'>('auto');
  const [error, setError] = useState('');
  const [uploadResults, setUploadResults] = useState<UploadResult[]>([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<{
    current: number;
    total: number;
    currentAgent: string;
    status: 'success' | 'error' | 'pending';
  } | null>(null);

  const toggleAgent = (agentId: number) => {
    setSelectedOwnerIds((prev) =>
      prev.includes(agentId) ? prev.filter((id) => id !== agentId) : [...prev, agentId]
    );
  };

  const selectAll = () => {
    setSelectedOwnerIds(agents.map((a) => a.app_platform_user_id!));
  };

  const resetForm = () => {
    setSelectedOwnerIds([]);
    setContent('');
    setSemanticTime('');
    setCoefficient(0.85);
    setChunkMode('auto');
    setError('');
    setUploadResults([]);
    setProgress(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setUploadResults([]);

    if (selectedOwnerIds.length === 0) { setError('请至少选择一个角色'); return; }
    if (!content.trim()) { setError('请输入记忆内容'); return; }
    if (chunkMode === 'auto' && !semanticTime) { setError('自动分块必须选择记忆发生时间'); return; }
    if (chunkMode === 'llm' && !agents.some((a) => selectedOwnerIds.includes(a.app_platform_user_id!) && a.personality_prompt?.trim())) {
      setError('LLM 分块模式下，至少一个被选角色需要配置个性提示词');
      return;
    }

    setUploading(true);
    setProgress({ current: 0, total: selectedOwnerIds.length, currentAgent: '准备上传', status: 'pending' });

    const results: UploadResult[] = [];

    for (let i = 0; i < selectedOwnerIds.length; i++) {
      const ownerId = selectedOwnerIds[i];
      const agent = agents.find((a) => a.app_platform_user_id === ownerId);
      const agentName = agent?.name ?? `User-${ownerId}`;

      setProgress({ current: i + 1, total: selectedOwnerIds.length, currentAgent: agentName, status: 'pending' });

      const payload: MemoryUploadRequest = {
        owner_id: ownerId,
        content: content.trim(),
        chunk_mode: chunkMode,
        memory_coefficient: coefficient,
      };

      if (chunkMode === 'auto') {
        payload.semantic_time = semanticTime;
      } else {
        if (!agent?.personality_prompt?.trim()) {
          results.push({ ownerId, name: agentName, success: false, message: '未配置个性提示词' });
          setUploadResults([...results]);
          continue;
        }
        payload.personality_prompt = agent.personality_prompt.trim();
        if (semanticTime) payload.semantic_time = semanticTime;
      }

      try {
        const response = await memoryApi.uploadSingle(payload);
        results.push({ ownerId, name: agentName, success: true, message: response.message });
      } catch (err: unknown) {
        results.push({ ownerId, name: agentName, success: false, message: getErrorMessage(err) });
      }
      setUploadResults([...results]);
    }

    const successCount = results.filter((r) => r.success).length;
    const hasFailures = successCount !== selectedOwnerIds.length;
    setProgress({
      current: selectedOwnerIds.length,
      total: selectedOwnerIds.length,
      currentAgent: `完成 ${successCount}/${selectedOwnerIds.length}`,
      status: hasFailures ? 'error' : 'success',
    });
    setUploading(false);
    queryClient.invalidateQueries({ queryKey: ['memory-owners'] });
    queryClient.invalidateQueries({ queryKey: ['memories-all'] });
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (uploading) return;
        onOpenChange(nextOpen);
        if (!nextOpen) resetForm();
      }}
    >
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>批量上传记忆</DialogTitle>
          <DialogDescription>
            将同一份文档分块后上传到多个角色的记忆库
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4 max-h-[60vh] overflow-y-auto pr-2">
            {error && (
              <div className="p-3 text-sm text-destructive bg-destructive/10 rounded-lg">{error}</div>
            )}

            {progress && (
              <div className="p-3 border rounded-md space-y-3">
                <div className="flex items-center gap-3">
                  {progress.status === 'pending' && <Loader2 size={20} className="animate-spin text-primary" />}
                  {progress.status === 'success' && <CheckCircle size={20} className="text-green-500" />}
                  {progress.status === 'error' && <AlertCircle size={20} className="text-destructive" />}
                  <div>
                    <p className="font-medium">处理状态: {progress.currentAgent}</p>
                    <p className="text-sm text-muted-foreground">
                      进度: {progress.current} / {progress.total}
                    </p>
                  </div>
                </div>
                <div className="w-full bg-muted rounded-full h-2">
                  <div
                    className="bg-primary h-2 rounded-full transition-all"
                    style={{ width: `${progress.total ? (progress.current / progress.total) * 100 : 0}%` }}
                  />
                </div>
              </div>
            )}

            {uploadResults.length > 0 && (
              <div className="border rounded-md divide-y">
                {uploadResults.map((result) => (
                  <div key={result.ownerId} className="p-3 text-sm flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium">{result.name}</p>
                      <p className="text-muted-foreground">{result.message}</p>
                    </div>
                    <Badge variant={result.success ? 'outline' : 'destructive'}>
                      {result.success ? '成功' : '失败'}
                    </Badge>
                  </div>
                ))}
              </div>
            )}

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">选择角色 *</label>
                <div className="flex gap-2">
                  <Button type="button" variant="ghost" size="sm" onClick={selectAll} disabled={uploading}>全选</Button>
                  <Button type="button" variant="ghost" size="sm" onClick={() => setSelectedOwnerIds([])} disabled={uploading}>取消</Button>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto p-2 border rounded-md">
                {agents.map((a) => (
                  <label
                    key={a.app_platform_user_id}
                    className="flex items-center gap-2 p-2 rounded hover:bg-muted cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedOwnerIds.includes(a.app_platform_user_id!)}
                      onChange={() => toggleAgent(a.app_platform_user_id!)}
                      disabled={uploading}
                      className="accent-primary"
                    />
                    <span className="text-sm">{a.name || `User-${a.app_platform_user_id}`}</span>
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
                disabled={uploading}
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">分块模式</label>
              <select
                value={chunkMode}
                onChange={(e) => setChunkMode(e.target.value as 'auto' | 'llm')}
                disabled={uploading}
                className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              >
                <option value="auto">自动分块（512 tokens, 50 重叠）</option>
                <option value="llm">LLM 智能分块（使用角色个性提示词）</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">
                记忆发生时间 {chunkMode === 'auto' ? '*' : '（可选）'}
              </label>
              <Input
                type="datetime-local"
                value={semanticTime}
                onChange={(e) => setSemanticTime(e.target.value)}
                disabled={uploading}
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
                disabled={uploading}
                className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              />
            </div>

            {chunkMode === 'llm' && (
              <div className="p-3 text-xs text-muted-foreground bg-muted rounded-md">
                <p>LLM 智能分块会逐个角色处理，长文本可能需要较长时间。</p>
                <p className="mt-1">未配置个性提示词的角色将被跳过并显示为失败。</p>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                onOpenChange(false);
                resetForm();
              }}
              disabled={uploading}
            >
              关闭
            </Button>
            <Button type="submit" disabled={uploading}>
              {uploading ? <Loader2 size={16} className="mr-1 animate-spin" /> : null}
              上传
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
