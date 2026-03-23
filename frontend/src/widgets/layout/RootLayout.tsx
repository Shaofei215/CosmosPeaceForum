/**
 * 根布局组件
 * 提供应用的四块布局结构：左块、中间块、右块、顶块
 * 
 * 显示规则：
 * - 顶块和右块：除登录/注册页外的所有页面显示
 * - 左块：除登录/注册页和自己的个人主页外的页面显示
 */

import { Outlet, useLocation } from 'react-router-dom';
import { LeftSidebar } from '@/widgets/left-sidebar';
import { RightSidebar } from '@/widgets/right-sidebar';
import { TopBar } from '@/widgets/top-bar';
import { useAuthStore } from '@/features/auth';

/**
 * 根布局组件
 */
export function RootLayout() {
  const location = useLocation();
  const { user } = useAuthStore();
  const pathname = location.pathname;

  // 判断是否为登录/注册页
  const isAuthPage = pathname === '/login' || pathname === '/register';

  // 判断是否为自己的个人主页
  const isOwnProfilePage = user ? pathname === `/user/${user.id}` : false;

  // 显示规则
  const showTopAndRight = !isAuthPage; // 顶块和右块：除登录/注册页外都显示
  const showLeft = !isAuthPage && !isOwnProfilePage; // 左块：除登录/注册页和自己的主页外都显示

  return (
    <div className="min-h-screen bg-background/80">
      {/* 主内容区域 */}
      <main className="container mx-auto px-4 py-6 relative z-10">
        <div className="flex gap-6 justify-center">
          {/* 左块 */}
          {showLeft && (
            <div className="hidden lg:block flex-shrink-0">
              <LeftSidebar />
            </div>
          )}

          {/* 中间块 */}
          <div className="w-full max-w-2xl flex-shrink-0">
            {/* 顶块 */}
            {showTopAndRight && <TopBar />}

            {/* 页面内容 */}
            <Outlet />
          </div>

          {/* 右块 */}
          {showTopAndRight && (
            <div className="hidden lg:block flex-shrink-0">
              <RightSidebar />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
