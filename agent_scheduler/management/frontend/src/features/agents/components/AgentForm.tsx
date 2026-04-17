import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { agentApi } from '@/shared/api/modules';
import type { AgentConfig, AgentCreate, AgentUpdate } from '@/shared/types/api';
import {
  Button, Input, Textarea, Card, CardContent, CardHeader, CardTitle,
} from '@/shared/components/ui';
import { ArrowLeft, Save } from 'lucide-react';

interface AgentFormPageProps {
  mode: 'create' | 'edit';
  agent?: AgentConfig;
}

export default function AgentFormPage({ mode, agent }: AgentFormPageProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [name, setName] = useState(agent?.name ?? '');
  const [username, setUsername] = useState(agent?.username ?? '');
  const [monthlyLogins, setMonthlyLogins] = useState(agent?.monthly_logins ?? 30);
  const [signature, setSignature] = useState(agent?.personal_signature ?? '');
  const [personalityPrompt, setPersonalityPrompt] = useState(agent?.personality_prompt ?? '');
  const [knowsIds, setKnowsIds] = useState<string>(agent?.knows_ids.join(', ') ?? '');
  const [isActive, setIsActive] = useState(agent?.is_active ?? true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (agent) {
      setName(agent.name);
      setUsername(agent.username);
      setMonthlyLogins(agent.monthly_logins);
      setSignature(agent.personal_signature);
      setPersonalityPrompt(agent.personality_prompt);
      setKnowsIds(agent.knows_ids.join(', '));
      setIsActive(agent.is_active);
    }
  }, [agent]);

  const createMutation = useMutation({
    mutationFn: (data: AgentCreate) => agentApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      navigate('/agents');
    },
    onError: (err: { message?: string }) => {
      setError(err.message || '创建失败');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: AgentUpdate }) =>
      agentApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      navigate('/agents');
    },
    onError: (err: { message?: string }) => {
      setError(err.message || '更新失败');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!name.trim()) {
      setError('请输入角色名称');
      return;
    }
    if (!username.trim()) {
      setError('请输入用户名');
      return;
    }

    const parsedKnowsIds = knowsIds
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
      .map(Number)
      .filter((n) => !isNaN(n));

    if (mode === 'create') {
      createMutation.mutate({
        name: name.trim(),
        username: username.trim(),
        monthly_logins: monthlyLogins,
        personal_signature: signature.trim(),
        personality_prompt: personalityPrompt.trim(),
        knows_ids: parsedKnowsIds,
        is_active: isActive,
      });
    } else if (agent) {
      updateMutation.mutate({
        id: agent.id,
        data: {
          name: name.trim(),
          monthly_logins: monthlyLogins,
          personal_signature: signature.trim(),
          personality_prompt: personalityPrompt.trim(),
          knows_ids: parsedKnowsIds,
          is_active: isActive,
        },
      });
    }
  };

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
          <ArrowLeft size={20} />
        </Button>
        <h1 className="text-2xl font-bold">
          {mode === 'create' ? '创建 Agent' : `编辑 Agent - ${agent?.name}`}
        </h1>
      </div>

      <form onSubmit={handleSubmit}>
        <Card>
          <CardHeader>
            <CardTitle>基本信息</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {error && (
              <div className="p-3 text-sm text-destructive bg-destructive/10 rounded-lg">
                {error}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">角色名称 *</label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="例如：Herta"
                  disabled={mode === 'edit'}
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">用户名 *</label>
                <Input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="例如：herta_bot"
                  disabled={mode === 'edit'}
                />
                {mode === 'edit' && (
                  <p className="text-xs text-muted-foreground">用户名不可修改</p>
                )}
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">每月登录次数</label>
                <Input
                  type="number"
                  value={monthlyLogins}
                  onChange={(e) => setMonthlyLogins(Number(e.target.value))}
                  min={0}
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">状态</label>
                <div className="flex items-center gap-2 pt-1">
                  <input
                    type="checkbox"
                    id="isActive"
                    checked={isActive}
                    onChange={(e) => setIsActive(e.target.checked)}
                    className="h-4 w-4"
                  />
                  <label htmlFor="isActive" className="text-sm">启用此 Agent</label>
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">个性签名</label>
              <Textarea
                value={signature}
                onChange={(e) => setSignature(e.target.value)}
                placeholder="简短描述..."
                rows={2}
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">角色性格提示词</label>
              <Textarea
                value={personalityPrompt}
                onChange={(e) => setPersonalityPrompt(e.target.value)}
                placeholder="定义 Agent 的个性和行为方式..."
                rows={5}
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">认识的 Agent ID</label>
              <Input
                value={knowsIds}
                onChange={(e) => setKnowsIds(e.target.value)}
                placeholder="用逗号分隔，例如：1, 3, 5"
              />
              <p className="text-xs text-muted-foreground">输入其他 Agent 的 ID，用逗号分隔</p>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end gap-3 mt-6">
          <Button type="button" variant="outline" onClick={() => navigate(-1)}>
            取消
          </Button>
          <Button type="submit" disabled={isPending}>
            <Save size={16} className="mr-1" />
            {isPending ? '保存中...' : (mode === 'create' ? '创建' : '保存')}
          </Button>
        </div>
      </form>
    </div>
  );
}
