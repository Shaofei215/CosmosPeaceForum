/**
 * 忘记密码页面
 * 用户输入邮箱、获取验证码、填写验证码，所有功能在一个表单内完成
 */

import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useSendPasswordResetCode } from '@/features/auth';
import { Button, Input, Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui';

/**
 * 忘记密码页面组件
 * 包含邮箱输入、验证码发送、验证码输入，全部在一个表单中
 */
export default function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [countdown, setCountdown] = useState(0);

  const { mutate: sendResetCode, isPending: isSending } = useSendPasswordResetCode();

  // 倒计时逻辑
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  /**
   * 处理发送验证码
   */
  const handleSendCode = () => {
    setError('');
    setSuccessMessage('');

    // 邮箱格式验证
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email.trim()) {
      setError('请输入邮箱地址');
      return;
    }
    if (!emailRegex.test(email)) {
      setError('请输入有效的邮箱地址');
      return;
    }

    sendResetCode(
      { email: email.trim() },
      {
        onSuccess: () => {
          setCountdown(60);
          setSuccessMessage('验证码已发送至您的邮箱，有效期10分钟');
          setTimeout(() => setSuccessMessage(''), 5000);
        },
        onError: (err: { message?: string }) => {
          setError(err.message || '发送验证码失败，请稍后重试');
        },
      }
    );
  };

  /**
   * 处理表单提交（验证验证码并跳转）
   */
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // 邮箱验证
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email.trim()) {
      setError('请输入邮箱地址');
      return;
    }
    if (!emailRegex.test(email)) {
      setError('请输入有效的邮箱地址');
      return;
    }

    // 验证码验证
    if (!code.trim()) {
      setError('请输入验证码');
      return;
    }
    if (code.length !== 6) {
      setError('验证码为6位数字');
      return;
    }

    // 验证通过，跳转到设置新密码页面
    navigate('/reset-password', { state: { email: email.trim(), code: code.trim() } });
  };

  return (
    <div className="auth-page min-h-screen flex items-center justify-center p-4">
      <div className="auth-mobile-hero">
        <p className="auth-mobile-brand">Imaginary Tree</p>
        <h1>找回密码</h1>
        <p>先验证邮箱，再设置一个新的密码。</p>
      </div>
      <Card className="auth-card w-full max-w-md rounded-lg bg-white shadow-sm border">
        <CardHeader className="auth-card-header space-y-1">
          <CardTitle className="auth-title text-2xl font-bold text-center">忘记密码</CardTitle>
        </CardHeader>
        <CardContent className="auth-card-content">
          <form onSubmit={handleSubmit} className="auth-form space-y-4">
            {error && (
              <div className="auth-alert p-3 text-sm text-red-500 bg-red-50/80 backdrop-blur-sm rounded-lg">
                {error}
              </div>
            )}
            {successMessage && (
              <div className="auth-alert p-3 text-sm text-green-600 bg-green-50/80 backdrop-blur-sm rounded-lg">
                {successMessage}
              </div>
            )}

            {/* 邮箱 */}
            <div className="auth-field space-y-2">
              <label htmlFor="email" className="text-sm font-medium">
                注册邮箱
              </label>
              <Input
                id="email"
                type="email"
                placeholder="请输入注册时使用的邮箱地址"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isSending}
                className="auth-input bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1"
              />
            </div>

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
                  onChange={(e) => setCode(e.target.value)}
                  maxLength={6}
                  className="auth-input bg-muted/50 border-0 shadow-none rounded-lg focus-visible:ring-1 flex-1"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleSendCode}
                  disabled={countdown > 0 || isSending || !email.trim()}
                  className="auth-code-button whitespace-nowrap rounded-lg shadow-none"
                >
                  {countdown > 0 ? `${countdown}秒后重试` : isSending ? '发送中...' : '获取验证码'}
                </Button>
              </div>
            </div>

            {/* 提交按钮 */}
            <Button
              type="submit"
              className="auth-submit w-full rounded-lg"
              disabled={!email.trim() || !code.trim()}
            >
              继续
            </Button>

            <div className="auth-footer mt-4 text-center text-sm">
              <Link
                to="/login"
                className="text-muted-foreground hover:text-primary transition-colors"
              >
                返回登录
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
