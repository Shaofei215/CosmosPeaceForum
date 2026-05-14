import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '@/features/auth/api';
import { useAuthStore } from '@/features/auth';
import { Card, CardContent } from '@/shared/components/ui';

function getSafeRedirect(value: string | null): string {
  if (!value || !value.startsWith('/') || value.startsWith('//')) {
    return '/feed';
  }
  return value;
}

export default function ManagementLoginPage() {
  const navigate = useNavigate();
  const { setAuth, logout } = useAuthStore();
  const [error, setError] = useState('');

  useEffect(() => {
    const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const searchParams = new URLSearchParams(window.location.search);
    const token = hashParams.get('token') || searchParams.get('token');
    const redirect = getSafeRedirect(hashParams.get('redirect') || searchParams.get('redirect'));

    if (!token) {
      setError('缺少登录令牌，请从管理端重新进入。');
      return;
    }

    localStorage.setItem('token', token);
    window.history.replaceState(null, '', '/management-login');

    authApi.getCurrentUser()
      .then((user) => {
        setAuth(token, user);
        navigate(redirect, { replace: true });
      })
      .catch(() => {
        logout();
        setError('登录令牌无效或已过期，请从管理端重新进入。');
      });
  }, [logout, navigate, setAuth]);

  return (
    <div className="min-h-[60vh] flex items-center justify-center p-4">
      <Card className="w-full max-w-md rounded-lg bg-white shadow-sm border">
        <CardContent className="p-6 text-center text-sm text-muted-foreground">
          {error || '正在登录角色账号...'}
        </CardContent>
      </Card>
    </div>
  );
}
