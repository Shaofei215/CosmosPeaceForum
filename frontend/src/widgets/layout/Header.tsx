/**
 * 头部导航组件
 */

import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore, useLogout } from '@/features/auth';
import { Button } from '@/shared/components/ui';

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
          Imaginary Tree
        </Link>

        {/* 导航链接 */}
        <nav className="flex items-center gap-4">
          <Link
            to="/feed"
            className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            信息流
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
                退出
              </Button>
            </>
          ) : (
            <>
              <Link to="/login">
                <Button variant="ghost" size="sm">
                  登录
                </Button>
              </Link>
              <Link to="/register">
                <Button size="sm">注册</Button>
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
