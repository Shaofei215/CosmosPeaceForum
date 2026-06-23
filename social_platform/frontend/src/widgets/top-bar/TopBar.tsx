/**
 * 顶部栏组件
 * 根据当前页面显示不同内容：
 * - 左侧 Logo：点击回到主页并刷新
 * - 信息流页面：显示搜索框 + 推荐/最新/关注切换按钮
 * - 其他页面：显示搜索框 + 返回按钮
 * 固定在视口顶部
 */

import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Search, Flame, Clock, Users, ArrowLeft, FileText, User } from 'lucide-react';
import { Input } from '@/shared/components/ui';
import { PLATFORM_DISPLAY_NAME } from '@/shared/config/branding';
import { cn } from '@/shared/lib/utils';
import type { SearchType } from '@/features/search';
import { usePublicTheme } from '@/features/theme';

/**
 * 筛选类型
 */
type FilterType = 'recommended' | 'latest' | 'following';
type SearchFilterType = 'content' | 'user';

/**
 * 顶部栏组件
 */
export function TopBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [isScrolled, setIsScrolled] = useState(false);
  const { data: theme } = usePublicTheme();

  useEffect(() => {
    const updateScrolled = () => {
      setIsScrolled(window.scrollY > 4);
    };

    updateScrolled();
    window.addEventListener('scroll', updateScrolled, { passive: true });

    return () => window.removeEventListener('scroll', updateScrolled);
  }, []);

  // 判断当前是否在信息流页面
  const isFeedPage = location.pathname === '/feed' || location.pathname === '/';
  const isSearchPage = location.pathname === '/search';
  // 将 feed 类型放进 URL，保证刷新、返回和无限滚动缓存都能保持同一视图。
  const searchParams = new URLSearchParams(location.search);
  const currentSearchQuery = searchParams.get('q') || '';
  const urlSearchType: SearchType =
    searchParams.get('type') === 'user'
      ? 'user'
      : searchParams.get('type') === 'topic'
        ? 'topic'
        : 'content';
  const currentFeedType = searchParams.get('feed_type');
  const activeFilter: FilterType =
    currentFeedType === 'latest' || currentFeedType === 'following'
      ? currentFeedType
      : 'recommended';

  const filters = [
    { id: 'recommended' as FilterType, label: '推荐', icon: Flame },
    { id: 'latest' as FilterType, label: '最新', icon: Clock },
    { id: 'following' as FilterType, label: '关注', icon: Users },
  ];

  const searchFilters = [
    { id: 'content' as SearchFilterType, label: '帖子', icon: FileText },
    { id: 'user' as SearchFilterType, label: '用户', icon: User },
  ];

  useEffect(() => {
    if (isSearchPage) {
      setSearchQuery(currentSearchQuery);
    }
  }, [currentSearchQuery, isSearchPage]);

  /**
   * 处理返回按钮点击
   */
  const handleBack = () => {
    navigate(-1);
  };

  const handleLogoClick = () => {
    window.location.assign('/feed');
  };

  const navigateToSearch = (nextType: SearchType = urlSearchType) => {
    const query = searchQuery.trim();
    if (!query) return;

    const nextParams = new URLSearchParams();
    nextParams.set('type', nextType);
    nextParams.set('q', query);
    navigate({ pathname: '/search', search: `?${nextParams.toString()}` });
  };

  const setSearchType = (nextType: SearchType) => {
    if (isSearchPage && searchQuery.trim()) {
      navigateToSearch(nextType);
    }
  };

  return (
    <div
      className={cn(
        'mobile-top-bar relative isolate overflow-visible rounded-[2rem] border border-transparent p-2 transition-all duration-200 sm:p-4',
        isScrolled
          ? 'border-white/40 shadow-md backdrop-blur-xl supports-[backdrop-filter]:bg-white/35'
          : 'shadow-sm'
      )}
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-0 overflow-hidden rounded-[inherit]"
      >
        <div
          className="absolute inset-0"
          style={{
            background: isScrolled ? 'var(--theme-topbar-scrolled-bg)' : 'var(--theme-topbar-bg)',
          }}
        />
        <div
          className="absolute inset-0 bg-cover bg-center transition-opacity duration-200"
          style={{
            backgroundImage: 'var(--theme-topbar-bg-image)',
            opacity: isScrolled ? 0.62 : 0.82,
          }}
        />
      </div>
      <TopBarDecorations theme={theme} />
      <div className="relative z-10 flex items-center gap-2 sm:gap-4">
        <button
          type="button"
          onClick={handleLogoClick}
          aria-label="回到主页并刷新"
          className="flex h-9 min-w-9 max-w-36 shrink-0 items-center justify-start overflow-hidden rounded-[1.5rem] transition-opacity hover:opacity-85 sm:h-10 sm:max-w-48"
        >
          <img
            src="/logo.png"
            alt={PLATFORM_DISPLAY_NAME}
            className="h-full w-auto object-contain"
          />
        </button>

        {/* 搜索框 */}
        <form
          className="relative min-w-0 flex-1"
          onSubmit={event => {
            event.preventDefault();
            navigateToSearch();
          }}
        >
          <button
            type="submit"
            aria-label="搜索"
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
          >
            <Search className="h-4 w-4" />
          </button>
          <Input
            type="text"
            placeholder="搜索内容..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="mobile-top-input h-9 rounded-[1.5rem] border-0 bg-muted/50 pl-10 shadow-none focus-visible:ring-1 sm:h-10"
          />
        </form>

        {/* 信息流页面显示筛选按钮，搜索页面显示搜索类型和返回，其他页面显示返回按钮 */}
        {isFeedPage ? (
          <div className="flex shrink-0 items-center gap-1 sm:gap-2">
            {filters.map(filter => {
              const Icon = filter.icon;
              return (
                <button
                  key={filter.id}
                  onClick={() => {
                    const nextParams = new URLSearchParams(location.search);
                    if (filter.id === 'recommended') {
                      nextParams.delete('feed_type');
                    } else {
                      nextParams.set('feed_type', filter.id);
                    }
                    const search = nextParams.toString();
                    navigate({ pathname: '/feed', search: search ? `?${search}` : '' });
                  }}
                  aria-label={filter.label}
                  className={`mobile-top-action feed-filter-action flex h-9 min-w-12 items-center justify-center rounded-[1.5rem] text-sm font-medium transition-colors sm:min-w-16 sm:gap-2 sm:px-4 sm:py-2 ${
                    activeFilter === filter.id
                      ? 'bg-[var(--theme-topbar-action-active-bg)] text-[var(--theme-topbar-action-active-fg)]'
                      : 'bg-[var(--theme-topbar-action-inactive-bg)] text-[var(--theme-topbar-action-inactive-fg)] hover:opacity-85'
                  }`}
                >
                  <Icon className="h-4 w-4 sm:hidden" />
                  <span className="hidden sm:inline">{filter.label}</span>
                </button>
              );
            })}
          </div>
        ) : isSearchPage ? (
          <div className="flex shrink-0 items-center gap-1 sm:gap-2">
            {searchFilters.map(filter => {
              const Icon = filter.icon;
              return (
                <button
                  key={filter.id}
                  type="button"
                  onClick={() => setSearchType(filter.id)}
                  aria-label={filter.label}
                  className={`mobile-top-action feed-filter-action flex h-9 min-w-12 items-center justify-center rounded-[1.5rem] text-sm font-medium transition-colors sm:min-w-16 sm:gap-2 sm:px-4 sm:py-2 ${
                    urlSearchType === filter.id
                      ? 'bg-[var(--theme-topbar-action-active-bg)] text-[var(--theme-topbar-action-active-fg)]'
                      : 'bg-[var(--theme-topbar-action-inactive-bg)] text-[var(--theme-topbar-action-inactive-fg)] hover:opacity-85'
                  }`}
                >
                  <Icon className="h-4 w-4 sm:hidden" />
                  <span className="hidden sm:inline">{filter.label}</span>
                </button>
              );
            })}
            <button
              onClick={handleBack}
              aria-label="返回"
              className="mobile-top-action flex h-9 w-9 shrink-0 items-center justify-center rounded-[1.5rem] bg-[var(--theme-topbar-action-inactive-bg)] text-sm font-medium text-[var(--theme-topbar-action-inactive-fg)] transition-colors hover:opacity-85 sm:w-auto sm:gap-2 sm:px-3 sm:py-2"
            >
              <ArrowLeft className="h-4 w-4" />
              <span className="hidden sm:inline">返回</span>
            </button>
          </div>
        ) : (
          <button
            onClick={handleBack}
            aria-label="返回"
            className="mobile-top-action flex h-9 w-9 shrink-0 items-center justify-center rounded-[1.5rem] bg-[var(--theme-topbar-action-inactive-bg)] text-sm font-medium text-[var(--theme-topbar-action-inactive-fg)] transition-colors hover:opacity-85 sm:w-auto sm:gap-2 sm:px-3 sm:py-2"
          >
            <ArrowLeft className="h-4 w-4" />
            <span className="hidden sm:inline">返回</span>
          </button>
        )}
      </div>
    </div>
  );
}

function TopBarDecorations({ theme }: { theme: ReturnType<typeof usePublicTheme>['data'] }) {
  const decorations = [
    { src: theme?.topbar_decoration_top, className: 'inset-x-6 -top-5 mx-auto h-10 max-w-[72%]' },
    {
      src: theme?.topbar_decoration_bottom,
      className: 'inset-x-6 -bottom-5 mx-auto h-10 max-w-[72%]',
    },
    {
      src: theme?.topbar_decoration_left,
      className: '-left-6 top-1/2 h-[118%] max-w-16 -translate-y-1/2',
    },
    {
      src: theme?.topbar_decoration_right,
      className: '-right-6 top-1/2 h-[118%] max-w-16 -translate-y-1/2',
    },
  ];

  return (
    <>
      {decorations.map(({ src, className }, index) =>
        src ? (
          <img
            key={index}
            src={src}
            alt=""
            aria-hidden="true"
            className={cn('pointer-events-none absolute z-20 object-contain opacity-95', className)}
          />
        ) : null
      )}
    </>
  );
}
