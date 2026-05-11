import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { agentApi } from '@/shared/api/modules';
import {
  Card, CardContent, CardHeader, CardTitle,
  Badge, Skeleton, Button,
} from '@/shared/components/ui';
import {
  ArrowLeft, RefreshCw, Upload, Loader2, Edit, Calendar,
  User, FileText, Hash, Activity, Users,
} from 'lucide-react';
import { Avatar } from '@/shared/components/ui/avatar';

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const agentId = Number(id);
  const [uploading, setUploading] = useState(false);

  const { data: agent, isLoading } = useQuery({
    queryKey: ['agent', agentId],
    queryFn: () => agentApi.getOne(agentId),
    enabled: !!agentId,
  });

  const { data: allAgents } = useQuery({
    queryKey: ['agents-all'],
    queryFn: () => agentApi.list(0, 1000),
  });

  const restartMutation = useMutation({
    mutationFn: () => agentApi.restart(agentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      queryClient.invalidateQueries({ queryKey: ['agent', agentId] });
    },
  });

  const handleAvatarUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !agent) return;
    setUploading(true);
    agentApi.uploadAvatar(agent.id, file)
      .then(() => {
        queryClient.invalidateQueries({ queryKey: ['agent', agentId] });
      })
      .catch(() => {})
      .finally(() => setUploading(false));
  };

  const handleRestart = () => {
    restartMutation.mutate();
  };

  const agentNameMap = new Map(
    (allAgents?.items ?? []).map((a) => [a.id, a.name])
  );

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (!agent) {
    return <div className="text-center py-12 text-muted-foreground">角色不存在</div>;
  }

  const knownAgents = agent.knows_ids
    .filter((kid) => kid !== agent.id)
    .map((kid) => ({
      id: kid,
      name: agentNameMap.get(kid) ?? `角色 #${kid}`,
    }));

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft size={20} />
          </Button>
          <h1 className="text-2xl font-bold">角色详情</h1>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(`/agents/${agent.id}/edit`)}>
            <Edit size={16} className="mr-1" /> 编辑
          </Button>
          <Button
            variant="outline"
            onClick={handleRestart}
            disabled={restartMutation.isPending}
          >
            {restartMutation.isPending ? (
              <Loader2 size={16} className="mr-1 animate-spin" />
            ) : (
              <RefreshCw size={16} className="mr-1" />
            )}
            重启
          </Button>
        </div>
      </div>

      {/* Avatar & Basic Info */}
      <Card className="mb-6">
        <CardContent className="p-6">
          <div className="flex items-start gap-6">
            <div className="relative">
              <Avatar src={null} alt={agent.name} size="2xl" />
              <label className="absolute bottom-0 right-0 p-1 bg-primary rounded-full cursor-pointer hover:bg-primary/90 transition-colors">
                <Upload size={12} className="text-primary-foreground" />
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={handleAvatarUpload}
                  disabled={uploading}
                />
              </label>
            </div>

            <div className="flex-1 space-y-3">
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold">{agent.name}</h2>
                <Badge variant={agent.is_active ? 'default' : 'secondary'}>
                  {agent.is_active ? '启用' : '禁用'}
                </Badge>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <User size={14} />
                  <span>用户名: <span className="text-foreground">{agent.username}</span></span>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Hash size={14} />
                  <span>ID: <span className="text-foreground">{agent.id}</span></span>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Activity size={14} />
                  <span>平台 ID: <span className="text-foreground">{agent.app_platform_user_id ?? '未注册'}</span></span>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Calendar size={14} />
                  <span>创建时间: <span className="text-foreground">{formatDateSimple(agent.created_at)}</span></span>
                </div>
              </div>

              {agent.personal_signature && (
                <div className="pt-2">
                  <p className="text-sm text-muted-foreground mb-1">个性签名</p>
                  <p className="text-sm">{agent.personal_signature}</p>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Personality Prompt */}
      {agent.personality_prompt && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText size={18} /> 角色性格提示词
            </CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="whitespace-pre-wrap text-sm bg-muted p-4 rounded-lg">
              {agent.personality_prompt}
            </pre>
          </CardContent>
        </Card>
      )}

      {/* Relationship */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users size={18} /> 关系网络
          </CardTitle>
        </CardHeader>
        <CardContent>
          {knownAgents.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {knownAgents.map((known) => (
                <Badge key={known.id} variant="outline">
                  {known.name}
                </Badge>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">暂无关联角色</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function formatDateSimple(dateStr: string): string {
  const d = new Date(dateStr);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}
