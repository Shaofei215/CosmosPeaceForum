import { useLayoutEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { LeftSidebar } from '@/widgets/left-sidebar';
import { RightSidebar } from '@/widgets/right-sidebar';
import { TopBar } from '@/widgets/top-bar';
import { cn } from '@/shared/lib/utils';
import { MobileBottomBar } from './MobileBottomBar';

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
  const isMobileDevice = isMobileUserAgent();

  useLayoutEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  }, [location.key]);

  const isAuthPage = AUTH_PATHS.some(path => pathname === path || pathname.startsWith(path + '/'));
  const showTopAndRight = !isAuthPage;
  const showLeft = !isAuthPage;

  return (
    <div
      className={cn('min-h-screen bg-background/80', isMobileDevice && 'mobile-device')}
      data-mobile-device={isMobileDevice ? 'true' : undefined}
    >
      <main
        className={cn(
          'relative z-10 container mx-auto px-2 pt-2 sm:px-4 sm:pt-3',
          showTopAndRight ? 'pb-24 lg:pb-3' : 'pb-2 sm:pb-3'
        )}
      >
        {showTopAndRight && (
          <div className="mobile-top-spacer h-[4.25rem] sm:h-20">
            <div className="fixed left-1/2 top-2 z-40 w-[calc(100%-1rem)] max-w-2xl -translate-x-1/2 sm:top-3 sm:w-[calc(100%-2rem)]">
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
      {showTopAndRight && <MobileBottomBar />}
    </div>
  );
}

function isMobileUserAgent() {
  if (typeof navigator === 'undefined') return false;

  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|Tablet/i.test(
    navigator.userAgent
  );
}
