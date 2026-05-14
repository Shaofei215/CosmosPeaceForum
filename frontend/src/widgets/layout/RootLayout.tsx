import { useLayoutEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { LeftSidebar } from '@/widgets/left-sidebar';
import { RightSidebar } from '@/widgets/right-sidebar';
import { TopBar } from '@/widgets/top-bar';

const AUTH_PATHS = [
  '/login',
  '/management-login',
  '/register',
  '/profile-setup',
  '/forgot-password',
  '/reset-password',
];

export function RootLayout() {
  const location = useLocation();
  const pathname = location.pathname;

  useLayoutEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  }, [location.key]);

  const isAuthPage = AUTH_PATHS.some(path => pathname === path || pathname.startsWith(path + '/'));
  const showTopAndRight = !isAuthPage;
  const showLeft = !isAuthPage;

  return (
    <div className="min-h-screen bg-background/80">
      <main className="relative z-10 container mx-auto px-4 pb-3 pt-3">
        {showTopAndRight && (
          <div className="h-20">
            <div className="fixed left-1/2 top-3 z-40 w-[calc(100%-2rem)] max-w-2xl -translate-x-1/2">
              <TopBar />
            </div>
          </div>
        )}

        <div className="flex items-start justify-center gap-3">
          {showLeft && (
            <div className="hidden w-64 flex-shrink-0 lg:block">
              <LeftSidebar />
            </div>
          )}

          <div className="w-full max-w-2xl flex-shrink-0">
            <Outlet />
          </div>

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
