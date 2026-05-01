import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { agentApi, modelApi, systemApi, terminalLogApi } from '@/shared/api/modules';
import { Card, CardContent, CardHeader, CardTitle, Button } from '@/shared/components/ui';
import { Users, Cpu, Settings, Activity, Terminal, Trash2 } from 'lucide-react';
import type { TerminalLog } from '@/shared/types/api';

const levelColors: Record<string, string> = {
  INFO: 'text-green-400',
  WARNING: 'text-yellow-400',
  ERROR: 'text-red-400',
  DEBUG: 'text-blue-400',
};

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

  const { data: logsData, refetch } = useQuery({
    queryKey: ['terminal-logs', 'dashboard'],
    queryFn: () => terminalLogApi.recent(100),
    refetchInterval: 2000,
  });

  const logContainerRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logsData?.items, autoScroll]);

  const handleScroll = () => {
    if (!logContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = logContainerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    setAutoScroll(isAtBottom);
  };

  const handleClearLogs = async () => {
    await terminalLogApi.clear();
    refetch();
  };

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
        <CardHeader className="flex flex-row items-center justify-between">
          <div className="flex items-center gap-2">
            <Terminal size={18} className="text-muted-foreground" />
            <CardTitle>终端日志</CardTitle>
          </div>
          <Button variant="outline" size="sm" onClick={handleClearLogs}>
            <Trash2 size={14} className="mr-1" />
            清空
          </Button>
        </CardHeader>
        <CardContent>
          <div
            ref={logContainerRef}
            onScroll={handleScroll}
            className="h-96 overflow-auto rounded-lg bg-zinc-950 p-4 font-mono text-sm"
          >
            {logsData?.items.map((log: TerminalLog, index: number) => (
              <div key={index} className="flex gap-3 leading-6">
                <span className="text-zinc-500 shrink-0">{log.timestamp}</span>
                <span className={`shrink-0 w-16 ${levelColors[log.level] || 'text-zinc-400'}`}>
                  [{log.level}]
                </span>
                <span className="text-zinc-300 break-all">{log.message}</span>
              </div>
            ))}
            {(!logsData?.items || logsData.items.length === 0) && (
              <div className="text-zinc-500 text-center py-12">暂无终端日志</div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="mt-6">
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
