import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, Plus } from 'lucide-react';
import {
  ADMIN_PERMISSIONS,
  adminApi,
  adminKeys,
  useAdminAuthStore,
  type AdminCreateRequest,
  type AdminPermission,
} from '@/features/admin';
import { Button, Card, CardContent, CardHeader, CardTitle, Input } from '@/shared/components/ui';
import { AdminPagination } from './AdminPagination';

const PAGE_SIZE = 50;

const permissionLabels: Record<AdminPermission, string> = {
  view_dashboard: '查看仪表盘',
  manage_users: '管理用户',
  manage_content: '管理内容',
  manage_hot_topics: '管理热点',
  manage_admins: '管理管理员',
  view_logs: '查看日志',
};

export default function AdminAdminsPage() {
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  const [operationError, setOperationError] = useState('');
  const [page, setPage] = useState(0);
  const currentAdmin = useAdminAuthStore(state => state.admin);
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: [...adminKeys.admins, page],
    queryFn: () => adminApi.admins({ skip: page * PAGE_SIZE, limit: PAGE_SIZE }),
  });
  const createMutation = useMutation({
    mutationFn: adminApi.createAdmin,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.admins });
      setCreating(false);
      setCreateError('');
    },
    onError: (error: { message?: string }) =>
      setCreateError(error.message || '创建管理员失败，请稍后重试'),
  });
  const updateMutation = useMutation({
    mutationFn: ({ adminId, isActive }: { adminId: number; isActive: boolean }) =>
      adminApi.updateAdmin(adminId, { is_active: isActive }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminKeys.admins });
      setOperationError('');
    },
    onError: (error: { message?: string }) =>
      setOperationError(error.message || '更新管理员失败，请稍后重试'),
  });

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">管理员</h1>
        <Button
          className="rounded-md"
          onClick={() => {
            setCreateError('');
            setCreating(true);
          }}
        >
          <Plus size={16} className="mr-1" />
          添加管理员
        </Button>
      </div>

      {operationError && (
        <div className="mb-4 flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{operationError}</span>
        </div>
      )}

      <Card className="rounded-lg">
        <CardContent className="p-0">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="border-b bg-muted/50 text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">用户名</th>
                <th className="px-4 py-3 font-medium">权限</th>
                <th className="px-4 py-3 font-medium">状态</th>
                <th className="px-4 py-3 font-medium">上次登录</th>
                <th className="px-4 py-3 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map(admin => {
                const canToggleAdmin = Boolean(
                  currentAdmin &&
                  admin.id !== currentAdmin.id &&
                  (!admin.is_super_admin || currentAdmin.is_super_admin)
                );

                return (
                  <tr key={admin.id} className="border-b last:border-0">
                    <td className="px-4 py-3">
                      <p className="font-medium">{admin.username}</p>
                      {admin.email && (
                        <p className="text-xs text-muted-foreground">{admin.email}</p>
                      )}
                    </td>
                    <td className="max-w-md px-4 py-3">
                      {admin.is_super_admin
                        ? '全部权限'
                        : admin.permissions.map(p => permissionLabels[p]).join('、')}
                    </td>
                    <td className="px-4 py-3">{admin.is_active ? '启用' : '停用'}</td>
                    <td className="px-4 py-3">
                      {admin.last_login ? new Date(admin.last_login).toLocaleString() : '从未登录'}
                    </td>
                    <td className="px-4 py-3">
                      {canToggleAdmin && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="rounded-md"
                          onClick={() =>
                            updateMutation.mutate({ adminId: admin.id, isActive: !admin.is_active })
                          }
                        >
                          {admin.is_active ? '停用' : '启用'}
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <AdminPagination
        page={page}
        pageSize={PAGE_SIZE}
        total={data?.total ?? 0}
        onPageChange={setPage}
      />

      {creating && (
        <CreateAdminDialog
          assignablePermissions={
            currentAdmin?.is_super_admin
              ? [...ADMIN_PERMISSIONS]
              : (currentAdmin?.permissions ?? [])
          }
          canCreateSuperAdmin={Boolean(currentAdmin?.is_super_admin)}
          saving={createMutation.isPending}
          error={createError}
          onClose={() => {
            setCreating(false);
            setCreateError('');
          }}
          onSubmit={payload => createMutation.mutate(payload)}
        />
      )}
    </div>
  );
}

function CreateAdminDialog({
  assignablePermissions,
  canCreateSuperAdmin,
  saving,
  error,
  onClose,
  onSubmit,
}: {
  assignablePermissions: AdminPermission[];
  canCreateSuperAdmin: boolean;
  saving: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (payload: AdminCreateRequest) => void;
}) {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [permissions, setPermissions] = useState<AdminPermission[]>(() =>
    assignablePermissions.includes('view_dashboard')
      ? ['view_dashboard']
      : assignablePermissions.slice(0, 1)
  );
  const [superAdmin, setSuperAdmin] = useState(false);

  const togglePermission = (permission: AdminPermission) => {
    setPermissions(value =>
      value.includes(permission)
        ? value.filter(item => item !== permission)
        : [...value, permission]
    );
  };

  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-xl rounded-lg shadow-xl">
        <CardHeader>
          <CardTitle>添加管理员</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          <Input
            value={username}
            onChange={event => setUsername(event.target.value)}
            placeholder="用户名"
            minLength={1}
            maxLength={30}
          />
          <Input
            value={email}
            onChange={event => setEmail(event.target.value)}
            placeholder="申诉邮箱（可选）"
            type="email"
          />
          <Input
            value={password}
            onChange={event => setPassword(event.target.value)}
            placeholder="初始密码，至少 8 位"
            type="password"
            minLength={8}
            maxLength={32}
          />
          {canCreateSuperAdmin && (
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={superAdmin}
                onChange={event => setSuperAdmin(event.target.checked)}
              />
              超级管理员
            </label>
          )}
          {!superAdmin && (
            <div className="grid gap-2 sm:grid-cols-2">
              {assignablePermissions.map(permission => (
                <label key={permission} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={permissions.includes(permission)}
                    onChange={() => togglePermission(permission)}
                  />
                  {permissionLabels[permission]}
                </label>
              ))}
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="outline" className="rounded-md" onClick={onClose} disabled={saving}>
              取消
            </Button>
            <Button
              className="rounded-md"
              disabled={saving || username.trim().length < 1 || password.length < 8}
              onClick={() =>
                onSubmit({
                  username: username.trim(),
                  email: email.trim() || undefined,
                  password,
                  permissions: superAdmin ? [...ADMIN_PERMISSIONS] : permissions,
                  is_active: true,
                  is_super_admin: superAdmin,
                })
              }
            >
              创建
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
