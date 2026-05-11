import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { agentApi, terminalLogApi } from '@/shared/api/modules';
import { Card, CardContent, CardHeader, CardTitle, Button } from '@/shared/components/ui';
import { Search, Terminal, Trash2 } from 'lucide-react';
import type { TerminalLog } from '@/shared/types/api';

const levelColors: Record<string, string> = {
  INFO: 'text-green-400',
  WARNING: 'text-yellow-400',
  ERROR: 'text-red-400',
  DEBUG: 'text-blue-400',
};

export default function DashboardPage() {
  const [selectedLogRole, setSelectedLogRole] = useState('');
  const [logSearch, setLogSearch] = useState('');

  const { data: agents } = useQuery({
    queryKey: ['agents', 'dashboard'],
    queryFn: () => agentApi.list(0, 1000),
  });

  const { data: dashboardStats } = useQuery({
    queryKey: ['agents', 'dashboard-stats'],
    queryFn: agentApi.dashboardStats,
  });

  const { data: logsData, refetch } = useQuery({
    queryKey: ['terminal-logs', 'dashboard', selectedLogRole, logSearch],
    queryFn: () => terminalLogApi.list(
      0,
      200,
      undefined,
      logSearch.trim() || undefined,
      selectedLogRole || undefined,
    ),
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

  const formatPercent = (value?: number) => `${Math.round(value ?? 0)}%`;

  const stats = [
    {
      label: '启用角色数',
      value: dashboardStats?.enabled_roles ?? 0,
      bg: 'bg-emerald-100',
      text: 'text-emerald-950',
    },
    {
      label: '日活跃角色数',
      value: dashboardStats?.daily_active_roles ?? 0,
      bg: 'bg-amber-100',
      text: 'text-amber-950',
    },
    {
      label: '系统情况',
      bg: 'bg-sky-100',
      text: 'text-sky-950',
      metrics: [
        { label: 'CPU', value: formatPercent(dashboardStats?.cpu_usage_percent) },
        { label: '内存', value: formatPercent(dashboardStats?.memory_usage_percent) },
      ],
    },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">仪表盘</h1>

      <div className="flex flex-wrap gap-4 mb-8">
        {stats.map((stat) => (
          <Card key={stat.label} className="aspect-[2/1] w-64 max-w-full overflow-hidden">
            <div className="grid h-full grid-cols-2">
              <div className="flex items-center p-5">
                <CardTitle className="text-base font-medium leading-6 text-muted-foreground">
                  {stat.label}
                </CardTitle>
              </div>
              <div className={`flex h-full items-center justify-center ${stat.bg} ${stat.text}`}>
                {'metrics' in stat ? (
                  <div className="grid h-full w-full grid-rows-2 divide-y divide-white/60">
                    {stat.metrics.map((metric) => (
                      <div key={metric.label} className="flex items-center justify-between px-4">
                        <span className="text-sm font-medium">{metric.label}</span>
                        <span className="text-3xl font-semibold tabular-nums">{metric.value}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <span className="text-5xl font-semibold tabular-nums">{stat.value}</span>
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader className="flex flex-col gap-3 space-y-0 p-4 pb-2 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-2">
            <Terminal size={18} className="text-muted-foreground" />
            <CardTitle>终端日志</CardTitle>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                value={logSearch}
                onChange={(event) => setLogSearch(event.target.value)}
                placeholder="搜索日志内容..."
                className="h-9 w-full rounded-md border border-input bg-background pl-8 pr-3 text-sm sm:w-56"
              />
            </div>
            <select
              value={selectedLogRole}
              onChange={(event) => setSelectedLogRole(event.target.value)}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              aria-label="按角色过滤日志"
            >
              <option value="">全部角色</option>
              {agents?.items.map((agent) => (
                <option key={agent.id} value={agent.username}>
                  {agent.name} (@{agent.username})
                </option>
              ))}
            </select>
            <Button variant="outline" size="sm" onClick={handleClearLogs}>
              <Trash2 size={14} className="mr-1" />
              清空
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-4 pt-0">
          <div
            ref={logContainerRef}
            onScroll={handleScroll}
            className="h-96 overflow-auto rounded-lg bg-zinc-950 p-4 font-mono text-sm"
          >
            {logsData?.items.map((log: TerminalLog, index: number) => (
              <div key={index} className="flex gap-3 leading-6">
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
            使用左侧导航栏访问角色管理、模型配置、系统配置和操作日志等功能。
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
