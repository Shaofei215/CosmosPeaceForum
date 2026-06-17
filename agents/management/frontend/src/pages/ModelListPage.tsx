import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { agentApi, modelApi, embeddingApi, chunkModelApi } from '@/shared/api/modules';
import type {
  AgentConfig,
  ModelConfig,
  ModelConfigCreate,
  ModelConfigUpdate,
  EmbeddingConfigUpdate,
  ChunkModelConfigCreate,
  ChunkModelConfigUpdate,
} from '@/shared/types/api';
import {
  Button, Input, Card, CardContent,
  Skeleton, Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter, DialogDescription, Switch, Label, Separator,
} from '@/shared/components/ui';
import { Plus, Edit, Trash2, Eye, EyeOff, Loader2, Search } from 'lucide-react';

const modelProviderOptions = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
];

const modelColorPresets = [
  { label: 'ChatGPT', value: '#10A37F', match: ['openai', 'chatgpt', 'gpt'] },
  { label: 'Claude', value: '#D97745', match: ['anthropic', 'claude'] },
  { label: 'DeepSeek', value: '#2563EB', match: ['deepseek'] },
  { label: 'Qwen', value: '#1677FF', match: ['qwen', '通义'] },
  { label: 'Grok', value: '#111827', match: ['grok', 'xai'] },
  { label: 'Kimi', value: '#1E3A8A', match: ['kimi', 'moonshot'] },
  { label: 'MiniMax', value: '#DC2626', match: ['minimax'] },
];

/**
 * 根据模型提供商、模型名和配置名推断默认颜色。
 *
 * @param provider 模型提供商。
 * @param modelName 实际模型名称。
 * @param name 管理端配置名称。
 * @returns 匹配到的预设 HEX 色值，未匹配时返回 ChatGPT 绿色。
 */
function inferModelColor(provider: string, modelName: string, name: string): string {
  const text = `${provider} ${modelName} ${name}`.toLowerCase();
  return modelColorPresets.find((preset) => preset.match.some((key) => text.includes(key)))?.value
    ?? modelColorPresets[0].value;
}

