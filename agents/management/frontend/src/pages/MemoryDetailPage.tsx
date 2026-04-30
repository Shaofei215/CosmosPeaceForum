import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { memoryApi, agentApi } from '@/shared/api/modules';
import type { MemoryUploadRequest } from '@/shared/types/api';
import {
  Button, Input, Textarea, Card, CardContent,
  Badge, Skeleton, Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter, DialogDescription,
} from '@/shared/components/ui';
import { ArrowLeft, Upload, Trash2, Loader2, Clock } from 'lucide-react';

export default function MemoryDetailPage() {
  const { ownerId } = useParams<{ ownerId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const limit = 50;

  const ownerIdNum = ownerId ? Number(ownerId) : undefined;

  const { data: agent } = useQuery({
    queryKey: ['agent', ownerId],
    queryFn: () => agentApi.list(0, 200).then((res) =>
      res.items.find((a) => a.app_platform_user_id === ownerIdNum)
    ),
    enabled: !!ownerIdNum,
  });

  const { data: memories, isLoading } = useQuery({
    queryKey: ['memories', ownerId, page],
    queryFn: () => memoryApi.list(page * limit, limit, ownerIdNum),
    enabled: !!ownerIdNum,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => memoryApi.deleteMemory(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['memories', ownerId] });
      queryClient.invalidateQueries({ queryKey: ['memories-all'] });
      queryClient.invalidateQueries({ queryKey: ['memory-owners'] });
      setDeleteId(null);
    },
  });

  const clearMutation = useMutation({
    mutationFn: (id: number) => memoryApi.clearUserMemories(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['memories', ownerId] });
      queryClient.invalidateQueries({ queryKey: ['memories-all'] });
      queryClient.invalidateQueries({ queryKey: ['memory-owners'] });
    },
  });

  const totalPages = Math.ceil((memories?.total ?? 0) / limit);

  if (!ownerIdNum) {
    return <div className="text-center py-12 text-muted-foreground">无效的角色ID</div>;
  }

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <Button variant="ghost" size="icon" onClick={() => navigate('/memories')}>
          <ArrowLeft size={20} />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">
            {agent?.name ?? `User-${ownerIdNum}`}的记忆
          </h1>
          <p className="text-sm text-muted-foreground">
            共 {memories?.total ?? 0} 条记忆
          </p>
        </div>
        <Button onClick={() => setUploadDialogOpen(true)}>
          <Upload size={16} className="mr-1" /> 上传记忆
        </Button>
        {memories && memories.total > 0 && (
          <Button
            variant="outline"
            onClick={() => clearMutation.mutate(ownerIdNum)}
            disabled={clearMutation.isPending}
          >
            {clearMutation.isPending ? '清除中...' : '清空全部'}
          </Button>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : (
        <>
          <div className="space-y-4">
            {memories?.items.map((mem) => (
              <Card key={mem.id}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="secondary">
                          系数: {mem.memory_coefficient.toFixed(2)}
                        </Badge>
                      </div>
                      <p className="text-sm mt-2 whitespace-pre-wrap">{mem.content}</p>
                      {mem.semantic_timestamp > 0 && (
                        <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                          <Clock size={12} />
                          产生于: {formatTimestamp(mem.semantic_timestamp)}
                        </div>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setDeleteId(mem.id)}
                      className="text-destructive hover:text-destructive ml-4"
                    >
                      <Trash2 size={16} />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}

            {memories?.items.length === 0 && (
              <Card>
                <CardContent className="py-12 text-center text-muted-foreground">
                  暂无记忆记录，点击上方「上传记忆」添加
                </CardContent>
              </Card>
            )}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-6">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                上一页
              </Button>
              <span className="text-sm">
                {page + 1} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
              >
                下一页
              </Button>
            </div>
          )}
        </>
      )}

      <UploadDialog
        open={uploadDialogOpen}
        onOpenChange={setUploadDialogOpen}
        agent={agent}
        ownerId={ownerIdNum}
      />

      <Dialog open={deleteId !== null} onOpenChange={() => setDeleteId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>确定要删除此记忆吗？此操作不可撤销。</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteId(null)}>取消</Button>
            <Button
              variant="destructive"
              onClick={() => deleteId && deleteMutation.mutate(deleteId)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? '删除中...' : '删除'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function formatTimestamp(ts: number): string {
  if (!ts || ts < 1000000) return 'N/A';
  return new Date(ts * 1000).toLocaleString('zh-CN');
}

function UploadDialog({
  open,
  onOpenChange,
  agent,
  ownerId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agent?: { name: string; personality_prompt?: string };
  ownerId: number;
}) {
  const queryClient = useQueryClient();
  const [content, setContent] = useState('');
  const [semanticTime, setSemanticTime] = useState('');
  const [coefficient, setCoefficient] = useState(0.85);
  const [chunkMode, setChunkMode] = useState<'auto' | 'llm'>('auto');
  const [personalityPrompt, setPersonalityPrompt] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (open && agent?.personality_prompt) {
      setPersonalityPrompt(agent.personality_prompt);
    }
  }, [agent?.personality_prompt, open]);

  const uploadMutation = useMutation({
    mutationFn: (data: MemoryUploadRequest) => memoryApi.uploadSingle(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['memories', ownerId.toString()] });
      queryClient.invalidateQueries({ queryKey: ['memories-all'] });
      queryClient.invalidateQueries({ queryKey: ['memory-owners'] });
      onOpenChange(false);
      setContent('');
      setSemanticTime('');
      setCoefficient(0.85);
      setChunkMode('auto');
      setPersonalityPrompt('');
      setError('');
    },
    onError: (err: unknown) => {
      if (err instanceof Error) {
        setError(err.message);
        return;
      }
      if (typeof err === 'object' && err !== null && 'message' in err) {
        setError(String((err as { message?: unknown }).message ?? '上传失败'));
        return;
      }
      setError('上传失败');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!content.trim()) { setError('请输入记忆内容'); return; }
    if (chunkMode === 'auto' && !semanticTime) { setError('自动分块必须选择记忆发生时间'); return; }
    if (chunkMode === 'llm' && !personalityPrompt.trim()) {
      setError('LLM 分块必须填写角色个性提示词');
      return;
    }

    const payload: MemoryUploadRequest = {
      owner_id: ownerId,
      content: content.trim(),
      chunk_mode: chunkMode,
      memory_coefficient: coefficient,
    };

    if (chunkMode === 'auto') {
      payload.semantic_time = semanticTime;
    } else {
      payload.personality_prompt = personalityPrompt.trim();
      if (semanticTime) payload.semantic_time = semanticTime;
    }

    uploadMutation.mutate(payload);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>上传记忆 - {agent?.name}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4 max-h-[60vh] overflow-y-auto pr-2">
            {error && (
              <div className="p-3 text-sm text-destructive bg-destructive/10 rounded-lg">{error}</div>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium">记忆内容 *</label>
              <Textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="粘贴需要分块的记忆文本..."
                className="min-h-32"
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
                <option value="llm">LLM 智能分块</option>
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
                  <p className="text-xs text-muted-foreground">
                    选择记忆实际产生的时间，用于理解时序关系
                  </p>
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
                  <Input
                    type="datetime-local"
                    value={semanticTime}
                    onChange={(e) => setSemanticTime(e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">角色个性提示词 *</label>
                  <Textarea
                    value={personalityPrompt}
                    onChange={(e) => setPersonalityPrompt(e.target.value)}
                    placeholder="用于引导 LLM 进行第一人称、上下文完整的分块..."
                    className="min-h-20"
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
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
            <Button type="submit" disabled={uploadMutation.isPending}>
              {uploadMutation.isPending ? <Loader2 size={16} className="mr-1 animate-spin" /> : null}
              上传
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
