/**
 * 注册页面
 * 简化版注册流程：仅需邮箱、验证码、密码
 * 注册成功后跳转到资料完善页面设置用户名
 */

import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowRight } from 'lucide-react';
import {
  useInvitationRegistrationConfig,
  useRegisterWithVerification,
  useSendVerificationCode,
} from '@/features/auth';
import { Button, Input, Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui';
import { AuthIllustration, BigLogo } from '@/shared/components/auth/BigLogo';
import { cn } from '@/shared/lib/utils';
import { copywriting } from '@/shared/config/copywriting';

export default function RegisterPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [invitationCode, setInvitationCode] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [acceptedTerms, setAcceptedTerms] = useState(false);
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
      setError(copywriting('auth.email_required', '请输入邮箱地址'));
      return;
    }
    if (!validateEmail(email)) {
      setError(copywriting('auth.email_invalid', '请输入有效的邮箱地址'));
      return;
    }
    if (invitationRequired && !invitationCode.trim()) {
      setError(copywriting('auth.invitation_required', '请输入邀请码'));
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
          setError(
            err.message || copywriting('auth.send_code_failed', '发送验证码失败，请稍后重试')
          );
        },
      }
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email.trim()) {
      setError(copywriting('auth.email_required', '请输入邮箱地址'));
      return;
    }
    if (!validateEmail(email)) {
      setError(copywriting('auth.email_invalid', '请输入有效的邮箱地址'));
      return;
    }
    if (invitationRequired && !invitationCode.trim()) {
      setError(copywriting('auth.invitation_required', '请输入邀请码'));
      return;
    }

    if (!code.trim()) {
      setError(copywriting('auth.verification_code_required', '请输入验证码'));
      return;
    }
    if (code.length !== 6) {
      setError(copywriting('auth.verification_code_invalid', '验证码为6位数字'));
      return;
    }

    if (!password.trim()) {
      setError(copywriting('auth.password_required', '请输入密码'));
      return;
    }
    if (password.length < 8) {
      setError(copywriting('auth.password_too_short', '密码至少需要8个字符'));
      return;
    }

    if (password !== confirmPassword) {
      setError(copywriting('auth.password_mismatch', '两次输入的密码不一致'));
      return;
    }
    if (!acceptedTerms) {
      setError(
        copywriting('auth.accept_agreements_required', '请先阅读并同意服务条款、隐私条约与社区规范')
      );
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
          setError(err.message || copywriting('auth.register_failed', '注册失败，请稍后重试'));
        },
      }
    );
  };

  return (
    <div className="auth-page" data-auth-word="Register">
      <AuthIllustration />
      <BigLogo />
      <Card
        className={cn(
          'auth-card rounded-lg border bg-white shadow-sm',
          invitationRequired && 'auth-register-card'
        )}
      >
        <CardHeader className="auth-card-header space-y-1 pb-4">
          <CardTitle className="auth-title text-2xl font-bold text-center">
            {copywriting('auth.register_title', '注册')}
          </CardTitle>
        </CardHeader>
        <CardContent className="auth-card-content">
          <form
            onSubmit={handleSubmit}
            className={cn(
              'auth-form grid gap-3.5',
              invitationRequired ? 'grid-cols-2' : 'grid-cols-1'
            )}
          >
            {error && (
              <div className={cn('auth-alert text-sm', invitationRequired && 'col-span-2')}>
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* 邮箱 */}
            <div className={cn('auth-field space-y-2', invitationRequired && 'col-span-2')}>
              <label htmlFor="email" className="text-sm font-medium">
                {copywriting('auth.email', '邮箱')}
              </label>
              <Input
                id="email"
                type="email"
                placeholder={copywriting('auth.email_placeholder', '请输入邮箱地址')}
                value={email}
                onChange={e => setEmail(e.target.value)}
                disabled={isPending}
                className="auth-input bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1"
              />
            </div>

            {invitationRequired && (
              <div className="auth-field space-y-2">
                <label htmlFor="invitationCode" className="text-sm font-medium">
                  {copywriting('auth.invitation_code', '邀请码')}
                </label>
                <Input
                  id="invitationCode"
                  type="text"
                  placeholder={copywriting('auth.invitation_placeholder', '请输入邮箱对应的邀请码')}
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
                {copywriting('auth.verification_code', '验证码')}
              </label>
              <div className="auth-code-row flex gap-2">
                <Input
                  id="code"
                  type="text"
                  placeholder={copywriting('auth.verification_code_placeholder', '请输入6位验证码')}
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
                  aria-label={
                    countdown > 0
                      ? copywriting('auth.resend_available_after', '{seconds}秒后可重新发送', {
                          seconds: countdown,
                        })
                      : copywriting('auth.get_verification_code', '获取验证码')
                  }
                  title={
                    countdown > 0
                      ? copywriting('auth.resend_available_after', '{seconds}秒后可重新发送', {
                          seconds: countdown,
                        })
                      : copywriting('auth.get_verification_code', '获取验证码')
                  }
                  disabled={
                    isSendingCode ||
                    countdown > 0 ||
                    !email.trim() ||
                    (invitationRequired && !invitationCode.trim())
                  }
                  className="auth-code-button whitespace-nowrap rounded-lg border-0 bg-zinc-950 text-white shadow-none hover:opacity-90"
                >
                  <span className="auth-code-button-label">
                    {countdown > 0
                      ? copywriting('auth.resend_after', '{seconds}秒后重试', {
                          seconds: countdown,
                        })
                      : copywriting('auth.get_verification_code', '获取验证码')}
                  </span>
                  <span className="auth-code-button-compact hidden items-center justify-center">
                    {countdown > 0 ? (
                      countdown
                    ) : (
                      <ArrowRight className="h-4 w-4" aria-hidden="true" />
                    )}
                  </span>
                </Button>
              </div>
            </div>

            {/* 密码 */}
            <div className="auth-field space-y-2">
              <label htmlFor="password" className="text-sm font-medium">
                {copywriting('auth.password', '密码')}
              </label>
              <Input
                id="password"
                type="password"
                placeholder={copywriting(
                  'auth.password_min_length_placeholder',
                  '请输入密码（至少8个字符）'
                )}
                value={password}
                onChange={e => setPassword(e.target.value)}
                disabled={isPending}
                minLength={8}
                maxLength={32}
                className="auth-input bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1"
              />
            </div>

            {/* 确认密码 */}
            <div className="auth-field space-y-2">
              <label htmlFor="confirmPassword" className="text-sm font-medium">
                {copywriting('auth.confirm_password', '确认密码')}
              </label>
              <Input
                id="confirmPassword"
                type="password"
                placeholder={copywriting('auth.confirm_password_placeholder', '请再次输入密码')}
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                disabled={isPending}
                minLength={8}
                maxLength={32}
                className="auth-input bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1"
              />
            </div>

            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={e => setRememberMe(e.target.checked)}
                disabled={isPending}
                className="h-4 w-4 rounded border-gray-300"
              />
              {copywriting('auth.remember_me', '记住我')}
            </label>

            <label className="flex items-start gap-2 text-sm leading-5 text-muted-foreground">
              <input
                type="checkbox"
                checked={acceptedTerms}
                onChange={e => setAcceptedTerms(e.target.checked)}
                disabled={isPending}
                className="mt-0.5 h-4 w-4 rounded border-gray-300"
              />
              <span>
                {copywriting('auth.accept', '同意')}{' '}
                <Link to="/legal/terms-of-service" className="text-primary hover:underline">
                  {copywriting('auth.terms', '服务条款')}
                </Link>
                、
                <Link to="/legal/privacy-policy" className="text-primary hover:underline">
                  {copywriting('auth.privacy', '隐私条约')}
                </Link>
                、
                <Link to="/legal/community-guidelines" className="text-primary hover:underline">
                  {copywriting('auth.guidelines', '社区规范')}
                </Link>
              </span>
            </label>

            <Button
              type="submit"
              className={cn('auth-submit w-full rounded-lg', invitationRequired && 'col-span-2')}
              disabled={isPending}
            >
              {isRegistering
                ? copywriting('auth.registering', '注册中...')
                : copywriting('common.register', '注册')}
            </Button>
          </form>
          <div className="auth-footer mt-3 text-center text-sm">
            {copywriting('auth.existing_account', '已有账号？')}{' '}
            <Link to="/login" className="text-primary hover:underline">
              {copywriting('auth.login_now', '立即登录')}
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
