import { useEffect, useLayoutEffect, useRef } from 'react';
import { Outlet, useLocation, useNavigationType } from 'react-router-dom';
import { LeftSidebar, SidebarFooter } from '@/widgets/left-sidebar';
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

const scrollPositions = new Map<string, { x: number; y: number }>();

export function RootLayout() {
  const location = useLocation();
  const navigationType = useNavigationType();
  const previousLocationKeyRef = useRef(location.key);
  const pathname = location.pathname;
  const isMobileDevice = isMobileUserAgent();

  useEffect(() => {
    if (!('scrollRestoration' in window.history)) {
      return undefined;
    }

    const previousScrollRestoration = window.history.scrollRestoration;
    window.history.scrollRestoration = 'manual';

    return () => {
      window.history.scrollRestoration = previousScrollRestoration;
    };
  }, []);

  useLayoutEffect(() => {
    scrollPositions.set(previousLocationKeyRef.current, {
      x: window.scrollX,
      y: window.scrollY,
    });

    const scrollPosition = scrollPositions.get(location.key);

    if (navigationType === 'POP' && scrollPosition) {
      window.scrollTo({ top: scrollPosition.y, left: scrollPosition.x, behavior: 'auto' });
    } else if (navigationType !== 'POP') {
      window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
    }

    previousLocationKeyRef.current = location.key;
  }, [location.key, navigationType]);

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
          isAuthPage && 'mobile-auth-main min-h-screen max-w-none p-0 sm:p-0',
          showTopAndRight ? 'pb-24 lg:pb-3' : !isAuthPage && 'pb-2 sm:pb-3'
        )}
      >
        {showTopAndRight && (
          <div className="mobile-top-spacer h-[4.25rem] sm:h-[5.25rem]">
            <div className="fixed left-1/2 top-2 z-40 w-[calc(100%-1rem)] max-w-2xl -translate-x-1/2 sm:top-3 sm:w-[calc(100%-2rem)]">
              <TopBar />
            </div>
          </div>
        )}

        <div className={cn('flex items-start justify-center gap-3', isAuthPage && 'min-h-screen')}>
          {showLeft && (
            <div className="hidden w-64 flex-shrink-0 lg:block">
              <LeftSidebar />
            </div>
          )}

          <div className={cn('w-full flex-shrink-0', isAuthPage ? 'max-w-none' : 'max-w-2xl')}>
            <Outlet />
            {!isAuthPage && (
              <div className="mx-2 mt-6 border-t border-border/60 px-2 py-6 lg:hidden">
                <SidebarFooter />
              </div>
            )}
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
