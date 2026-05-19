import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Shield } from 'lucide-react';
import { useAdminLogin } from '@/features/admin';
import { Button, Card, CardContent, CardHeader, CardTitle, Input } from '@/shared/components/ui';

function getRedirectPath(state: unknown): string {
  const value = state as { from?: { pathname?: string } };
  const path = value?.from?.pathname;
  return path && path.startsWith('/admin') ? path : '/admin/dashboard';
}

export default function AdminLoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const login = useAdminLogin();

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    login.mutate(
      { username: username.trim(), password },
      {
        onSuccess: data => {
          navigate(
            data.admin.must_change_credentials ? '/admin/setup' : getRedirectPath(location.state),
            {
              replace: true,
            }
          );
        },
        onError: (err: { message?: string }) => {
          setError(err.message || '登录失败');
        },
      }
    );
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md rounded-lg shadow-xl">
        <CardHeader className="space-y-2 text-center">
          <div className="mb-2 flex justify-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
              <Shield size={24} className="text-primary" />
            </div>
          </div>
          <CardTitle className="text-2xl font-bold">平台管理后台</CardTitle>
          <p className="text-sm text-muted-foreground">管理员登录</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <label htmlFor="admin-username" className="text-sm font-medium">
                用户名
              </label>
              <Input
                id="admin-username"
                value={username}
                onChange={event => setUsername(event.target.value)}
                disabled={login.isPending}
                autoComplete="username"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="admin-password" className="text-sm font-medium">
                密码
              </label>
              <Input
                id="admin-password"
                type="password"
                value={password}
                onChange={event => setPassword(event.target.value)}
                disabled={login.isPending}
                autoComplete="current-password"
              />
            </div>
            <Button type="submit" className="w-full rounded-md" disabled={login.isPending}>
              {login.isPending ? '登录中...' : '登录'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
