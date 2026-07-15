import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { systemApi } from '@/shared/api/modules';
import {
  Button, Input, Card, CardContent, Switch,
} from '@/shared/components/ui';
import { Settings, Edit, Eye, EyeOff } from 'lucide-react';

const PASSWORD_KEYS = ['AI_USER_PASSWORD', 'TAVILY_API_KEY'];
const BOOLEAN_KEYS = ['MEMORY_ENABLED', 'WEB_SEARCH_ENABLED'];

const configGroupLabels: Record<string, string[]> = {
  '通用': ['ADMIN_KEY', 'AI_USER_PASSWORD', 'SOCIAL_PLATFORM_API_BASE_URL', 'LOG_LEVEL'],
  '调度器': ['SCHEDULER_TIME_SCALE'],
  'LangGraph': ['LANGGRAPH_MAX_STEPS', 'LANGGRAPH_TOOL_TIMEOUT'],
  '联网搜索': ['WEB_SEARCH_ENABLED', 'TAVILY_API_KEY'],
  '记忆': [
    'MEMORY_ENABLED',
    'MEMORY_RECALL_LIMIT',
    'MEMORY_RECALL_VECTOR_RESULTS',
    'MEMORY_RECALL_BM25_RESULTS',
    'MEMORY_RRF_RANK_CONSTANT',
    'MEMORY_THRESHOLD',
    'MEMORY_BOOST_FACTOR',
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
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <Settings size={18} /> {group}
          </h2>
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
                        ) : (
                          <div className="relative">
                            <Input
                              type={PASSWORD_KEYS.includes(config.key) && !visiblePasswords.has(config.key) ? 'password' : 'text'}
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
