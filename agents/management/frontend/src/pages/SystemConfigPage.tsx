import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { systemApi } from '@/shared/api/modules';
import {
  Button, Input, Card, CardContent, Switch,
} from '@/shared/components/ui';
import { Settings, Edit, Eye, EyeOff } from 'lucide-react';

const PASSWORD_KEYS = ['AI_USER_PASSWORD', 'TAVILY_API_KEY'];
const BOOLEAN_KEYS = ['MEMORY_ENABLED', 'WEB_SEARCH_ENABLED'];
const INPUT_PLACEHOLDERS: Record<string, string> = {
  TAVILY_INCLUDE_DOMAINS: '例如 who.int, un.org',
  TAVILY_EXCLUDE_DOMAINS: '多个域名用逗号分隔',
};
const SELECT_OPTIONS: Record<string, Array<{ value: string; label: string }>> = {
  TAVILY_TOPIC: [
    { value: '', label: '由 Agent 填写' },
    { value: 'general', label: 'general' },
    { value: 'news', label: 'news' },
    { value: 'finance', label: 'finance' },
  ],
  TAVILY_SEARCH_DEPTH: [
    { value: '', label: '由 Agent 填写' },
    { value: 'basic', label: 'basic' },
    { value: 'advanced', label: 'advanced' },
    { value: 'fast', label: 'fast' },
    { value: 'ultra-fast', label: 'ultra-fast' },
  ],
};

const configGroupLabels: Record<string, string[]> = {
  '通用': ['ADMIN_KEY', 'AI_USER_PASSWORD', 'SOCIAL_PLATFORM_API_BASE_URL', 'LOG_LEVEL'],
  '调度器': ['SCHEDULER_TIME_SCALE'],
  'LangGraph': ['LANGGRAPH_MAX_STEPS', 'LANGGRAPH_TOOL_TIMEOUT'],
  '联网搜索': [
    'WEB_SEARCH_ENABLED',
    'TAVILY_API_KEY',
    'TAVILY_TOPIC',
    'TAVILY_MAX_RESULTS',
    'TAVILY_SEARCH_DEPTH',
    'TAVILY_INCLUDE_DOMAINS',
    'TAVILY_EXCLUDE_DOMAINS',
  ],
  '记忆': [
    'MEMORY_ENABLED',
    'MEMORY_RECALL_LIMIT',
    'MEMORY_RECALL_VECTOR_RESULTS',
    'MEMORY_RECALL_BM25_RESULTS',
    'MEMORY_RECALL_MAX_CANDIDATES',
    'MEMORY_RRF_RANK_CONSTANT',
    'MEMORY_IMPORTANCE_WEIGHT',
    'MEMORY_THRESHOLD',
    'MEMORY_BOOST_FACTOR',
    'MEMORY_BOOST_COOLDOWN_SECONDS',
    'MEMORY_DECAY_RATE',
    'MEMORY_DECAY_INTERVAL_SECONDS',
  ],
};

function getConfigGroup(key: string): string {
  for (const [group, keys] of Object.entries(configGroupLabels)) {
    if (keys.includes(key)) return group;
  }
  return '其他';
}

