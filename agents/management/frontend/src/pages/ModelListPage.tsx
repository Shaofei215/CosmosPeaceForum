import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { modelApi, embeddingApi } from '@/shared/api/modules';
import type { ModelConfigCreate, ModelConfigUpdate, EmbeddingConfigUpdate } from '@/shared/types/api';
import {
  Button, Input, Textarea, Card, CardContent, CardHeader, CardTitle,
  Badge, Skeleton, Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter, DialogDescription, Switch, Label, Separator,
} from '@/shared/components/ui';
import { Plus, Edit, Trash2, Eye, EyeOff, Loader2 } from 'lucide-react';

export default function ModelListPage() {
  const queryClient = useQueryClient();
  const [editingModel, setEditingModel] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);

  const { data: models, isLoading } = useQuery({
    queryKey: ['models'],
    queryFn: modelApi.list,
  });

  const { data: embeddingConfig } = useQuery({
    queryKey: ['embedding'],
    queryFn: embeddingApi.get,
  });

  const createMutation = useMutation({
    mutationFn: (data: ModelConfigCreate) => modelApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['models'] });
      setCreating(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ModelConfigUpdate }) =>
      modelApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['models'] });
      setEditingModel(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => modelApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['models'] });
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

  const handleToggleModel = (id: number) => {
    toggleModelMutation.mutate(id);
  };

  const handleToggleEmbedding = (checked: boolean) => {
    updateEmbeddingMutation.mutate({ is_active: checked });
  };

  const handleSaveEmbedding = (data: EmbeddingConfigUpdate) => {
    updateEmbeddingMutation.mutate(data);
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
          <Card key={model.id}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold">{model.name}</h3>
                    <Badge variant={model.is_active ? 'default' : 'secondary'}>
                      {model.is_active ? '启用' : '禁用'}
                    </Badge>
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
            <Badge variant={embeddingConfig?.is_active ? 'default' : 'secondary'}>
              {embeddingConfig?.is_active ? '启用' : '禁用'}
            </Badge>
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

      {/* Create Dialog */}
      <CreateModelDialog
        open={creating}
        onOpenChange={setCreating}
        onSubmit={(data) => createMutation.mutate(data)}
        isPending={createMutation.isPending}
      />

      {/* Edit Dialog */}
      {editingModel && (
        <EditModelDialog
          open={!!editingModel}
          onOpenChange={() => setEditingModel(null)}
          onSubmit={(data) => updateMutation.mutate({ id: editingModel, data })}
          isPending={updateMutation.isPending}
          model={models?.find((m) => m.id === editingModel)}
        />
      )}

      {/* Delete Confirm */}
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
}

interface CreateDialogProps extends BaseDialogProps {
  onSubmit: (data: ModelConfigCreate) => void;
  model?: undefined;
}

interface EditDialogProps extends BaseDialogProps {
  onSubmit: (data: ModelConfigUpdate) => void;
  model?: { name: string; provider: string; base_url: string; model_name: string; temperature: number; max_token: number; is_active: boolean };
}

function CreateModelDialog({ open, onOpenChange, onSubmit, isPending }: CreateDialogProps) {
  const [name, setName] = useState('');
  const [provider, setProvider] = useState('openai');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [modelName, setModelName] = useState('');
  const [temperature, setTemperature] = useState(1.2);
  const [maxToken, setMaxToken] = useState(4096);
  const [isActive, setIsActive] = useState(true);
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
          <DialogTitle>创建模型配置</DialogTitle>
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
                <Input value={provider} onChange={(e) => setProvider(e.target.value)} placeholder="openai / anthropic" />
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

function EditModelDialog({ open, onOpenChange, onSubmit, isPending, model }: EditDialogProps) {
  const [name, setName] = useState(model?.name ?? '');
  const [provider, setProvider] = useState(model?.provider ?? 'openai');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState(model?.base_url ?? '');
  const [modelName, setModelName] = useState(model?.model_name ?? '');
  const [temperature, setTemperature] = useState(model?.temperature ?? 1.2);
  const [maxToken, setMaxToken] = useState(model?.max_token ?? 4096);
  const [isActive, setIsActive] = useState(model?.is_active ?? true);
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
                <Input value={provider} onChange={(e) => setProvider(e.target.value)} placeholder="openai / anthropic" />
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
