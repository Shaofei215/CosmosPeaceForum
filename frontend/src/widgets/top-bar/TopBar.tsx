/**
 * 顶部栏组件
 * 根据当前页面显示不同内容：
 * - 信息流页面：显示搜索框 + 热门/最新/关注切换按钮
 * - 其他页面：显示搜索框 + 返回按钮
 * 跟随滚动 (sticky)
 */

import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Search, Flame, Clock, Users, ArrowLeft } from 'lucide-react';
import { Input } from '@/shared/components/ui';

/**
 * 筛选类型
 */
type FilterType = 'hot' | 'latest' | 'following';

/**
 * 顶部栏组件
 */
export function TopBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const [activeFilter, setActiveFilter] = useState<FilterType>('hot');
  const [searchQuery, setSearchQuery] = useState('');

  // 判断当前是否在信息流页面
  const isFeedPage = location.pathname === '/feed' || location.pathname === '/';

  const filters = [
    { id: 'hot' as FilterType, label: '热门', icon: Flame },
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
    <div className="sticky top-6 z-40 rounded-[2rem] bg-white shadow-sm p-4 mb-5">
      <div className="flex items-center gap-4">
        {/* 搜索框 */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="搜索内容..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 bg-muted/50 border-0 shadow-none rounded-[1.5rem] focus-visible:ring-1"
          />
        </div>

        {/* 信息流页面显示筛选按钮，其他页面显示返回按钮 */}
        {isFeedPage ? (
          <div className="flex items-center gap-2">
            {filters.map((filter) => {
              const Icon = filter.icon;
              return (
                <button
                  key={filter.id}
                  onClick={() => setActiveFilter(filter.id)}
                  className={`flex items-center gap-2 px-3 py-2 rounded-[1.5rem] text-sm font-medium transition-colors ${
                    activeFilter === filter.id
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted/80 text-muted-foreground hover:bg-muted/60 hover:text-foreground'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {filter.label}
                </button>
              );
            })}
          </div>
        ) : (
          <button
            onClick={handleBack}
            className="flex items-center gap-2 px-3 py-2 rounded-[1.5rem] text-sm font-medium transition-colors bg-muted/80 text-muted-foreground hover:bg-muted/60 hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            返回
          </button>
        )}
      </div>
    </div>
  );
}
