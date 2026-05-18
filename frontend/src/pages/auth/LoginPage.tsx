/**
 * 登录页面
 * 支持邮箱+密码或邮箱+验证码登录
 */

import { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useLogin, useSendLoginCode } from '@/features/auth';
import { Button, Input, Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui';

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
        onSuccess: (data) => {
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

      login(
        { email: email.trim(), password },
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
        { email: email.trim(), code },
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
    <div className="auth-page min-h-screen flex items-center justify-center p-4">
      <Card className="auth-card w-full max-w-md rounded-lg bg-white shadow-sm border">
        <CardHeader className="auth-card-header space-y-1">
          <CardTitle className="auth-title text-2xl font-bold text-center">登录</CardTitle>
        </CardHeader>
        <CardContent className="auth-card-content">
          <form onSubmit={handleSubmit} className="auth-form space-y-4">
            {/* 错误提示 */}
            {error && (
              <div className="auth-alert whitespace-pre-wrap break-words p-3 text-sm text-red-500 bg-red-50/80 backdrop-blur-sm rounded-lg">
                {error}
              </div>
            )}

            {/* 成功提示 */}
            {successMessage && (
              <div className="auth-alert p-3 text-sm text-green-600 bg-green-50/80 backdrop-blur-sm rounded-lg">
                {successMessage}
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
                onChange={(e) => setEmail(e.target.value)}
                disabled={isPending}
                className="auth-input bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1"
              />
            </div>

            {/* 登录方式切换 */}
            <div className="auth-segmented flex gap-2 p-1 bg-muted/50 rounded-lg">
              <button
                type="button"
                onClick={() => setLoginMethod('password')}
                className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
                  loginMethod === 'password'
                    ? 'bg-primary text-primary-foreground'
                    : 'text-foreground/70 hover:text-foreground'
                }`}
              >
                密码登录
              </button>
              <button
                type="button"
                onClick={() => setLoginMethod('code')}
                className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
                  loginMethod === 'code'
                    ? 'bg-primary text-primary-foreground'
                    : 'text-foreground/70 hover:text-foreground'
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
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isPending}
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
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    disabled={isPending}
                    className="auth-input flex-1 bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1"
                    maxLength={6}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleSendCode}
                    disabled={isPending || countdown > 0 || !email.trim()}
                    className="auth-code-button whitespace-nowrap"
                  >
                    {countdown > 0 ? `${countdown}秒后重发` : '获取验证码'}
                  </Button>
                </div>
              </div>
            )}

            {/* 忘记密码链接 */}
            <div className="flex justify-end">
              <Link
                to="/forgot-password"
                className="text-sm text-primary hover:underline"
              >
                忘记密码？
              </Link>
            </div>

            {/* 登录按钮 */}
            <Button
              type="submit"
              className="auth-submit w-full rounded-lg"
              disabled={isPending}
            >
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
