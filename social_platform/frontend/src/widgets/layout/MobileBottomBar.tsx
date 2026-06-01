import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Bell, Flame, Home, PlusCircle, UserRound, X } from 'lucide-react';
import { useAuthStore } from '@/features/auth';
import { useNotificationUnreadCount } from '@/features/notification';
import { CreatePostForm } from '@/widgets/create-post-form';
import { cn } from '@/shared/lib/utils';

export function MobileBottomBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuthStore();
  const { data: unreadData } = useNotificationUnreadCount(isAuthenticated);
  const [isComposerOpen, setIsComposerOpen] = useState(false);

  const unreadCount = unreadData?.unread_count ?? 0;
  const profilePath = isAuthenticated && user ? `/user/${user.id}` : '/login';
  const notificationPath = isAuthenticated ? '/notifications' : '/login';

  useEffect(() => {
    setIsComposerOpen(false);
  }, [location.pathname]);

  const openComposer = () => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }

    setIsComposerOpen(value => !value);
  };

  return (
    <div className="lg:hidden">
      {isComposerOpen && (
        <>
          <button
            type="button"
            aria-label="关闭发布面板"
            className="fixed inset-0 z-40 bg-black/10"
            onClick={() => setIsComposerOpen(false)}
          />
          <div className="mobile-composer-panel fixed inset-x-2 bottom-[5.25rem] z-50 rounded-2xl bg-white p-3 shadow-lg">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-medium text-foreground">发布动态</span>
              <button
                type="button"
                aria-label="关闭发布面板"
                className="flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                onClick={() => setIsComposerOpen(false)}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <CreatePostForm />
          </div>
        </>
      )}

      <nav className="mobile-bottom-nav fixed inset-x-2 bottom-2 z-50 rounded-[2rem] border border-white/40 bg-white/45 px-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))] pt-2 shadow-md backdrop-blur-xl supports-[backdrop-filter]:bg-white/35">
        <div className="grid grid-cols-5 items-center gap-1">
          <MobileNavLink
            to="/feed"
            label="主页"
            active={location.pathname === '/feed' || location.pathname === '/'}
          >
            <Home className="h-5 w-5" />
          </MobileNavLink>
          <MobileNavLink to="/hot" label="热榜" active={location.pathname === '/hot'}>
            <Flame className="h-5 w-5" />
          </MobileNavLink>
          <MobileNavLink
            to={notificationPath}
            label="消息"
            active={location.pathname === '/notifications'}
          >
            <span className="relative">
              <Bell className="h-5 w-5" />
              {unreadCount > 0 && (
                <span className="absolute -right-2 -top-2 min-w-4 rounded-full bg-red-500 px-1 text-center text-[10px] font-semibold leading-4 text-white">
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              )}
            </span>
          </MobileNavLink>
          <button
            type="button"
            className={cn(
              'flex min-w-0 flex-col items-center gap-1 rounded-2xl px-2 py-1.5 text-xs font-medium',
              'text-muted-foreground transition-colors hover:bg-muted/70 hover:text-foreground',
              isComposerOpen &&
                'bg-[var(--theme-accent-bg)] text-[var(--theme-accent-fg)] hover:opacity-90'
            )}
            onClick={openComposer}
          >
            <PlusCircle className="h-5 w-5" />
            <span className="mobile-bottom-label truncate">发布</span>
          </button>
          <MobileNavLink to={profilePath} label="我的" active={location.pathname === profilePath}>
            <UserRound className="h-5 w-5" />
          </MobileNavLink>
        </div>
      </nav>
    </div>
  );
}

function MobileNavLink({
  to,
  label,
  active,
  children,
}: {
  to: string;
  label: string;
  active: boolean;
  children: ReactNode;
}) {
  return (
    <Link
      to={to}
      className={cn(
        'flex min-w-0 flex-col items-center gap-1 rounded-2xl px-2 py-1.5 text-xs font-medium',
        'text-muted-foreground transition-colors hover:bg-muted/70 hover:text-foreground',
        active && 'bg-muted text-foreground'
      )}
    >
      {children}
      <span className="mobile-bottom-label truncate">{label}</span>
    </Link>
  );
}
