/**
 * 资料完善页面
 * 用户注册后设置用户名、签名和头像
 */

import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useCompleteProfile, useUploadAvatar, useDeleteAvatar } from '@/features/user';
import { useAuthStore } from '@/features/auth';
import { AvatarUpload } from '@/shared/components/avatar-upload';
import { Button, Input, Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui';

function extractErrorMessage(err: unknown): string | null {
  if (typeof err === 'object' && err !== null) {
    const e = err as Record<string, unknown>;
    if (typeof e.message === 'string') {
      return e.message;
    }
    if (Array.isArray(e.message)) {
      return (e.message as Array<Record<string, unknown>>)
        .map((item) => (typeof item.msg === 'string' ? item.msg : JSON.stringify(item)))
        .join(', ');
    }
  }
  if (err instanceof Error) {
    return err.message;
  }
  return null;
}

export default function ProfileSetupPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuthStore();

  const [username, setUsername] = useState('');
  const [bio, setBio] = useState('');
  const [error, setError] = useState('');
  const [avatarError, setAvatarError] = useState('');

  const { mutate: completeProfile, isPending: isCompleting } = useCompleteProfile();
  const { mutate: uploadAvatar, isPending: isUploading } = useUploadAvatar();
  const { mutate: deleteAvatar } = useDeleteAvatar();

  const isPending = isCompleting || isUploading;

  useEffect(() => {
    if (!location.state?.userId && !user?.id) {
      navigate('/register');
    }
  }, [location.state, user, navigate]);

  const handleAvatarUpload = (file: File) => {
    setAvatarError('');
    uploadAvatar(file, {
      onError: (err: unknown) => {
        setAvatarError(extractErrorMessage(err) || '头像上传失败');
      },
    });
  };

  const handleAvatarDelete = () => {
    deleteAvatar(undefined, {
      onError: (err: unknown) => {
        const message = extractErrorMessage(err);
        setAvatarError(message || '头像删除失败');
      },
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!username.trim()) {
      setError('请输入用户名');
      return;
    }

    if (username.length < 3) {
      setError('用户名至少需要3个字符');
      return;
    }

    if (username.length > 30) {
      setError('用户名最多30个字符');
      return;
    }

    if (bio.length > 20) {
      setError('签名最多20个字符');
      return;
    }

    if (!/^[a-zA-Z0-9_\u4e00-\u9fa5]+$/.test(username)) {
      setError('用户名只能包含字母、数字、下划线和中文');
      return;
    }

    const userId = location.state?.userId || user?.id;

    completeProfile(
      { userId, data: { username: username.trim(), bio: bio.trim() || undefined } },
      {
        onSuccess: () => {
          navigate('/feed');
        },
        onError: (err: unknown) => {
          setError(extractErrorMessage(err) || '保存失败，请稍后重试');
        },
      }
    );
  };

  return (
    <div className="auth-page min-h-screen flex items-center justify-center p-4">
      <Card className="auth-card w-full max-w-md rounded-lg bg-white shadow-sm border">
        <CardHeader className="auth-card-header space-y-1">
          <CardTitle className="auth-title text-2xl font-bold text-center">完善个人资料</CardTitle>
        </CardHeader>
        <CardContent className="auth-card-content">
          <form onSubmit={handleSubmit} className="auth-form space-y-6">
            {error && (
              <div className="auth-alert p-3 text-sm text-red-500 bg-red-50/80 backdrop-blur-sm rounded-lg">
                {error}
              </div>
            )}

            <div className="flex justify-center">
              <AvatarUpload
                avatarUrl={user?.avatar_url}
                username={username}
                size="2xl"
                isUploading={isUploading}
                onUpload={handleAvatarUpload}
                onDelete={handleAvatarDelete}
                error={avatarError}
              />
            </div>

            <div className="auth-field space-y-2">
              <div className="flex items-center justify-between">
                <label htmlFor="username" className="text-sm font-medium">
                  用户名 <span className="text-destructive">*</span>
                </label>
                <span className="text-xs text-muted-foreground">
                  {username.length}/30
                </span>
              </div>
              <Input
                id="username"
                type="text"
                placeholder="用户名设置后暂不可更改，请仔细思考哦~"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={isPending}
                className="auth-input bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1"
                maxLength={30}
              />
            </div>

            <div className="auth-field space-y-2">
              <div className="flex items-center justify-between">
                <label htmlFor="bio" className="text-sm font-medium">
                  个人签名
                </label>
                <span className="text-xs text-muted-foreground">
                  {bio.length}/20
                </span>
              </div>
              <Input
                id="bio"
                type="text"
                placeholder="签名也暂不可更改，三思而后行哦~"
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                disabled={isPending}
                className="auth-input bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1"
                maxLength={20}
              />
            </div>

            <Button
              type="submit"
              className="auth-submit w-full rounded-lg"
              disabled={isPending}
            >
              {isCompleting ? '保存中...' : '完成设置'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
