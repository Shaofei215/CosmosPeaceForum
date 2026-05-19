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

type DashboardStat =
  | {
      type: 'value';
      label: string;
      value: number;
      bg: string;
      text: string;
    }
  | {
      type: 'metrics';
      label: string;
      metrics: Array<{ label: string; value: string }>;
      bg: string;
      text: string;
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
    refetchInterval: 3000,
  });

  const { data: logsData, refetch } = useQuery({
    queryKey: ['terminal-logs', 'dashboard', selectedLogRole, logSearch],
    queryFn: async () => {
      const data = await terminalLogApi.recent(200, selectedLogRole || undefined);
      const keyword = logSearch.trim().toLowerCase();
      if (!keyword) return data;

      const items = data.items.filter((log) => log.message.toLowerCase().includes(keyword));
      return { ...data, items, total: items.length };
    },
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

  const formatPercent = (value?: number) => {
    if (value === undefined || value === null) return '0%';
    if (value > 0 && value < 0.1) return '<0.1%';
    if (value < 10) return `${value.toFixed(1)}%`;
    return `${Math.round(value)}%`;
  };

  const stats: DashboardStat[] = [
    {
      type: 'value',
      label: '启用角色数',
      value: dashboardStats?.enabled_roles ?? 0,
      bg: 'bg-emerald-100',
      text: 'text-emerald-950',
    },
    {
      type: 'value',
      label: '日活跃角色数',
      value: dashboardStats?.daily_active_roles ?? 0,
      bg: 'bg-amber-100',
      text: 'text-amber-950',
    },
    {
      type: 'metrics',
      label: '性能占用',
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

      <div className="flex flex-wrap gap-4 mb-4">
        {stats.map((stat) => (
          <Card key={stat.label} className="aspect-[2/1] w-64 max-w-full overflow-hidden">
            <div className="grid h-full grid-cols-2">
              <div className="flex items-center justify-center p-5 text-center">
                <CardTitle className={`text-xl font-semibold leading-7 ${stat.text}`}>
                  {stat.label}
                </CardTitle>
              </div>
              <div className={`flex h-full items-center justify-center ${stat.bg} ${stat.text}`}>
                {stat.type === 'metrics' ? (
                  <div className="grid h-full w-full grid-rows-2 divide-y divide-white/60">
                    {stat.metrics.map((metric) => (
                      <div
                        key={metric.label}
                        className="flex min-w-0 items-center justify-between gap-2 px-3"
                      >
                        <span className="shrink-0 text-xs font-medium">{metric.label}</span>
                        <span className="min-w-0 whitespace-nowrap text-right text-2xl font-semibold tabular-nums">
                          {metric.value}
                        </span>
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
              <div
                key={`${log.timestamp}-${index}-${log.message}`}
                className="flex gap-3 leading-6"
              >
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
