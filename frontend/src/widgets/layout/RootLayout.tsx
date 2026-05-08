/**
 * 根布局组件
 * 提供应用的四块布局结构：左块、中间块、右块、顶块
 *
 * 显示规则：
 * - 顶块和右块：除登录/注册页外的所有页面显示
 * - 左块：除登录/注册页外的所有页面显示
 */

import { Outlet, useLocation } from 'react-router-dom';
import { LeftSidebar } from '@/widgets/left-sidebar';
import { RightSidebar } from '@/widgets/right-sidebar';
import { TopBar } from '@/widgets/top-bar';

/**
 * 认证页面路径列表
 */
const AUTH_PATHS = [
  '/login',
  '/register',
  '/profile-setup',
  '/forgot-password',
  '/reset-password',
];

/**
 * 根布局组件
 */
export function RootLayout() {
  const location = useLocation();
  const pathname = location.pathname;

  // 判断是否为登录/注册页（支持子路径如 /login/email）
  const isAuthPage = AUTH_PATHS.some(path =>
    pathname === path || pathname.startsWith(path + '/')
  );

  // 显示规则
  const showTopAndRight = !isAuthPage; // 顶块和右块：除登录/注册页外都显示
  const showLeft = !isAuthPage; // 左块：除登录/注册页外都显示

  return (
    <div className="min-h-screen bg-background/80">
      {/* 主内容区域 */}
      <main className="container mx-auto px-4 pt-3 pb-3 relative z-10">
        {/* 顶块 - 固定在视口顶部，保留占位避免内容被遮挡 */}
        {showTopAndRight && (
          <div className="h-20">
            <div className="fixed left-1/2 top-3 z-40 w-[calc(100%-2rem)] max-w-2xl -translate-x-1/2">
              <TopBar />
            </div>
          </div>
        )}

        <div className="flex gap-3 justify-center items-start">
          {/* 左块 */}
          {showLeft && (
            <div className="hidden w-64 flex-shrink-0 lg:block">
              <LeftSidebar />
            </div>
          )}

          {/* 中间块 */}
          <div className="w-full max-w-2xl flex-shrink-0">
            {/* 页面内容 */}
            <Outlet />
          </div>

          {/* 右块 */}
          {showTopAndRight && (
            <div className="hidden w-64 flex-shrink-0 lg:block">
              <RightSidebar />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