export default function ModelListPage() {
  const queryClient = useQueryClient();
  const [editingModel, setEditingModel] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [creatingChunkModel, setCreatingChunkModel] = useState(false);
  const [editingChunkModel, setEditingChunkModel] = useState<number | null>(null);
  const [deleteChunkModelId, setDeleteChunkModelId] = useState<number | null>(null);

  const { data: models, isLoading } = useQuery({
    queryKey: ['models'],
    queryFn: modelApi.list,
  });

  const { data: agentsData } = useQuery({
    queryKey: ['agents'],
    queryFn: () => agentApi.list(0, 1000),
  });

  const { data: embeddingConfig } = useQuery({
    queryKey: ['embedding'],
    queryFn: embeddingApi.get,
  });

  const { data: chunkModelConfigs } = useQuery({
    queryKey: ['chunk-models'],
    queryFn: chunkModelApi.list,
  });

  const createMutation = useMutation({
    mutationFn: (data: ModelConfigCreate) => modelApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['models'] });
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      setCreating(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ModelConfigUpdate }) =>
      modelApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['models'] });
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      setEditingModel(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => modelApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['models'] });
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      setDeleteId(null);
    },
  });

  const toggleModelMutation = useMutation({
    mutationFn: (id: number) => modelApi.toggle(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['models'] });
    },
  });

  const updateEmbeddingMutation = useMutation({
    mutationFn: (data: EmbeddingConfigUpdate) => embeddingApi.update(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['embedding'] });
    },
  });

  const createChunkMutation = useMutation({
    mutationFn: (data: ChunkModelConfigCreate) => chunkModelApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chunk-models'] });
      setCreatingChunkModel(false);
    },
  });

  const updateChunkMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ChunkModelConfigUpdate }) =>
      chunkModelApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chunk-models'] });
      setEditingChunkModel(null);
    },
  });

  const deleteChunkMutation = useMutation({
    mutationFn: (id: number) => chunkModelApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chunk-models'] });
      setDeleteChunkModelId(null);
    },
  });

  const toggleChunkMutation = useMutation({
    mutationFn: (id: number) => chunkModelApi.toggle(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chunk-models'] });
    },
  });

  const handleToggleModel = (id: number) => {
    toggleModelMutation.mutate(id);
  };

  const handleToggleEmbedding = (checked: boolean) => {
    updateEmbeddingMutation.mutate({ is_active: checked });
  };

  const handleSaveEmbedding = (data: EmbeddingConfigUpdate) => {
    updateEmbeddingMutation.mutate(data);
  };

  const handleToggleChunkModel = (id: number) => {
    toggleChunkMutation.mutate(id);
  };

  if (isLoading) {
    return (
      <div>
        <h1 className="text-2xl font-bold mb-6">模型配置</h1>
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">模型配置</h1>
        <Button onClick={() => setCreating(true)}>
          <Plus size={16} className="mr-1" /> 创建配置
        </Button>
      </div>

      <div className="space-y-4">
        {models?.map((model) => (
          <Card
            key={model.id}
            className="overflow-hidden"
            style={{
              borderLeftColor: model.color,
              borderRightColor: model.color,
              borderLeftWidth: 4,
              borderRightWidth: 4,
              boxShadow: `inset 12px 0 18px -18px ${model.color}, inset -12px 0 18px -18px ${model.color}`,
            }}
          >
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className="h-3 w-3 rounded-full border"
                      style={{ backgroundColor: model.color }}
                    />
                    <h3 className="font-semibold">{model.name}</h3>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {model.provider} / {model.model_name} / {model.base_url || '默认地址'}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    温度: {model.temperature} | Max Token: {model.max_token}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Switch
                    checked={model.is_active}
                    onCheckedChange={() => handleToggleModel(model.id)}
                    disabled={toggleModelMutation.isPending}
                  />
                  <Button variant="ghost" size="icon" onClick={() => setEditingModel(model.id)}>
                    <Edit size={16} />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setDeleteId(model.id)}
                    className="text-destructive hover:text-destructive"
                  >
                    <Trash2 size={16} />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}

        {models?.length === 0 && (
          <Card>
            <CardContent className="py-12 text-center text-muted-foreground">
              暂无模型配置，点击「创建配置」添加
            </CardContent>
          </Card>
        )}
      </div>

      <Separator className="my-8" />

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            Embedding 配置
          </h2>
          <Switch
            checked={embeddingConfig?.is_active ?? false}
            onCheckedChange={handleToggleEmbedding}
            disabled={updateEmbeddingMutation.isPending}
          />
        </div>

        <Card>
          <CardContent className="p-4">
            <EmbeddingConfigForm
              config={embeddingConfig}
              onSave={handleSaveEmbedding}
              isPending={updateEmbeddingMutation.isPending}
            />
          </CardContent>
        </Card>
      </div>

      <Separator className="my-8" />

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">分块模型配置</h2>
          <Button onClick={() => setCreatingChunkModel(true)}>
            <Plus size={16} className="mr-1" /> 创建配置
          </Button>
        </div>

        <div className="space-y-3">
          {chunkModelConfigs?.map((config) => (
            <Card key={config.id}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-semibold">{config.name}</h3>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {config.provider} / {config.model_name} / {config.base_url || '默认地址'}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      温度: {config.temperature} | Max Token: {config.max_token}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Switch
                      checked={config.is_active}
                      onCheckedChange={() => handleToggleChunkModel(config.id)}
                      disabled={toggleChunkMutation.isPending}
                    />
                    <Button variant="ghost" size="icon" onClick={() => setEditingChunkModel(config.id)}>
                      <Edit size={16} />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setDeleteChunkModelId(config.id)}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 size={16} />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}

          {chunkModelConfigs?.length === 0 && (
            <Card>
              <CardContent className="py-12 text-center text-muted-foreground">
                暂无分块模型配置，点击「创建配置」添加
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      <CreateModelDialog
        open={creating}
        onOpenChange={setCreating}
        onSubmit={(data) => createMutation.mutate(data)}
        isPending={createMutation.isPending}
        agents={agentsData?.items ?? []}
        models={models ?? []}
      />

      {editingModel && (
        <EditModelDialog
          open={!!editingModel}
          onOpenChange={() => setEditingModel(null)}
          onSubmit={(data) => updateMutation.mutate({ id: editingModel, data })}
          isPending={updateMutation.isPending}
          model={models?.find((m) => m.id === editingModel)}
          agents={agentsData?.items ?? []}
          models={models ?? []}
        />
      )}

      <Dialog open={deleteId !== null} onOpenChange={() => setDeleteId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>确定要删除此模型配置吗？此操作不可撤销。</DialogDescription>
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

      <CreateChunkModelDialog
        open={creatingChunkModel}
        onOpenChange={setCreatingChunkModel}
        onSubmit={(data) => createChunkMutation.mutate(data)}
        isPending={createChunkMutation.isPending}
      />

      {editingChunkModel && (
        <EditChunkModelDialog
          open={!!editingChunkModel}
          onOpenChange={() => setEditingChunkModel(null)}
          onSubmit={(data) => updateChunkMutation.mutate({ id: editingChunkModel, data })}
          isPending={updateChunkMutation.isPending}
          model={chunkModelConfigs?.find((m) => m.id === editingChunkModel)}
        />
      )}

      <Dialog open={deleteChunkModelId !== null} onOpenChange={() => setDeleteChunkModelId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>确定要删除此分块模型配置吗？此操作不可撤销。</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteChunkModelId(null)}>取消</Button>
            <Button
              variant="destructive"
              onClick={() => deleteChunkModelId && deleteChunkMutation.mutate(deleteChunkModelId)}
              disabled={deleteChunkMutation.isPending}
            >
              {deleteChunkMutation.isPending ? '删除中...' : '删除'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

interface EmbeddingConfigFormProps {
  config?: { base_url: string; api_key: string; model_name: string; dimension: number };
  onSave: (data: EmbeddingConfigUpdate) => void;
  isPending: boolean;
}

function EmbeddingConfigForm({ config, onSave, isPending }: EmbeddingConfigFormProps) {
  const [baseUrl, setBaseUrl] = useState(config?.base_url ?? '');
  const [apiKey, setApiKey] = useState('');
  const [modelName, setModelName] = useState(config?.model_name ?? 'text-embedding-3-small');
  const [dimension, setDimension] = useState(config?.dimension ?? 1536);
  const [showApiKey, setShowApiKey] = useState(false);
  const [editing, setEditing] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const data: EmbeddingConfigUpdate = {
      base_url: baseUrl.trim(),
      model_name: modelName.trim(),
      dimension,
    };
    if (apiKey.trim()) {
      data.api_key = apiKey.trim();
    }
    onSave(data);
    setEditing(false);
    setApiKey('');
  };

  if (!config && !editing) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        暂无 Embedding 配置
      </div>
    );
  }

  if (!editing) {
    return (
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label className="text-xs text-muted-foreground">Base URL</Label>
            <p className="text-sm">{config?.base_url || '未配置'}</p>
          </div>
          <div>
            <Label className="text-xs text-muted-foreground">模型名称</Label>
            <p className="text-sm">{config?.model_name || '未配置'}</p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label className="text-xs text-muted-foreground">API Key</Label>
            <p className="text-sm">{config?.api_key ? '******' : '未配置'}</p>
          </div>
          <div>
            <Label className="text-xs text-muted-foreground">维度</Label>
            <p className="text-sm">{config?.dimension ?? '未配置'}</p>
          </div>
        </div>
        <div className="flex justify-end pt-2">
          <Button size="sm" onClick={() => setEditing(true)}>
            <Edit size={14} className="mr-1" /> 编辑
          </Button>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Base URL</Label>
            <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.openai.com/v1" />
          </div>
          <div className="space-y-2">
            <Label>模型名称</Label>
            <Input value={modelName} onChange={(e) => setModelName(e.target.value)} placeholder="text-embedding-3-small" />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>API Key (留空则不修改)</Label>
            <div className="relative">
              <Input
                type={showApiKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-..."
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
              >
                {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>
          <div className="space-y-2">
            <Label>维度</Label>
            <Input type="number" min="1" value={dimension} onChange={(e) => setDimension(Number(e.target.value))} />
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="outline" size="sm" onClick={() => { setEditing(false); setApiKey(''); }}>
            取消
          </Button>
          <Button type="submit" size="sm" disabled={isPending}>
            {isPending ? <Loader2 size={14} className="mr-1 animate-spin" /> : null}
            保存
          </Button>
        </div>
      </div>
    </form>
  );
}

interface BaseDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  isPending: boolean;
  agents: AgentConfig[];
  models: ModelConfig[];
}

interface CreateDialogProps extends BaseDialogProps {
  onSubmit: (data: ModelConfigCreate) => void;
  model?: undefined;
}

interface EditDialogProps extends BaseDialogProps {
  onSubmit: (data: ModelConfigUpdate) => void;
  model?: ModelConfig;
}

function ProviderSelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-8 w-full rounded-md border border-input bg-background px-2.5 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
    >
      {modelProviderOptions.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

/**
 * 模型颜色选择器，提供品牌预设与自定义色值输入。
 *
 * @param value 当前色值。
 * @param onChange 色值变更回调。
 * @returns 颜色选择 UI。
 */
function ModelColorPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium">模型颜色</label>
      <div className="flex flex-wrap gap-2">
        {modelColorPresets.map((preset) => (
          <button
            key={preset.value}
            type="button"
            onClick={() => onChange(preset.value)}
            className="h-8 w-8 rounded-full border p-0.5 transition-transform hover:scale-105"
            title={preset.label}
          >
            <span
              className="block h-full w-full rounded-full"
              style={{ backgroundColor: preset.value }}
            />
          </button>
        ))}
        <div
          className="inline-flex h-8 items-center rounded-full border bg-background p-0.5"
          style={{ width: `${Math.max(value.length, 7) + 7}ch` }}
        >
          <span
            className="h-full w-7 shrink-0 rounded-full"
            style={{ backgroundColor: value }}
          />
          <Input
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="#10A37F"
            className="h-7 min-w-0 border-0 bg-transparent px-2 text-xs shadow-none focus-visible:ring-0"
          />
        </div>
      </div>
    </div>
  );
}

/**
 * 角色模型归属选择器，以胶囊形式展示角色并支持搜索、全选与切换归属。
 *
 * @param agents 可分配的角色列表。
 * @param models 当前模型配置列表，用于显示已有归属颜色。
 * @param currentModelId 当前正在创建或编辑的模型 ID，创建时为空。
 * @param currentModelColor 当前正在创建或编辑的模型色值，用于即时预览未保存颜色。
 * @param selectedIds 当前将归属到本模型的角色 ID 集合。
 * @param onChange 角色归属集合变更回调。
 * @returns 角色胶囊选择 UI。
 */
function RoleAssignmentSelector({
  agents,
  models,
  currentModelId,
  currentModelColor,
  selectedIds,
  onChange,
}: {
  agents: AgentConfig[];
  models: ModelConfig[];
  currentModelId?: number;
  currentModelColor: string;
  selectedIds: Set<number>;
  onChange: (ids: Set<number>) => void;
}) {
  const [search, setSearch] = useState('');
  const modelById = new Map(models.map((model) => [model.id, model]));
  const filtered = agents.filter((agent) => agent.name.toLowerCase().includes(search.toLowerCase()));
  const isAllSelected = filtered.length > 0 && filtered.every((agent) => selectedIds.has(agent.id));

  const toggleAgent = (agentId: number) => {
    const next = new Set(selectedIds);
    if (next.has(agentId)) {
      next.delete(agentId);
    } else {
      next.add(agentId);
    }
    onChange(next);
  };

  const toggleAll = () => {
    const next = new Set(selectedIds);
    if (isAllSelected) {
      filtered.forEach((agent) => next.delete(agent.id));
    } else {
      filtered.forEach((agent) => next.add(agent.id));
    }
    onChange(next);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <label className="text-sm font-medium">角色分配</label>
        <Button type="button" variant="outline" size="sm" onClick={toggleAll}>
          {isAllSelected ? '取消全选' : '全选'}
        </Button>
      </div>
      <div className="flex h-9 items-center gap-2 rounded-md border px-2">
        <Search size={15} className="text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索角色名称"
          className="h-7 border-0 px-0 shadow-none focus-visible:ring-0"
        />
      </div>
      <div className="flex flex-wrap gap-2">
        {filtered.map((agent) => {
          const wasAssignedToCurrentModel = currentModelId !== undefined
            && agent.model_config_id === currentModelId;
          const isSelected = selectedIds.has(agent.id);
          const assignedModel = isSelected
            ? models.find((model) => model.id === currentModelId)
            : wasAssignedToCurrentModel
              ? undefined
              : modelById.get(agent.model_config_id ?? -1);
          const color = isSelected ? currentModelColor : assignedModel?.color;

          return (
            <button
              key={agent.id}
              type="button"
              onClick={() => toggleAgent(agent.id)}
              className="inline-flex max-w-full items-center gap-2 rounded-full border px-4 py-1.5 text-sm transition-colors hover:bg-muted"
              style={{
                backgroundColor: color,
                borderColor: color ?? undefined,
                color: color ? '#FFFFFF' : undefined,
              }}
            >
              <span className="max-w-[14rem] truncate font-medium">{agent.name}</span>
            </button>
          );
        })}
        {filtered.length === 0 && (
          <div className="py-3 text-sm text-muted-foreground">未找到匹配角色</div>
        )}
      </div>
    </div>
  );
}

function CreateModelDialog({
  open,
  onOpenChange,
  onSubmit,
  isPending,
  agents,
  models,
}: CreateDialogProps) {
  const [name, setName] = useState('');
  const [provider, setProvider] = useState('openai');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [modelName, setModelName] = useState('');
  const [temperature, setTemperature] = useState(1.2);
  const [maxToken, setMaxToken] = useState(4096);
  const [isActive] = useState(true);
  const [color, setColor] = useState(modelColorPresets[0].value);
  const [colorTouched, setColorTouched] = useState(false);
  const [assignedAgentIds, setAssignedAgentIds] = useState<Set<number>>(new Set());
  const [error, setError] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);

  const updateAutoColor = (nextProvider: string, nextModelName: string, nextName: string) => {
    if (!colorTouched) {
      setColor(inferModelColor(nextProvider, nextModelName, nextName));
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!name.trim()) { setError('请输入配置名称'); return; }
    if (!provider.trim()) { setError('请输入提供商'); return; }
    if (!modelName.trim()) { setError('请输入模型名称'); return; }
    if (!apiKey.trim()) { setError('请输入 API Key'); return; }

    onSubmit({
      name: name.trim(),
      provider: provider.trim(),
      api_key: apiKey.trim(),
      model_name: modelName.trim(),
      base_url: baseUrl.trim(),
      temperature,
      max_token: maxToken,
      is_active: isActive,
      color,
      assigned_agent_ids: Array.from(assignedAgentIds),
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100vh-2rem)] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>创建模型配置</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4">
            {error && (
              <div className="p-3 text-sm text-destructive bg-destructive/10 rounded-lg">{error}</div>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium">配置名称 *</label>
              <Input
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  updateAutoColor(provider, modelName, e.target.value);
                }}
                placeholder="例如：OpenAI GPT-4"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">提供商 *</label>
                <ProviderSelect
                  value={provider}
                  onChange={(value) => {
                    setProvider(value);
                    updateAutoColor(value, modelName, name);
                  }}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">模型名称 *</label>
                <Input
                  value={modelName}
                  onChange={(e) => {
                    setModelName(e.target.value);
                    updateAutoColor(provider, e.target.value, name);
                  }}
                  placeholder="gpt-4o"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">API Key *</label>
              <div className="relative">
                <Input
                  type={showApiKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                >
                  {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Base URL</label>
              <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.openai.com/v1" />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">温度</label>
                <Input type="number" step="0.1" min="0" max="2" value={temperature} onChange={(e) => setTemperature(Number(e.target.value))} />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Max Token</label>
                <Input type="number" min="1" value={maxToken} onChange={(e) => setMaxToken(Number(e.target.value))} />
              </div>
            </div>
            <ModelColorPicker
              value={color}
              onChange={(value) => {
                setColorTouched(true);
                setColor(value);
              }}
            />
            <RoleAssignmentSelector
              agents={agents}
              models={models}
              currentModelColor={color}
              selectedIds={assignedAgentIds}
              onChange={setAssignedAgentIds}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? <Loader2 size={16} className="mr-1 animate-spin" /> : null}
              创建
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditModelDialog({
  open,
  onOpenChange,
  onSubmit,
  isPending,
  model,
  agents,
  models,
}: EditDialogProps) {
  const [name, setName] = useState(model?.name ?? '');
  const [provider, setProvider] = useState(model?.provider ?? 'openai');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState(model?.base_url ?? '');
  const [modelName, setModelName] = useState(model?.model_name ?? '');
  const [temperature, setTemperature] = useState(model?.temperature ?? 1.2);
  const [maxToken, setMaxToken] = useState(model?.max_token ?? 4096);
  const [isActive] = useState(model?.is_active ?? true);
  const [color, setColor] = useState(model?.color ?? modelColorPresets[0].value);
  const [assignedAgentIds, setAssignedAgentIds] = useState<Set<number>>(
    new Set(agents.filter((agent) => agent.model_config_id === model?.id).map((agent) => agent.id)),
  );
  const [error, setError] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!name.trim()) { setError('请输入配置名称'); return; }
    if (!provider.trim()) { setError('请输入提供商'); return; }
    if (!modelName.trim()) { setError('请输入模型名称'); return; }

    const data: ModelConfigUpdate = {
      name: name.trim(),
      provider: provider.trim(),
      model_name: modelName.trim(),
      base_url: baseUrl.trim(),
      temperature,
      max_token: maxToken,
      is_active: isActive,
      color,
      assigned_agent_ids: Array.from(assignedAgentIds),
    };

    if (apiKey.trim()) {
      data.api_key = apiKey.trim();
    }

    onSubmit(data);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100vh-2rem)] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>编辑模型配置</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4">
            {error && (
              <div className="p-3 text-sm text-destructive bg-destructive/10 rounded-lg">{error}</div>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium">配置名称 *</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：OpenAI GPT-4" />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">提供商 *</label>
                <ProviderSelect value={provider} onChange={setProvider} />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">模型名称 *</label>
                <Input value={modelName} onChange={(e) => setModelName(e.target.value)} placeholder="gpt-4o" />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">API Key (留空则不修改)</label>
              <div className="relative">
                <Input
                  type={showApiKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                >
                  {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Base URL</label>
              <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.openai.com/v1" />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">温度</label>
                <Input type="number" step="0.1" min="0" max="2" value={temperature} onChange={(e) => setTemperature(Number(e.target.value))} />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Max Token</label>
                <Input type="number" min="1" value={maxToken} onChange={(e) => setMaxToken(Number(e.target.value))} />
              </div>
            </div>
            <ModelColorPicker value={color} onChange={setColor} />
            <RoleAssignmentSelector
              agents={agents}
              models={models}
              currentModelId={model?.id}
              currentModelColor={color}
              selectedIds={assignedAgentIds}
              onChange={setAssignedAgentIds}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? <Loader2 size={16} className="mr-1 animate-spin" /> : null}
              保存
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function CreateChunkModelDialog({ open, onOpenChange, onSubmit, isPending }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: ChunkModelConfigCreate) => void;
  isPending: boolean;
}) {
  const [name, setName] = useState('');
  const [provider, setProvider] = useState('openai');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [modelName, setModelName] = useState('');
  const [temperature, setTemperature] = useState(0.7);
  const [maxToken, setMaxToken] = useState(4096);
  const [isActive] = useState(true);
  const [error, setError] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!name.trim()) { setError('请输入配置名称'); return; }
    if (!provider.trim()) { setError('请输入提供商'); return; }
    if (!modelName.trim()) { setError('请输入模型名称'); return; }
    if (!apiKey.trim()) { setError('请输入 API Key'); return; }

    onSubmit({
      name: name.trim(),
      provider: provider.trim(),
      api_key: apiKey.trim(),
      model_name: modelName.trim(),
      base_url: baseUrl.trim(),
      temperature,
      max_token: maxToken,
      is_active: isActive,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>创建分块模型配置</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4">
            {error && (
              <div className="p-3 text-sm text-destructive bg-destructive/10 rounded-lg">{error}</div>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium">配置名称 *</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：GPT-4 Chunker" />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">提供商 *</label>
                <ProviderSelect value={provider} onChange={setProvider} />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">模型名称 *</label>
                <Input value={modelName} onChange={(e) => setModelName(e.target.value)} placeholder="gpt-4o" />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">API Key *</label>
              <div className="relative">
                <Input
                  type={showApiKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                >
                  {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Base URL</label>
              <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.openai.com/v1" />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">温度</label>
                <Input type="number" step="0.1" min="0" max="2" value={temperature} onChange={(e) => setTemperature(Number(e.target.value))} />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Max Token</label>
                <Input type="number" min="1" value={maxToken} onChange={(e) => setMaxToken(Number(e.target.value))} />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? <Loader2 size={16} className="mr-1 animate-spin" /> : null}
              创建
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditChunkModelDialog({ open, onOpenChange, onSubmit, isPending, model }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: ChunkModelConfigUpdate) => void;
  isPending: boolean;
  model?: { name: string; provider: string; base_url: string; model_name: string; temperature: number; max_token: number; is_active: boolean };
}) {
  const [name, setName] = useState(model?.name ?? '');
  const [provider, setProvider] = useState(model?.provider ?? 'openai');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState(model?.base_url ?? '');
  const [modelName, setModelName] = useState(model?.model_name ?? '');
  const [temperature, setTemperature] = useState(model?.temperature ?? 0.7);
  const [maxToken, setMaxToken] = useState(model?.max_token ?? 4096);
  const [isActive] = useState(model?.is_active ?? true);
  const [error, setError] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!name.trim()) { setError('请输入配置名称'); return; }
    if (!provider.trim()) { setError('请输入提供商'); return; }
    if (!modelName.trim()) { setError('请输入模型名称'); return; }

    const data: ChunkModelConfigUpdate = {
      name: name.trim(),
      provider: provider.trim(),
      model_name: modelName.trim(),
      base_url: baseUrl.trim(),
      temperature,
      max_token: maxToken,
      is_active: isActive,
    };

    if (apiKey.trim()) {
      data.api_key = apiKey.trim();
    }

    onSubmit(data);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>编辑分块模型配置</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4">
            {error && (
              <div className="p-3 text-sm text-destructive bg-destructive/10 rounded-lg">{error}</div>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium">配置名称 *</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：GPT-4 Chunker" />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">提供商 *</label>
                <ProviderSelect value={provider} onChange={setProvider} />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">模型名称 *</label>
                <Input value={modelName} onChange={(e) => setModelName(e.target.value)} placeholder="gpt-4o" />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">API Key (留空则不修改)</label>
              <div className="relative">
                <Input
                  type={showApiKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                >
                  {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Base URL</label>
              <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.openai.com/v1" />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">温度</label>
                <Input type="number" step="0.1" min="0" max="2" value={temperature} onChange={(e) => setTemperature(Number(e.target.value))} />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Max Token</label>
                <Input type="number" min="1" value={maxToken} onChange={(e) => setMaxToken(Number(e.target.value))} />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? <Loader2 size={16} className="mr-1 animate-spin" /> : null}
              保存
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