export default function SystemConfigPage() {
  const queryClient = useQueryClient();
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [visiblePasswords, setVisiblePasswords] = useState<Set<string>>(new Set());

  const { data: configs, isLoading } = useQuery({
    queryKey: ['system'],
    queryFn: systemApi.list,
  });

  const updateMutation = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) =>
      systemApi.update(key, value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system'] });
      setEditingKey(null);
    },
  });

  const groupedConfigs: Record<string, typeof configs> = {};
  configs?.forEach((c) => {
    const group = getConfigGroup(c.key);
    if (!groupedConfigs[group]) groupedConfigs[group] = [];
    groupedConfigs[group].push(c);
  });

  if (isLoading) {
    return (
      <div>
        <h1 className="text-2xl font-bold mb-6">系统配置</h1>
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Card key={i}><CardContent className="p-4"><div className="h-4 bg-muted rounded w-3/4 animate-pulse" /></CardContent></Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">系统配置</h1>
      </div>

      {Object.entries(groupedConfigs).map(([group, items]) => (
        <div key={group} className="mb-6">
          <div className="mb-3 flex items-center gap-3">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <Settings size={18} /> {group}
            </h2>
            {group === '联网搜索' && (
              <a
                href="https://app.tavily.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-sky-600 transition-colors hover:text-sky-700 hover:underline"
              >
                开始使用 Tavily
              </a>
            )}
          </div>
          <Card>
            <CardContent className="p-0">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 px-4 text-sm font-medium text-muted-foreground w-1/4">配置键</th>
                    <th className="text-left py-2 px-4 text-sm font-medium text-muted-foreground w-1/4">说明</th>
                    <th className="text-left py-2 px-4 text-sm font-medium text-muted-foreground w-1/3">值</th>
                    <th className="text-right py-2 px-4 text-sm font-medium text-muted-foreground w-20">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {items && items.map((config) => (
                    <tr key={config.key} className="border-b border-border hover:bg-muted/50">
                      <td className="py-2 px-4 text-sm font-mono">{config.key}</td>
                      <td className="py-2 px-4 text-sm text-muted-foreground">{config.description}</td>
                      <td className="py-2 px-4 text-sm">
                        {BOOLEAN_KEYS.includes(config.key) ? (
                          <Switch
                            checked={config.value.toLowerCase() === 'true'}
                            onCheckedChange={(checked) => {
                              updateMutation.mutate({ key: config.key, value: checked ? 'true' : 'false' });
                            }}
                            disabled={updateMutation.isPending}
                          />
                        ) : SELECT_OPTIONS[config.key] ? (
                          <select
                            value={editingKey === config.key ? editValue : config.value}
                            onChange={(event) => {
                              if (editingKey === config.key) setEditValue(event.target.value);
                            }}
                            disabled={editingKey !== config.key}
                            className="h-7 w-full rounded-md border border-input bg-background px-3 text-sm disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {SELECT_OPTIONS[config.key].map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <div className="relative">
                            <Input
                              type={
                                config.key === 'TAVILY_MAX_RESULTS'
                                  ? 'number'
                                  : PASSWORD_KEYS.includes(config.key) &&
                                      !visiblePasswords.has(config.key)
                                    ? 'password'
                                    : 'text'
                              }
                              min={config.key === 'TAVILY_MAX_RESULTS' ? 1 : undefined}
                              max={config.key === 'TAVILY_MAX_RESULTS' ? 20 : undefined}
                              placeholder={INPUT_PLACEHOLDERS[config.key]}
                              value={editingKey === config.key ? editValue : config.value}
                              onChange={(e) => {
                                if (editingKey === config.key) setEditValue(e.target.value);
                              }}
                              disabled={editingKey !== config.key}
                              className={`text-sm h-7 ${PASSWORD_KEYS.includes(config.key) ? 'pr-10' : ''}`}
                            />
                            {PASSWORD_KEYS.includes(config.key) && (
                              <button
                                type="button"
                                onClick={() => {
                                  const next = new Set(visiblePasswords);
                                  if (next.has(config.key)) {
                                    next.delete(config.key);
                                  } else {
                                    next.add(config.key);
                                  }
                                  setVisiblePasswords(next);
                                }}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                tabIndex={-1}
                              >
                                {visiblePasswords.has(config.key) ? <EyeOff size={14} /> : <Eye size={14} />}
                              </button>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="py-2 px-4 text-right">
                        {BOOLEAN_KEYS.includes(config.key) ? (
                          <span className="text-sm text-muted-foreground">-</span>
                        ) : editingKey === config.key ? (
                          <div className="flex justify-end gap-1">
                            <Button
                              size="sm"
                              onClick={() => updateMutation.mutate({ key: config.key, value: editValue })}
                              disabled={updateMutation.isPending}
                            >
                              保存
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => setEditingKey(null)}>
                              取消
                            </Button>
                          </div>
                        ) : (
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => {
                              setEditingKey(config.key);
                              setEditValue(config.value);
                            }}
                          >
                            <Edit size={14} />
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      ))}

    </div>
  );
}
