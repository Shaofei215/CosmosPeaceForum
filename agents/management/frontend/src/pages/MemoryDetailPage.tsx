import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { memoryApi, agentApi } from '@/shared/api/modules';
import type { MemoryChunk, MemoryUpdateRequest, MemoryUploadRequest } from '@/shared/types/api';
import {
  Button, Input, Textarea, Card, CardContent,
  Badge, Skeleton, Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter, DialogDescription,
} from '@/shared/components/ui';
import { ArrowLeft, Upload, Trash2, Loader2, Clock, Pencil, Search } from 'lucide-react';

export default function MemoryDetailPage() {
  const { ownerId } = useParams<{ ownerId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [editMemory, setEditMemory] = useState<MemoryChunk | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(0);
  const limit = 50;

  const ownerIdNum = ownerId ? Number(ownerId) : undefined;

  const { data: agent } = useQuery({
    queryKey: ['agent', ownerId],
    queryFn: () => agentApi.list(0, 200).then((res) =>
      res.items.find((a) => a.social_platform_user_id === ownerIdNum)
    ),
    enabled: !!ownerIdNum,
  });

  const { data: memories, isLoading, error: memoriesError } = useQuery({
    queryKey: ['memories', ownerId, page, searchQuery],
    queryFn: () => searchQuery
      ? memoryApi.search(searchQuery, page * limit, limit, ownerIdNum)
      : memoryApi.list(page * limit, limit, ownerIdNum),
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

  const submitSearch = (event: React.FormEvent) => {
    event.preventDefault();
    setPage(0);
    setSearchQuery(searchInput.trim());
  };

  if (!ownerIdNum) {
    return <div className="text-center py-12 text-muted-foreground">无效的角色链接</div>;
  }

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <Button variant="ghost" size="icon" onClick={() => navigate('/memories')}>
          <ArrowLeft size={20} />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">
            {agent?.name || agent?.username || '角色'}的记忆
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

      <form onSubmit={submitSearch} className="relative mb-6 max-w-md">
        <Search
          size={18}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          value={searchInput}
          onChange={(event) => {
            const value = event.target.value;
            setSearchInput(value);
            if (!value) {
              setSearchQuery('');
              setPage(0);
            }
          }}
          placeholder="检索这个角色的记忆，按回车确认..."
          className="pl-10"
        />
      </form>

      {searchQuery && !memoriesError && (
        <p className="text-sm text-muted-foreground mb-4">
          “{searchQuery}”找到 {memories?.total ?? 0} 条相关记忆
        </p>
      )}

      {memoriesError ? (
        <Card className="border-destructive/50">
          <CardContent className="py-8 text-center text-destructive">
            {getMemoryQueryErrorMessage(memoriesError)}
          </CardContent>
        </Card>
      ) : isLoading ? (
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
                        <Badge variant="outline">
                          {mem.memory_type === 'static' ? '静态记忆' : '动态记忆'}
                        </Badge>
                      </div>
                      <p className="text-sm mt-2 whitespace-pre-wrap">{mem.content}</p>
                      {mem.semantic_timestamp > 0 && mem.semantic_timestamp > 1000000 && (
                        <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                          <Clock size={12} />
                          产生于: {formatTimestamp(mem.semantic_timestamp)}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center ml-4">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setEditMemory(mem)}
                        aria-label="编辑记忆"
                      >
                        <Pencil size={16} />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDeleteId(mem.id)}
                        className="text-destructive hover:text-destructive"
                        aria-label="删除记忆"
                      >
                        <Trash2 size={16} />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}

            {memories?.items.length === 0 && (
              <Card>
                <CardContent className="py-12 text-center text-muted-foreground">
                  {searchQuery
                    ? '没有找到符合当前检索条件的记忆'
                    : '暂无记忆记录，点击上方「上传记忆」添加'}
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

      <EditMemoryDialog
        memory={editMemory}
        onOpenChange={(open) => {
          if (!open) setEditMemory(null);
        }}
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

function getMemoryQueryErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'message' in error) {
    return String((error as { message?: unknown }).message ?? '记忆查询失败');
  }
  return '记忆查询失败，请确认 Agents 后端已重启并加载最新接口';
}

function timestampToLocalInput(timestamp: number): string {
  if (!timestamp || timestamp < 1000000) return '';
  const date = new Date(timestamp * 1000);
  const offsetMilliseconds = date.getTimezoneOffset() * 60 * 1000;
  return new Date(date.getTime() - offsetMilliseconds).toISOString().slice(0, 16);
}

function EditMemoryDialog({
  memory,
  onOpenChange,
  ownerId,
}: {
  memory: MemoryChunk | null;
  onOpenChange: (open: boolean) => void;
  ownerId: number;
}) {
  const queryClient = useQueryClient();
  const [content, setContent] = useState('');
  const [semanticTime, setSemanticTime] = useState('');
  const [coefficient, setCoefficient] = useState('0.85');
  const [memoryType, setMemoryType] = useState<'normal' | 'static'>('normal');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!memory) return;
    setContent(memory.content);
    setSemanticTime(timestampToLocalInput(memory.semantic_timestamp));
    setCoefficient(String(memory.memory_coefficient));
    setMemoryType(memory.memory_type);
    setError('');
  }, [memory]);

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: MemoryUpdateRequest }) =>
      memoryApi.updateMemory(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['memories', ownerId.toString()] });
      queryClient.invalidateQueries({ queryKey: ['memories-all'] });
      queryClient.invalidateQueries({ queryKey: ['memory-owners'] });
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      if (err instanceof Error) {
        setError(err.message);
        return;
      }
      if (typeof err === 'object' && err !== null && 'message' in err) {
        setError(String((err as { message?: unknown }).message ?? '更新失败'));
        return;
      }
      setError('更新失败');
    },
  });

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!memory) return;
    if (!content.trim()) {
      setError('请输入记忆内容');
      return;
    }
    const parsedCoefficient = Number(coefficient);
    if (
      !coefficient
      || !Number.isFinite(parsedCoefficient)
      || parsedCoefficient < 0
      || parsedCoefficient > 1
    ) {
      setError('记忆系数必须在 0.0 到 1.0 之间');
      return;
    }

    const semanticTimestamp = semanticTime
      ? new Date(semanticTime).getTime() / 1000
      : memory.semantic_timestamp;
    updateMutation.mutate({
      id: memory.id,
      data: {
        content: content.trim(),
        semantic_timestamp: semanticTimestamp,
        memory_coefficient: parsedCoefficient,
        memory_type: memoryType,
      },
    });
  };

  return (
    <Dialog open={memory !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>编辑记忆</DialogTitle>
          <DialogDescription>
            保存后主数据立即更新，向量与关键词索引将在后台重新构建。
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4">
            {error && (
              <div className="p-3 text-sm text-destructive bg-destructive/10 rounded-lg">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <label className="text-sm font-medium">记忆内容 *</label>
              <Textarea
                value={content}
                onChange={(event) => setContent(event.target.value)}
                className="min-h-32"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">记忆类型</label>
              <select
                value={memoryType}
                onChange={(event) =>
                  setMemoryType(event.target.value as 'normal' | 'static')
                }
                className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              >
                <option value="normal">动态记忆</option>
                <option value="static">静态记忆</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">记忆发生时间</label>
              <Input
                type="datetime-local"
                value={semanticTime}
                onChange={(event) => setSemanticTime(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">记忆系数 (0.0 - 1.0)</label>
              <Input
                type="number"
                step="any"
                min="0"
                max="1"
                value={coefficient}
                onChange={(event) => setCoefficient(event.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button type="submit" disabled={updateMutation.isPending}>
              {updateMutation.isPending && <Loader2 size={16} className="mr-1 animate-spin" />}
              保存
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
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
  const [chunkMode, setChunkMode] = useState<'auto' | 'llm' | 'none'>('auto');
  const [memoryType, setMemoryType] = useState<'normal' | 'static'>('normal');
  const [staticCoefficient, setStaticCoefficient] = useState(0.7);
  const [personalityPrompt, setPersonalityPrompt] = useState('');
  const [enableRagOnChunking, setEnableRagOnChunking] = useState(true);
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
      setMemoryType('normal');
      setStaticCoefficient(0.7);
      setPersonalityPrompt('');
      setEnableRagOnChunking(true);
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
    if (chunkMode === 'auto' && memoryType === 'normal' && !semanticTime) { setError('动态记忆的自动分块模式必须选择记忆发生时间'); return; }
    if (chunkMode === 'none' && memoryType === 'normal' && !semanticTime) { setError('动态记忆的不分块模式必须选择记忆发生时间'); return; }
    if (chunkMode === 'llm' && !personalityPrompt.trim()) {
      setError('LLM 分块必须填写角色个性提示词');
      return;
    }

    const payload: MemoryUploadRequest = {
      owner_id: ownerId,
      content: content.trim(),
      chunk_mode: chunkMode,
      memory_type: memoryType,
      memory_coefficient: memoryType === 'static' ? staticCoefficient : coefficient,
    };

    if (chunkMode === 'auto') {
      if (memoryType === 'normal') {
        payload.semantic_time = semanticTime;
      }
    } else if (chunkMode === 'none') {
      if (memoryType === 'normal') {
        payload.semantic_time = semanticTime;
      }
    } else {
      payload.personality_prompt = personalityPrompt.trim();
      if (semanticTime) payload.semantic_time = semanticTime;
      payload.enable_rag_on_chunking = enableRagOnChunking;
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
                onChange={(e) => setChunkMode(e.target.value as 'auto' | 'llm' | 'none')}
                className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              >
                <option value="auto">自动分块</option>
                <option value="llm">LLM 智能分块</option>
                <option value="none">不分块</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">记忆类型</label>
              <select
                value={memoryType}
                onChange={(e) => setMemoryType(e.target.value as 'normal' | 'static')}
                className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              >
                <option value="normal">动态记忆</option>
                <option value="static">静态记忆</option>
              </select>
            </div>

            {memoryType === 'normal' && chunkMode !== 'llm' && (
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
                  <p className="text-xs text-muted-foreground">
                    初始记忆系数，后续会随时间衰减或被唤醒提升
                  </p>
                </div>
              </>
            )}

            {memoryType === 'normal' && chunkMode === 'llm' && (
              <>
                <div className="space-y-2">
                  <label className="text-sm font-medium">记忆发生时间（可选）</label>
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
                  <label className="text-sm font-medium">角色个性提示词 *</label>
                  <Textarea
                    value={personalityPrompt}
                    onChange={(e) => setPersonalityPrompt(e.target.value)}
                    placeholder="用于引导 LLM 进行第一人称、上下文完整的分块..."
                    className="min-h-20"
                  />
                </div>
              </>
            )}

            {memoryType === 'static' && (
              <>
                <div className="space-y-2">
                  <label className="text-sm font-medium">记忆发生时间（可选）</label>
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
                  <label className="text-sm font-medium">
                    记忆系数 (0.0 - 1.0)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={staticCoefficient}
                    onChange={(e) => setStaticCoefficient(Number(e.target.value))}
                    className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                  />
                  <p className="text-xs text-muted-foreground">
                    记忆系数设定后将保持恒定不变
                  </p>
                </div>

                {chunkMode === 'llm' && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium">角色个性提示词 *</label>
                    <Textarea
                      value={personalityPrompt}
                      onChange={(e) => setPersonalityPrompt(e.target.value)}
                      placeholder="用于引导 LLM 进行第一人称、上下文完整的分块..."
                      className="min-h-20"
                    />
                  </div>
                )}
              </>
            )}

            {chunkMode === 'llm' && (
              <div className="flex items-center gap-2 p-3 border rounded-md">
                <input
                  type="checkbox"
                  checked={enableRagOnChunking}
                  onChange={(e) => setEnableRagOnChunking(e.target.checked)}
                  className="accent-primary"
                />
                <div>
                  <p className="text-sm font-medium">LLM 分块时启用 RAG</p>
                  <p className="text-xs text-muted-foreground">
                    分块前召回已有静态记忆作为参考
                  </p>
                </div>
              </div>
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
