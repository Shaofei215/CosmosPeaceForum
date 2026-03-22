/**
 * 登录页面
 */

import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useLogin } from '@/features/auth';
import { Button, Input, Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui';

/**
 * 登录页面组件
 */
export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const { mutate: login, isPending } = useLogin();

  // 获取登录后要跳转的路径
  const from = (location.state as { from?: { pathname?: string } })?.from?.pathname || '/';

  /**
   * 处理登录提交
   */
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!username.trim() || !password.trim()) {
      setError('请输入用户名和密码');
      return;
    }

    login(
      { username, password },
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
    <div className="min-h-screen flex items-center justify-center bg-muted/50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold text-center">登录</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 text-sm text-red-500 bg-red-50 rounded-md">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <label htmlFor="username" className="text-sm font-medium">
                用户名
              </label>
              <Input
                id="username"
                type="text"
                placeholder="请输入用户名"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={isPending}
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium">
                密码
              </label>
              <Input
                id="password"
                type="password"
                placeholder="请输入密码"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isPending}
              />
            </div>
            <Button type="submit" className="w-full" disabled={isPending}>
              {isPending ? '登录中...' : '登录'}
            </Button>
          </form>
          <div className="mt-4 text-center text-sm">
            还没有账号？{' '}
            <Link to="/register" className="text-primary hover:underline">
              立即注册
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
