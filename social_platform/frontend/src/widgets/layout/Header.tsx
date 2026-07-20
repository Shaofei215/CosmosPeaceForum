/**
 * 头部导航组件
 */

import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore, useLogout } from '@/features/auth';
import { Button } from '@/shared/components/ui';
import { PLATFORM_DISPLAY_NAME } from '@/shared/config/branding';
import { copywriting } from '@/shared/config/copywriting';

/**
 * 头部导航组件
 */
export function Header() {
  const { isAuthenticated, user } = useAuthStore();
  const logout = useLogout();
  const navigate = useNavigate();

  /**
   * 处理登出
   */
  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto px-4 h-14 flex items-center justify-between max-w-3xl">
        {/* Logo */}
        <Link to="/" className="font-bold text-xl">
          {PLATFORM_DISPLAY_NAME}
        </Link>

        {/* 导航链接 */}
        <nav className="flex items-center gap-4">
          <Link
            to="/feed"
            className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            {copywriting('navigation.home', '主页')}
          </Link>

          {isAuthenticated ? (
            <>
              <Link
                to={`/user/${user?.id}`}
                className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              >
                {user?.username}
              </Link>
              <Button variant="ghost" size="sm" onClick={handleLogout}>
                {copywriting('common.logout', '登出')}
              </Button>
            </>
          ) : (
            <>
              <Link to="/login">
                <Button variant="ghost" size="sm">
                  {copywriting('common.login', '登录')}
                </Button>
              </Link>
              <Link to="/register">
                <Button size="sm">{copywriting('common.register', '注册')}</Button>
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
