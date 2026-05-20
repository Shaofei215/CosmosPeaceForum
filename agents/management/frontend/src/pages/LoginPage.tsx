import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useLogin } from '@/features/auth';
import { Button, Input, Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui';
import { BigLogo } from '@/shared/components/auth/BigLogo';

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const { mutate: login, isPending } = useLogin();

  const from = (location.state as { from?: { pathname?: string } })?.from?.pathname || '/';

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!username.trim()) {
      setError('请输入用户名');
      return;
    }
    if (!password.trim()) {
      setError('请输入密码');
      return;
    }

    login(
      { username: username.trim(), password },
      {
        onSuccess: () => {
          navigate(from, { replace: true });
        },
        onError: (err: { message?: string }) => {
          setError(err.message || '登录失败，请检查用户名和密码');
        },
      }
    );
  };

  return (
    <div className="auth-page" data-auth-word="Login">
      <BigLogo />
      <Card className="auth-card w-full max-w-md rounded-lg bg-white shadow-sm border">
        <CardHeader className="space-y-2 text-center">
          <CardTitle className="text-2xl font-bold">登录</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 text-sm text-red-600 bg-red-50 rounded-lg border border-red-200">
                {error}
              </div>
            )}

            <div className="space-y-2">
              <label htmlFor="username" className="text-sm font-medium">用户名</label>
              <Input
                id="username"
                type="text"
                placeholder="请输入用户名"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={isPending}
                autoComplete="username"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium">密码</label>
              <Input
                id="password"
                type="password"
                placeholder="请输入密码"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isPending}
                autoComplete="current-password"
              />
            </div>

            <Button type="submit" className="w-full" disabled={isPending}>
              {isPending ? '登录中...' : '登录'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
