import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { useCurrentAdmin } from '@/features/auth';
import { adminApi } from '@/shared/api/modules';
import {
  ADMIN_PERMISSIONS,
  type AdminCreateRequest,
  type AdminPermission,
} from '@/shared/types/api';
import { Button, Card, CardContent, CardHeader, CardTitle, Input } from '@/shared/components/ui';

const permissionLabels: Record<AdminPermission, string> = {
  view_dashboard: '查看仪表盘',
  manage_agents: '管理角色',
  manage_models: '管理模型',
  manage_memories: '管理记忆',
  manage_prompts: '管理提示词',
  manage_system: '管理系统',
  manage_admins: '管理管理员',
  view_logs: '查看日志',
};

export default function AdminListPage() {
  const [creating, setCreating] = useState(false);
  const { data: currentAdmin } = useCurrentAdmin();
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ['admins'],
    queryFn: () => adminApi.list(0, 100),
  });
  const createMutation = useMutation({
    mutationFn: adminApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admins'] });
      setCreating(false);
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({ adminId, isActive }: { adminId: number; isActive: boolean }) =>
      adminApi.update(adminId, { is_active: isActive }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admins'] }),
  });

  return (
    <div>
      <div className="mb-6 flex items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">管理员</h1>
        <Button className="rounded-md" onClick={() => setCreating(true)}>
          <Plus size={16} className="mr-1" />
          添加管理员
        </Button>
      </div>

      <Card className="rounded-lg">
        <CardContent className="p-0">
          <div className="overflow-auto">
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
                {data?.items.map((admin) => {
                  const canToggleAdmin = admin.id !== currentAdmin?.id && !admin.is_super_admin;

                  return (
                    <tr key={admin.id} className="border-b last:border-0">
                      <td className="px-4 py-3">
                        <p className="font-medium">{admin.username}</p>
                        <p className="text-xs text-muted-foreground">
                          {admin.is_super_admin ? '超级管理员' : `ID ${admin.id}`}
                        </p>
                        {admin.email && (
                          <p className="text-xs text-muted-foreground">{admin.email}</p>
                        )}
                      </td>
                      <td className="max-w-md px-4 py-3">
                        {admin.is_super_admin
                          ? '全部权限'
                          : admin.permissions.map((permission) => permissionLabels[permission]).join('、')}
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
                {(!data?.items || data.items.length === 0) && (
                  <tr>
                    <td className="px-4 py-10 text-center text-muted-foreground" colSpan={5}>
                      暂无管理员
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {creating && (
        <CreateAdminDialog
          saving={createMutation.isPending}
          onClose={() => setCreating(false)}
          onSubmit={(payload) => createMutation.mutate(payload)}
        />
      )}
    </div>
  );
}

function CreateAdminDialog({
  saving,
  onClose,
  onSubmit,
}: {
  saving: boolean;
  onClose: () => void;
  onSubmit: (payload: AdminCreateRequest) => void;
}) {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [permissions, setPermissions] = useState<AdminPermission[]>(['view_dashboard']);
  const [superAdmin, setSuperAdmin] = useState(false);

  const togglePermission = (permission: AdminPermission) => {
    setPermissions((value) =>
      value.includes(permission)
        ? value.filter((item) => item !== permission)
        : [...value, permission],
    );
  };

  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-xl rounded-lg shadow-xl">
        <CardHeader>
          <CardTitle>添加管理员</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="用户名"
          />
          <Input
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="邮箱（可选）"
            type="email"
          />
          <Input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="初始密码，至少 8 位"
            type="password"
          />
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={superAdmin}
              onChange={(event) => setSuperAdmin(event.target.checked)}
            />
            超级管理员
          </label>
          {!superAdmin && (
            <div className="grid gap-2 sm:grid-cols-2">
              {ADMIN_PERMISSIONS.map((permission) => (
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
              disabled={saving}
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
