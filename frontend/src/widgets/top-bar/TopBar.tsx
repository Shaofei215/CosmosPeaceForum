/**
 * 顶部栏组件
 * 包含搜索框与热门、最新、关注切换按钮
 * 跟随滚动 (sticky)
 */

import { useState } from 'react';
import { Search, Flame, Clock, Users } from 'lucide-react';
import { Input } from '@/shared/components/ui';

/**
 * 筛选类型
 */
type FilterType = 'hot' | 'latest' | 'following';

/**
 * 顶部栏组件
 */
export function TopBar() {
  const [activeFilter, setActiveFilter] = useState<FilterType>('hot');
  const [searchQuery, setSearchQuery] = useState('');

  const filters = [
    { id: 'hot' as FilterType, label: '热门', icon: Flame },
    { id: 'latest' as FilterType, label: '最新', icon: Clock },
    { id: 'following' as FilterType, label: '关注', icon: Users },
  ];

  return (
    <div className="sticky top-6 z-40 rounded-[2rem] bg-card/40 backdrop-blur-md supports-[backdrop-filter]:bg-card/30 p-4 mb-4">
      <div className="flex items-center gap-4">
        {/* 搜索框 */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="搜索内容..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 bg-muted/80 border-0 focus-visible:ring-1 rounded-[1.5rem]"
          />
        </div>

        {/* 切换按钮 */}
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
      </div>
    </div>
  );
}
