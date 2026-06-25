/**
 * 注册页面
 * 简化版注册流程：仅需邮箱、验证码、密码
 * 注册成功后跳转到资料完善页面设置用户名
 */

import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertCircle } from 'lucide-react';
import {
  useInvitationRegistrationConfig,
  useRegisterWithVerification,
  useSendVerificationCode,
} from '@/features/auth';
import { Button, Input, Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui';
import { BigLogo } from '@/shared/components/auth/BigLogo';

export default function RegisterPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [invitationCode, setInvitationCode] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState('');
  const [countdown, setCountdown] = useState(0);

  const { mutate: sendCode, isPending: isSendingCode } = useSendVerificationCode();
  const { mutate: register, isPending: isRegistering } = useRegisterWithVerification();
  const { data: invitationConfig } = useInvitationRegistrationConfig();

  const isPending = isSendingCode || isRegistering;
  const invitationRequired = !!invitationConfig?.enabled;

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
    if (invitationRequired && !invitationCode.trim()) {
      setError('请输入邀请码');
      return;
    }

    sendCode(
      {
        email: email.trim(),
        invitation_code: invitationRequired ? invitationCode.trim() : undefined,
      },
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
    if (invitationRequired && !invitationCode.trim()) {
      setError('请输入邀请码');
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
        invitation_code: invitationRequired ? invitationCode.trim() : undefined,
        remember_me: rememberMe,
      },
      {
        onSuccess: data => {
          navigate('/profile-setup', { state: { userId: data.id } });
        },
        onError: (err: { message?: string }) => {
          setError(err.message || '注册失败，请稍后重试');
        },
      }
    );
  };

  return (
    <div className="auth-page" data-auth-word="Register">
      <BigLogo />
      <Card className="auth-card auth-register-card rounded-lg bg-white shadow-sm border">
        <CardHeader className="auth-card-header space-y-1 pb-4">
          <CardTitle className="auth-title text-2xl font-bold text-center">注册</CardTitle>
        </CardHeader>
        <CardContent className="auth-card-content">
          <form
            onSubmit={handleSubmit}
            className="auth-form grid grid-cols-1 gap-3.5 md:grid-cols-2"
          >
            {error && (
              <div className="auth-alert text-sm md:col-span-2">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* 邮箱 */}
            <div className="auth-field space-y-2 md:col-span-2">
              <label htmlFor="email" className="text-sm font-medium">
                邮箱
              </label>
              <Input
                id="email"
                type="email"
                placeholder="请输入邮箱地址"
                value={email}
                onChange={e => setEmail(e.target.value)}
                disabled={isPending}
                className="auth-input bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1"
              />
            </div>

            {invitationRequired && (
              <div className="auth-field space-y-2">
                <label htmlFor="invitationCode" className="text-sm font-medium">
                  邀请码
                </label>
                <Input
                  id="invitationCode"
                  type="text"
                  placeholder="请输入邮箱对应的邀请码"
                  value={invitationCode}
                  onChange={e =>
                    setInvitationCode(
                      e.target.value
                        .replace(/[^A-Za-z0-9_-]/g, '')
                        .toUpperCase()
                        .slice(0, 64)
                    )
                  }
                  disabled={isPending}
                  maxLength={64}
                  className="auth-input bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1"
                />
              </div>
            )}

            {/* 验证码 */}
            <div className="auth-field space-y-2">
              <label htmlFor="code" className="text-sm font-medium">
                验证码
              </label>
              <div className="auth-code-row flex gap-2">
                <Input
                  id="code"
                  type="text"
                  placeholder="请输入6位验证码"
                  value={code}
                  onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  disabled={isPending}
                  maxLength={6}
                  className="auth-input bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1 flex-1"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleSendCode}
                  disabled={
                    isSendingCode ||
                    countdown > 0 ||
                    !email.trim() ||
                    (invitationRequired && !invitationCode.trim())
                  }
                  className="auth-code-button whitespace-nowrap rounded-lg border-0 bg-zinc-950 text-white shadow-none hover:opacity-90"
                >
                  {countdown > 0 ? `${countdown}秒后重试` : '获取验证码'}
                </Button>
              </div>
            </div>

            {/* 密码 */}
            <div className="auth-field space-y-2">
              <label htmlFor="password" className="text-sm font-medium">
                密码
              </label>
              <Input
                id="password"
                type="password"
                placeholder="请输入密码（至少6个字符）"
                value={password}
                onChange={e => setPassword(e.target.value)}
                disabled={isPending}
                className="auth-input bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1"
              />
            </div>

            {/* 确认密码 */}
            <div className="auth-field space-y-2">
              <label htmlFor="confirmPassword" className="text-sm font-medium">
                确认密码
              </label>
              <Input
                id="confirmPassword"
                type="password"
                placeholder="请再次输入密码"
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                disabled={isPending}
                className="auth-input bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1"
              />
            </div>

            <label className="flex items-center gap-2 text-sm text-muted-foreground md:col-span-2">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={e => setRememberMe(e.target.checked)}
                disabled={isPending}
                className="h-4 w-4 rounded border-gray-300"
              />
              记住我
            </label>

            <Button
              type="submit"
              className="auth-submit w-full rounded-lg md:col-span-2"
              disabled={isPending}
            >
              {isRegistering ? '注册中...' : '注册'}
            </Button>
          </form>
          <div className="auth-footer mt-3 text-center text-sm">
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
