import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, Terminal, Trash2 } from 'lucide-react';
import { adminApi, adminKeys } from '@/features/admin';
import { Button, Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui';

const levelColors: Record<string, string> = {
  INFO: 'text-green-400',
  WARNING: 'text-yellow-400',
  ERROR: 'text-red-400',
  DEBUG: 'text-blue-400',
};

export default function AdminDashboardPage() {
  const [keyword, setKeyword] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const logRef = useRef<HTMLDivElement>(null);

  const { data: stats } = useQuery({
    queryKey: adminKeys.stats,
    queryFn: adminApi.dashboardStats,
    refetchInterval: 3000,
  });

  const { data: logs, refetch } = useQuery({
    queryKey: adminKeys.terminal(keyword),
    queryFn: () => adminApi.terminalLogs({ count: 240, keyword: keyword.trim() || undefined }),
    refetchInterval: 2000,
  });

  useEffect(() => {
    if (autoScroll && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs?.items, autoScroll]);

  const handleScroll = () => {
    if (!logRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = logRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 50);
  };

  const formatPercent = (value?: number) => {
    if (value === undefined || value === null) return '0%';
    if (value > 0 && value < 0.1) return '<0.1%';
    if (value < 10) return `${value.toFixed(1)}%`;
    return `${Math.round(value)}%`;
  };

  const statCards = [
    {
      label: '总用户数',
      value: stats?.total_users ?? 0,
      bg: 'bg-emerald-100',
      text: 'text-emerald-950',
    },
    {
      label: 'DAU',
      value: stats?.daily_active_users ?? 0,
      bg: 'bg-amber-100',
      text: 'text-amber-950',
    },
    {
      label: '性能占用',
      bg: 'bg-sky-100',
      text: 'text-sky-950',
      metrics: [
        { label: 'CPU', value: formatPercent(stats?.cpu_usage_percent) },
        { label: '内存', value: formatPercent(stats?.memory_usage_percent) },
      ],
    },
  ];

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">仪表盘</h1>
      <div className="mb-4 flex flex-wrap gap-4">
        {statCards.map((stat) => (
          <Card
            key={stat.label}
            className="aspect-[2/1] w-64 max-w-full overflow-hidden rounded-lg"
          >
            <div className="grid h-full grid-cols-2">
              <div className="flex items-center justify-center p-5 text-center">
                <CardTitle className={`text-xl font-semibold leading-7 ${stat.text}`}>
                  {stat.label}
                </CardTitle>
              </div>
              <div
                className={`flex h-full items-center justify-center text-center ${stat.bg} ${stat.text}`}
              >
                {'metrics' in stat ? (
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
                  <span className="break-words px-4 text-5xl font-semibold tabular-nums">
                    {stat.value}
                  </span>
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>

      <Card className="rounded-lg">
        <CardHeader className="flex flex-col gap-3 space-y-0 p-4 pb-2 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-2">
            <Terminal size={18} className="text-muted-foreground" />
            <CardTitle>终端日志</CardTitle>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="relative">
              <Search
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              />
              <input
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                placeholder="搜索日志内容..."
                className="h-9 w-full rounded-md border border-input bg-background pl-8 pr-3 text-sm sm:w-56"
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              className="rounded-md"
              onClick={async () => {
                await adminApi.clearTerminalLogs();
                refetch();
              }}
            >
              <Trash2 size={14} className="mr-1" />
              清空
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-4 pt-0">
          <div
            ref={logRef}
            onScroll={handleScroll}
            className="h-96 overflow-auto rounded-lg bg-zinc-950 p-4 font-mono text-sm"
          >
            {logs?.items.map((log, index) => (
              <div key={`${log.timestamp}-${index}`} className="flex gap-3 leading-6">
                <span className={`w-20 shrink-0 ${levelColors[log.level] || 'text-zinc-400'}`}>
                  [{log.level}]
                </span>
                <span className="break-all text-zinc-300">{log.message}</span>
              </div>
            ))}
            {(!logs?.items || logs.items.length === 0) && (
              <div className="py-12 text-center text-zinc-500">暂无终端日志</div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
