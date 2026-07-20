/**
 * Management 管理端跳转到公开平台角色账号时的登录桥。
 *
 * 管理端会通过 URL hash/search 传入 access_token 和 refresh_token；本页写入
 * sessionStorage 后立即替换地址栏，避免 token 长时间暴露在浏览器历史中。
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '@/features/auth/api';
import { useAuthStore } from '@/features/auth';
import { setTokens } from '@/features/auth/tokenStorage';
import { Card, CardContent } from '@/shared/components/ui';
import { AuthIllustration, BigLogo } from '@/shared/components/auth/BigLogo';
import { copywriting } from '@/shared/config/copywriting';

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
    const refreshToken = hashParams.get('refresh_token') || searchParams.get('refresh_token');
    const redirect = getSafeRedirect(hashParams.get('redirect') || searchParams.get('redirect'));

    if (!token || !refreshToken) {
      setError(copywriting('auth.management_token_missing', '缺少登录令牌，请从管理端重新进入。'));
      return;
    }

    setTokens(token, refreshToken, false);
    window.history.replaceState(null, '', '/management-login');

    authApi
      .getCurrentUser()
      .then(user => {
        setAuth(token, user);
        navigate(redirect, { replace: true });
      })
      .catch(() => {
        logout();
        setError(
          copywriting('auth.management_token_invalid', '登录令牌无效或已过期，请从管理端重新进入。')
        );
      });
  }, [logout, navigate, setAuth]);

  return (
    <div className="auth-page" data-auth-word="Login">
      <AuthIllustration />
      <BigLogo />
      <Card className="auth-card w-full max-w-md rounded-lg bg-white shadow-sm border">
        <CardContent className="auth-card-content p-6 text-center text-sm text-muted-foreground">
          {error || copywriting('auth.management_logging_in', '正在登录角色账号...')}
        </CardContent>
      </Card>
    </div>
  );
}
