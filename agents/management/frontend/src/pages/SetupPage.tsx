/**
 * Management 管理员首次登录设置页。
 *
 * 该页面只处理当前管理员自己的初始用户名和密码修改，成功后进入管理后台首页。
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle } from 'lucide-react';
import { useProfileUpdate } from '@/features/auth';
import { AuthIllustration, BigLogo } from '@/shared/components/auth/BigLogo';
import { Button, Card, CardContent, CardHeader, CardTitle, Input } from '@/shared/components/ui';

export default function SetupPage() {
  const navigate = useNavigate();
  const updateProfile = useProfileUpdate();
  const [currentPassword, setCurrentPassword] = useState('');
  const [username, setUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setError('');

    updateProfile.mutate(
      {
        current_password: currentPassword,
        username: username.trim(),
        new_password: newPassword,
      },
      {
        onSuccess: () => navigate('/dashboard', { replace: true }),
        onError: (err: { message?: string }) => setError(err.message || '保存失败'),
      },
    );
  };

  return (
    <div className="auth-page" data-auth-word="Setup">
      <AuthIllustration />
      <BigLogo />
      <Card className="auth-card w-full max-w-lg rounded-lg border bg-card shadow-sm">
        <CardHeader className="space-y-2 text-center">
          <CardTitle className="text-2xl font-bold">首次登录设置</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="auth-alert text-sm">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="space-y-2">
              <label htmlFor="current-password" className="text-sm font-medium">
                当前初始密码
              </label>
              <Input
                id="current-password"
                type="password"
                placeholder="请输入当前初始密码"
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
                disabled={updateProfile.isPending}
                autoComplete="current-password"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="setup-username" className="text-sm font-medium">
                新管理员用户名
              </label>
              <Input
                id="setup-username"
                placeholder="请输入新的管理员用户名"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                disabled={updateProfile.isPending}
                autoComplete="username"
                minLength={1}
                maxLength={30}
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="setup-password" className="text-sm font-medium">
                新管理员密码
              </label>
              <Input
                id="setup-password"
                type="password"
                placeholder="至少 8 位"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                disabled={updateProfile.isPending}
                autoComplete="new-password"
                minLength={8}
                maxLength={32}
              />
            </div>

            <Button
              type="submit"
              className="w-full"
              disabled={
                updateProfile.isPending ||
                username.trim().length === 0 ||
                username.trim().length > 30 ||
                newPassword.length < 8 ||
                newPassword.length > 32
              }
            >
              {updateProfile.isPending ? '保存中...' : '保存并进入后台'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
