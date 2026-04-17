import { useQuery } from '@tanstack/react-query';
import { logApi } from '@/shared/api/modules';
import { Card, CardContent, CardHeader, CardTitle, Badge, Skeleton } from '@/shared/components/ui';
import { formatDate } from '@/shared/lib/format';
import { FileText } from 'lucide-react';

const actionLabels: Record<string, string> = {
  create_agent: '创建 Agent',
  update_agent: '更新 Agent',
  delete_agent: '删除 Agent',
  restart_agent: '重启 Agent',
  import_agents: '批量导入 Agent',
  upload_avatar: '上传头像',
  create_model: '创建模型',
  update_model: '更新模型',
  delete_model: '删除模型',
  update_system: '更新系统配置',
  restart_system: '重启 Scheduler',
  login: '登录',
};

const targetLabels: Record<string, string> = {
  agent: 'Agent',
  model: '模型',
  system: '系统',
};

export default function LogPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['logs'],
    queryFn: () => logApi.list(0, 500),
  });

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">操作日志</h1>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">操作</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">目标类型</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">目标 ID</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">操作用户</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">时间</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.items.map((log) => (
                    <tr key={log.id} className="border-b border-border hover:bg-muted/50 transition-colors">
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <FileText size={14} className="text-muted-foreground" />
                          <span className="text-sm">{actionLabels[log.action] || log.action}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant="outline">
                          {targetLabels[log.target_type] || log.target_type}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {log.target_id ?? '-'}
                      </td>
                      <td className="py-3 px-4 text-sm">操作员 #{log.operator_id}</td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {formatDate(log.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data?.items.length === 0 && (
                <div className="py-12 text-center text-muted-foreground">暂无操作日志</div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
