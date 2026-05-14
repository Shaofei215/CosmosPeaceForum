/**
 * 顶部栏组件
 * 根据当前页面显示不同内容：
 * - 信息流页面：显示搜索框 + 推荐/最新/关注切换按钮
 * - 其他页面：显示搜索框 + 返回按钮
 * 固定在视口顶部
 */

import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Search, Flame, Clock, Users, ArrowLeft } from 'lucide-react';
import { Input } from '@/shared/components/ui';
import { cn } from '@/shared/lib/utils';

/**
 * 筛选类型
 */
type FilterType = 'recommended' | 'latest' | 'following';

/**
 * 顶部栏组件
 */
export function TopBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [isScrolled, setIsScrolled] = useState(false);

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
  // 将 feed 类型放进 URL，保证刷新、返回和无限滚动缓存都能保持同一视图。
  const searchParams = new URLSearchParams(location.search);
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

  /**
   * 处理返回按钮点击
   */
  const handleBack = () => {
    navigate(-1);
  };

  return (
    <div
      className={cn(
        'mobile-top-bar rounded-[2rem] border border-transparent p-2 transition-all duration-200 sm:p-4',
        isScrolled
          ? 'border-white/40 bg-white/45 shadow-md backdrop-blur-xl supports-[backdrop-filter]:bg-white/35'
          : 'bg-white shadow-sm'
      )}
    >
      <div className="flex items-center gap-2 sm:gap-4">
        {/* 搜索框 */}
        <div className="relative min-w-0 flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="搜索内容..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="mobile-top-input h-9 rounded-[1.5rem] border-0 bg-muted/50 pl-10 shadow-none focus-visible:ring-1 sm:h-10"
          />
        </div>

        {/* 信息流页面显示筛选按钮，其他页面显示返回按钮 */}
        {isFeedPage ? (
          <div className="flex shrink-0 items-center gap-1 sm:gap-2">
            {filters.map((filter) => {
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
                  className={`mobile-top-action flex h-9 w-9 items-center justify-center rounded-[1.5rem] text-sm font-medium transition-colors sm:w-auto sm:gap-2 sm:px-3 sm:py-2 ${
                    activeFilter === filter.id
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted/80 text-muted-foreground hover:bg-muted/60 hover:text-foreground'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span className="hidden sm:inline">{filter.label}</span>
                </button>
              );
            })}
          </div>
        ) : (
          <button
            onClick={handleBack}
            aria-label="返回"
            className="mobile-top-action flex h-9 w-9 shrink-0 items-center justify-center rounded-[1.5rem] bg-muted/80 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground sm:w-auto sm:gap-2 sm:px-3 sm:py-2"
          >
            <ArrowLeft className="h-4 w-4" />
            <span className="hidden sm:inline">返回</span>
          </button>
        )}
      </div>
    </div>
  );
}
