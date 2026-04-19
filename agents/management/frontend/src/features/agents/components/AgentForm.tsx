import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { agentApi } from '@/shared/api/modules';
import type { AgentConfig, AgentCreate, AgentUpdate, AgentRelationUpdate } from '@/shared/types/api';
import {
  Button, Input, Textarea, Card, CardContent, CardHeader, CardTitle,
  Skeleton,
} from '@/shared/components/ui';
import { ArrowLeft, Save, Users } from 'lucide-react';

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
  const [isActive, setIsActive] = useState(agent?.is_active ?? true);
  const [selectedKnowsIds, setSelectedKnowsIds] = useState<Set<number>>(new Set());
  const [bidirectional, setBidirectional] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (agent) {
      setName(agent.name);
      setUsername(agent.username);
      setMonthlyLogins(agent.monthly_logins);
      setSignature(agent.personal_signature);
      setPersonalityPrompt(agent.personality_prompt);
      setSelectedKnowsIds(new Set(agent.knows_ids));
      setIsActive(agent.is_active);
    }
  }, [agent]);

  const { data: allAgents, isLoading: isLoadingAgents } = useQuery({
    queryKey: ['agents-all'],
    queryFn: () => agentApi.list(0, 1000),
    enabled: mode === 'edit',
  });

  const createMutation = useMutation({
    mutationFn: (data: AgentCreate) => agentApi.create(data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['agents'] });
      await queryClient.invalidateQueries({ queryKey: ['agent'] });
      await queryClient.invalidateQueries({ queryKey: ['agents-all'] });
      navigate('/agents');
    },
    onError: (err: { message?: string }) => {
      setError(err.message || '创建失败');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: AgentUpdate }) =>
      agentApi.update(id, data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['agents'] });
      await queryClient.invalidateQueries({ queryKey: ['agent'] });
      await queryClient.invalidateQueries({ queryKey: ['agents-all'] });
      navigate('/agents');
    },
    onError: (err: { message?: string }) => {
      setError(err.message || '更新失败');
    },
  });

  const relationMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: AgentRelationUpdate }) =>
      agentApi.updateRelation(id, data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['agents'] });
      await queryClient.invalidateQueries({ queryKey: ['agent'] });
      await queryClient.invalidateQueries({ queryKey: ['agents-all'] });
      navigate('/agents');
    },
    onError: (err: { message?: string }) => {
      setError(err.message || '更新关系失败');
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

    if (mode === 'create') {
      createMutation.mutate({
        name: name.trim(),
        username: username.trim(),
        monthly_logins: monthlyLogins,
        personal_signature: signature.trim(),
        personality_prompt: personalityPrompt.trim(),
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
          is_active: isActive,
        },
      });
    }
  };

  const handleSaveRelations = () => {
    if (!agent) return;
    setError('');

    relationMutation.mutate({
      id: agent.id,
      data: {
        knows_ids: Array.from(selectedKnowsIds),
        bidirectional,
      },
    });
  };

  const toggleKnows = (agentId: number) => {
    setSelectedKnowsIds((prev) => {
      const next = new Set(prev);
      if (next.has(agentId)) {
        next.delete(agentId);
      } else {
        next.add(agentId);
      }
      return next;
    });
  };

  const isPending = createMutation.isPending || updateMutation.isPending;
  const isRelationPending = relationMutation.isPending;

  const otherAgents = (allAgents?.items ?? []).filter((a) => a.id !== agent?.id);

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
        <Card className="mb-6">
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
          </CardContent>
        </Card>

        {mode === 'edit' && agent && (
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users size={18} /> 相识 Agent 关系
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isLoadingAgents ? (
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-10 w-full" />
                  ))}
                </div>
              ) : otherAgents.length === 0 ? (
                <p className="text-sm text-muted-foreground">暂无其他 Agent</p>
              ) : (
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">
                    勾选 {agent.name} 认识的 Agent
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {otherAgents.map((other) => (
                      <label
                        key={other.id}
                        className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                          selectedKnowsIds.has(other.id)
                            ? 'border-primary bg-primary/5'
                            : 'border-border hover:bg-muted/50'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={selectedKnowsIds.has(other.id)}
                          onChange={() => toggleKnows(other.id)}
                          className="h-4 w-4"
                        />
                        <div className="flex-1">
                          <span className="text-sm font-medium">{other.name}</span>
                          <span className="text-xs text-muted-foreground ml-2">
                            @{other.username} (ID: {other.id})
                          </span>
                        </div>
                      </label>
                    ))}
                  </div>

                  <div className="flex items-center gap-2 pt-2 mt-2 border-t">
                    <input
                      type="checkbox"
                      id="bidirectional"
                      checked={bidirectional}
                      onChange={(e) => setBidirectional(e.target.checked)}
                      className="h-4 w-4"
                    />
                    <label htmlFor="bidirectional" className="text-sm">
                      双向操作（勾选/取消时对方也会同步添加/移除当前 Agent）
                    </label>
                  </div>

                  <div className="flex items-center gap-2 pt-2">
                    <span className="text-sm text-muted-foreground">
                      已选择 {selectedKnowsIds.size} 位 Agent
                    </span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        <div className="flex justify-end gap-3 mt-6">
          <Button type="button" variant="outline" onClick={() => navigate('/agents')}>
            取消
          </Button>
          {mode === 'edit' ? (
            <>
              <Button
                type="button"
                variant="outline"
                disabled={isRelationPending}
                onClick={handleSaveRelations}
              >
                <Users size={16} className="mr-1" />
                {isRelationPending ? '保存中...' : '保存关系'}
              </Button>
              <Button type="submit" disabled={isPending}>
                <Save size={16} className="mr-1" />
                {isPending ? '保存中...' : '保存'}
              </Button>
            </>
          ) : (
            <Button type="submit" disabled={isPending}>
              <Save size={16} className="mr-1" />
              {isPending ? '创建中...' : '创建'}
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}
