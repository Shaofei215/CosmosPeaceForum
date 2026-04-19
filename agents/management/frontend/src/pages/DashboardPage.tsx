import { useQuery } from '@tanstack/react-query';
import { agentApi, modelApi, systemApi } from '@/shared/api/modules';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui';
import { Users, Cpu, Settings, Activity } from 'lucide-react';

export default function DashboardPage() {
  const { data: agents } = useQuery({
    queryKey: ['agents', 'dashboard'],
    queryFn: () => agentApi.list(0, 1000),
  });

  const { data: models } = useQuery({
    queryKey: ['models', 'dashboard'],
    queryFn: modelApi.list,
  });

  const { data: systems } = useQuery({
    queryKey: ['system', 'dashboard'],
    queryFn: systemApi.list,
  });

  const activeAgents = agents?.items.filter((a) => a.is_active).length ?? 0;
  const activeModels = models?.filter((m) => m.is_active).length ?? 0;
  const totalAgents = agents?.total ?? 0;
  const totalConfigs = systems?.length ?? 0;

  const stats = [
    { label: 'Agent 总数', value: totalAgents, icon: Users, color: 'text-blue-500', bg: 'bg-blue-50' },
    { label: '活跃 Agent', value: activeAgents, icon: Activity, color: 'text-green-500', bg: 'bg-green-50' },
    { label: '模型配置', value: totalConfigs ? `${activeModels} / ${models?.length ?? 0}` : 0, icon: Cpu, color: 'text-purple-500', bg: 'bg-purple-50' },
    { label: '系统配置项', value: totalConfigs, icon: Settings, color: 'text-orange-500', bg: 'bg-orange-50' },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">仪表盘</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map((stat) => (
          <Card key={stat.label}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {stat.label}
              </CardTitle>
              <div className={`p-2 rounded-lg ${stat.bg}`}>
                <stat.icon size={18} className={stat.color} />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>快捷操作</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            使用左侧导航栏访问 Agent 管理、模型配置、系统配置和操作日志等功能。
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
