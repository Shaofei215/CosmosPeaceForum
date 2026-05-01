/**
 * 注册页面
 * 简化版注册流程：仅需邮箱、验证码、密码
 * 注册成功后跳转到资料完善页面设置用户名
 */

import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useSendVerificationCode, useRegisterWithVerification } from '@/features/auth';
import { Button, Input, Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui';

export default function RegisterPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [countdown, setCountdown] = useState(0);

  const { mutate: sendCode, isPending: isSendingCode } = useSendVerificationCode();
  const { mutate: register, isPending: isRegistering } = useRegisterWithVerification();

  const isPending = isSendingCode || isRegistering;

  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  const validateEmail = (email: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  const handleSendCode = () => {
    setError('');

    if (!email.trim()) {
      setError('请输入邮箱地址');
      return;
    }
    if (!validateEmail(email)) {
      setError('请输入有效的邮箱地址');
      return;
    }

    sendCode(
      { email: email.trim() },
      {
        onSuccess: () => {
          setCountdown(60);
        },
        onError: (err: { message?: string }) => {
          setError(err.message || '发送验证码失败，请稍后重试');
        },
      }
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email.trim()) {
      setError('请输入邮箱地址');
      return;
    }
    if (!validateEmail(email)) {
      setError('请输入有效的邮箱地址');
      return;
    }

    if (!code.trim()) {
      setError('请输入验证码');
      return;
    }
    if (code.length !== 6) {
      setError('验证码为6位数字');
      return;
    }

    if (!password.trim()) {
      setError('请输入密码');
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

    register(
      {
        email: email.trim(),
        password,
        code: code.trim(),
      },
      {
        onSuccess: (data) => {
          navigate('/profile-setup', { state: { userId: data.id } });
        },
        onError: (err: { message?: string }) => {
          setError(err.message || '注册失败，请稍后重试');
        },
      }
    );
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <Card className="w-full max-w-md rounded-lg bg-white shadow-sm border">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold text-center">注册</CardTitle>
          <p className="text-sm text-muted-foreground text-center mt-2">
            注册后需完善个人资料
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 text-sm text-red-500 bg-red-50/80 backdrop-blur-sm rounded-lg">
                {error}
              </div>
            )}

            {/* 邮箱 */}
            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium">
                邮箱
              </label>
              <Input
                id="email"
                type="email"
                placeholder="请输入邮箱地址"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isPending}
                className="bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1"
              />
            </div>

            {/* 验证码 */}
            <div className="space-y-2">
              <label htmlFor="code" className="text-sm font-medium">
                验证码
              </label>
              <div className="flex gap-2">
                <Input
                  id="code"
                  type="text"
                  placeholder="请输入6位验证码"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  disabled={isPending}
                  maxLength={6}
                  className="bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1 flex-1"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleSendCode}
                  disabled={isSendingCode || countdown > 0 || !email.trim()}
                  className="whitespace-nowrap rounded-lg shadow-none"
                >
                  {countdown > 0 ? `${countdown}秒后重试` : '获取验证码'}
                </Button>
              </div>
            </div>

            {/* 密码 */}
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium">
                密码
              </label>
              <Input
                id="password"
                type="password"
                placeholder="请输入密码（至少6个字符）"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isPending}
                className="bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1"
              />
            </div>

            {/* 确认密码 */}
            <div className="space-y-2">
              <label htmlFor="confirmPassword" className="text-sm font-medium">
                确认密码
              </label>
              <Input
                id="confirmPassword"
                type="password"
                placeholder="请再次输入密码"
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
              {isRegistering ? '注册中...' : '注册'}
            </Button>
          </form>
          <div className="mt-4 text-center text-sm">
            已有账号？{' '}
            <Link to="/login" className="text-primary hover:underline">
              立即登录
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
