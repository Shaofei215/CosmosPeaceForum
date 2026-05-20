import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, CardContent, CardHeader, CardTitle, Input } from '@/shared/components/ui';
import { useAdminProfileUpdate } from '@/features/admin';
import { BigLogo } from '@/shared/components/auth/BigLogo';

export default function AdminSetupPage() {
  const navigate = useNavigate();
  const updateProfile = useAdminProfileUpdate();
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
        onSuccess: () => navigate('/admin/dashboard', { replace: true }),
        onError: (err: { message?: string }) => setError(err.message || '保存失败'),
      }
    );
  };

  return (
    <div className="auth-page bg-background" data-auth-word="Setup">
      <BigLogo />
      <Card className="auth-card w-full max-w-lg rounded-lg bg-white shadow-sm border">
        <CardHeader>
          <CardTitle>首次登录设置</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600">
                {error}
              </div>
            )}
            <Input
              type="password"
              placeholder="当前初始密码"
              value={currentPassword}
              onChange={event => setCurrentPassword(event.target.value)}
              disabled={updateProfile.isPending}
            />
            <Input
              placeholder="新的管理员用户名"
              value={username}
              onChange={event => setUsername(event.target.value)}
              disabled={updateProfile.isPending}
            />
            <Input
              type="password"
              placeholder="新的管理员密码，至少 8 位"
              value={newPassword}
              onChange={event => setNewPassword(event.target.value)}
              disabled={updateProfile.isPending}
            />
            <Button type="submit" className="w-full rounded-md" disabled={updateProfile.isPending}>
              保存并进入后台
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
