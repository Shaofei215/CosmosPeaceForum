/**
 * 登录页面
 * 支持邮箱+密码或邮箱+验证码登录
 */

import { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { AlertCircle } from 'lucide-react';
import { useLogin, useSendLoginCode } from '@/features/auth';
import { Button, Input, Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui';
import { AuthIllustration, BigLogo } from '@/shared/components/auth/BigLogo';

type LoginMethod = 'password' | 'code';

/**
 * 登录页面组件
 */
export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();

  // 登录方式状态
  const [loginMethod, setLoginMethod] = useState<LoginMethod>('password');

  // 表单状态
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [rememberMe, setRememberMe] = useState(false);

  // 验证码倒计时
  const [countdown, setCountdown] = useState(0);

  // Hooks
  const { mutate: login, isPending: isLoginPending } = useLogin();
  const { mutate: sendCode, isPending: isSendCodePending } = useSendLoginCode();

  const isPending = isLoginPending || isSendCodePending;

  // 获取登录后要跳转的路径和成功消息
  useEffect(() => {
    const state = location.state as { from?: { pathname?: string }; message?: string } | null;
    if (state?.message) {
      setSuccessMessage(state.message);
      window.history.replaceState({}, document.title);
    }
  }, [location.state]);

  // 验证码倒计时
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  const from = (location.state as { from?: { pathname?: string } })?.from?.pathname || '/';

  /**
   * 验证邮箱格式
   */
  const validateEmail = (email: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  /**
   * 处理发送验证码
   */
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
        onSuccess: data => {
          setCountdown(60);
          setSuccessMessage(`${data.message}，有效期10分钟`);
          setTimeout(() => setSuccessMessage(''), 5000);
        },
        onError: (err: { message?: string }) => {
          setError(err.message || '发送验证码失败，请稍后重试');
        },
      }
    );
  };

  /**
   * 处理登录提交
   */
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

    if (loginMethod === 'password') {
      if (!password.trim()) {
        setError('请输入密码');
        return;
      }

      if (password.length < 8) {
        setError('密码至少需要8位');
        return;
      }

      login(
        { email: email.trim(), password, remember_me: rememberMe },
        {
          onSuccess: () => {
            navigate(from, { replace: true });
          },
          onError: (err: { message?: string }) => {
            setError(err.message || '登录失败，请检查邮箱和密码');
          },
        }
      );
    } else {
      if (!code.trim()) {
        setError('请输入验证码');
        return;
      }

      if (code.length !== 6) {
        setError('验证码应为6位数字');
        return;
      }

      login(
        { email: email.trim(), code, remember_me: rememberMe },
        {
          onSuccess: () => {
            navigate(from, { replace: true });
          },
          onError: (err: { message?: string }) => {
            setError(err.message || '登录失败，请检查验证码');
          },
        }
      );
    }
  };

  return (
    <div className="auth-page" data-auth-word="Login">
      <AuthIllustration />
      <BigLogo />
      <Card className="auth-card w-full max-w-md rounded-lg bg-white shadow-sm border">
        <CardHeader className="auth-card-header space-y-1">
          <CardTitle className="auth-title text-2xl font-bold text-center">登录</CardTitle>
        </CardHeader>
        <CardContent className="auth-card-content">
          <form onSubmit={handleSubmit} className="auth-form space-y-4">
            {error && (
              <div className="auth-alert whitespace-pre-wrap break-words text-sm">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {successMessage && (
              <div className="auth-alert auth-success text-sm">
                <span>{successMessage}</span>
              </div>
            )}

            {/* 邮箱输入 */}
            <div className="auth-field space-y-2">
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

            {/* 登录方式切换 */}
            <div
              className="auth-segmented relative grid grid-cols-2 rounded-lg bg-zinc-100/80 p-1"
              data-active={loginMethod}
            >
              <span className="auth-segmented-slider absolute left-1 top-1 h-[calc(100%-0.5rem)] w-[calc(50%-0.25rem)] rounded-md bg-zinc-950 shadow-sm transition-transform duration-200 ease-out" />
              <button
                type="button"
                onClick={() => setLoginMethod('password')}
                className={`relative z-10 rounded-md py-2 text-sm font-medium transition-colors ${
                  loginMethod === 'password' ? 'text-white' : 'text-zinc-600 hover:text-foreground'
                }`}
              >
                密码登录
              </button>
              <button
                type="button"
                onClick={() => setLoginMethod('code')}
                className={`relative z-10 rounded-md py-2 text-sm font-medium transition-colors ${
                  loginMethod === 'code' ? 'text-white' : 'text-zinc-600 hover:text-foreground'
                }`}
              >
                验证码登录
              </button>
            </div>

            {/* 密码输入 */}
            {loginMethod === 'password' && (
              <div className="auth-field space-y-2">
                <label htmlFor="password" className="text-sm font-medium">
                  密码
                </label>
                <Input
                  id="password"
                  type="password"
                  placeholder="请输入密码"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  disabled={isPending}
                  minLength={8}
                  className="auth-input bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1"
                />
              </div>
            )}

            {/* 验证码输入 */}
            {loginMethod === 'code' && (
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
                    className="auth-input flex-1 bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1"
                    maxLength={6}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleSendCode}
                    disabled={isPending || countdown > 0 || !email.trim()}
                    className="auth-code-button whitespace-nowrap rounded-lg border-0 bg-zinc-950 text-white shadow-none hover:opacity-90"
                  >
                    {countdown > 0 ? `${countdown}秒后重发` : '获取验证码'}
                  </Button>
                </div>
              </div>
            )}

            <div className="flex items-center justify-between gap-3">
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={e => setRememberMe(e.target.checked)}
                  disabled={isPending}
                  className="h-4 w-4 rounded border-gray-300"
                />
                记住我
              </label>
              <Link to="/forgot-password" className="text-sm text-primary hover:underline">
                忘记密码？
              </Link>
            </div>

            {/* 登录按钮 */}
            <Button type="submit" className="auth-submit w-full rounded-lg" disabled={isPending}>
              {isLoginPending ? '登录中...' : '登录'}
            </Button>
          </form>

          {/* 注册链接 */}
          <div className="auth-footer mt-4 text-center text-sm">
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
