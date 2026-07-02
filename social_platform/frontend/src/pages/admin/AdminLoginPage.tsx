/**
 * 平台管理员登录页。
 *
 * remember_me 默认不勾选，交给后端决定 refresh/session 生命周期。
 */

import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAdminLogin } from '@/features/admin';
import { Button, Card, CardContent, CardHeader, CardTitle, Input } from '@/shared/components/ui';
import { AuthIllustration, BigLogo } from '@/shared/components/auth/BigLogo';

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
  const [rememberMe, setRememberMe] = useState(false);
  const login = useAdminLogin();

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    login.mutate(
      { username: username.trim(), password, remember_me: rememberMe },
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
    <div className="auth-page management-compact bg-background" data-auth-word="Login">
      <AuthIllustration />
      <BigLogo />
      <Card className="auth-card w-full max-w-md rounded-lg bg-white shadow-sm border">
        <CardHeader className="space-y-2 text-center">
          <CardTitle className="text-2xl font-bold">登录</CardTitle>
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
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={event => setRememberMe(event.target.checked)}
                disabled={login.isPending}
                className="h-4 w-4 rounded border-gray-300"
              />
              记住我
            </label>
            <Button type="submit" className="w-full rounded-md" disabled={login.isPending}>
              {login.isPending ? '登录中...' : '登录'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
