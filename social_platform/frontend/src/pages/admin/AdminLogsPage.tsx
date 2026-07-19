import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { adminApi, adminKeys } from '@/features/admin';
import { Card, CardContent } from '@/shared/components/ui';
import { AdminPagination } from './AdminPagination';

const PAGE_SIZE = 50;

export default function AdminLogsPage() {
  const [page, setPage] = useState(0);
  const { data } = useQuery({
    queryKey: [...adminKeys.operations, page],
    queryFn: () => adminApi.operationLogs({ skip: page * PAGE_SIZE, limit: PAGE_SIZE }),
  });

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">操作日志</h1>
      <Card className="rounded-lg">
        <CardContent className="p-0">
          <div className="overflow-auto">
            <table className="w-full min-w-[860px] text-sm">
              <thead className="border-b bg-muted/50 text-left text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">时间</th>
                  <th className="px-4 py-3 font-medium">管理员</th>
                  <th className="px-4 py-3 font-medium">动作</th>
                  <th className="px-4 py-3 font-medium">对象</th>
                  <th className="px-4 py-3 font-medium">详情</th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map(log => (
                  <tr key={log.id} className="border-b last:border-0">
                    <td className="px-4 py-3">{new Date(log.created_at).toLocaleString()}</td>
                    <td className="px-4 py-3">{log.operator_username || '-'}</td>
                    <td className="px-4 py-3">{log.action}</td>
                    <td className="px-4 py-3">
                      {log.target_type}
                      {log.target_id ? ` #${log.target_id}` : ''}
                    </td>
                    <td className="max-w-md px-4 py-3">
                      <span className="line-clamp-2 text-muted-foreground">{log.details}</span>
                    </td>
                  </tr>
                ))}
                {(!data?.items || data.items.length === 0) && (
                  <tr>
                    <td className="px-4 py-10 text-center text-muted-foreground" colSpan={5}>
                      暂无日志
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
      <AdminPagination
        page={page}
        pageSize={PAGE_SIZE}
        total={data?.total ?? 0}
        onPageChange={setPage}
      />
    </div>
  );
}
