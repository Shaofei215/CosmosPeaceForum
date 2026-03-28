/**
 * 重置密码页面 - Step 2
 * 用户输入新密码并确认重置
 */

import { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useConfirmPasswordReset } from '@/features/auth';
import { Button, Input, Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui';

/**
 * 重置密码页面组件 - Step 2
 * 输入新密码并提交
 */
export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');

  const { mutate: resetPassword, isPending } = useConfirmPasswordReset();

  // 从上一个页面获取邮箱和验证码
  useEffect(() => {
    const state = location.state as { email?: string; code?: string } | null;
    if (state?.email && state?.code) {
      setEmail(state.email);
      setCode(state.code);
    } else {
      // 如果没有邮箱或验证码，返回忘记密码页
      navigate('/forgot-password');
    }
  }, [location.state, navigate]);

  /**
   * 处理密码重置提交
   */
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // 密码验证
    if (!password.trim()) {
      setError('请输入新密码');
      return;
    }
    if (password.length < 6) {
      setError('密码至少需要6个字符');
      return;
    }

    if (password !== confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }

    resetPassword(
      {
        email,
        code,
        new_password: password,
      },
      {
        onSuccess: () => {
          // 密码重置成功，跳转到登录页
          navigate('/login', {
            state: { message: '密码重置成功，请使用新密码登录' }
          });
        },
        onError: (err: { message?: string }) => {
          setError(err.message || '密码重置失败，请稍后重试');
        },
      }
    );
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative z-10">
      <Card className="w-full max-w-md rounded-xl bg-card/40 backdrop-blur-md supports-[backdrop-filter]:bg-card/30 border-0 shadow-none">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold text-center">设置新密码</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 text-sm text-red-500 bg-red-50/80 backdrop-blur-sm rounded-lg">
                {error}
              </div>
            )}

            {/* 邮箱显示（只读） */}
            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium">
                邮箱
              </label>
              <Input
                id="email"
                type="email"
                value={email}
                disabled
                className="bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1"
              />
            </div>

            {/* 新密码 */}
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium">
                新密码
              </label>
              <Input
                id="password"
                type="password"
                placeholder="请输入新密码（至少6个字符）"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isPending}
                className="bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1"
              />
            </div>

            {/* 确认新密码 */}
            <div className="space-y-2">
              <label htmlFor="confirmPassword" className="text-sm font-medium">
                确认密码
              </label>
              <Input
                id="confirmPassword"
                type="password"
                placeholder="请再次输入新密码"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={isPending}
                className="bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1"
              />
            </div>

            <Button
              type="submit"
              className="w-full rounded-lg"
              disabled={isPending}
            >
              {isPending ? '重置中...' : '确认重置'}
            </Button>

            <div className="mt-4 text-center text-sm">
              <Link
                to="/forgot-password"
                className="text-muted-foreground hover:text-primary transition-colors"
              >
                返回上一步
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
