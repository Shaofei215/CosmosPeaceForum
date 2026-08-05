/**
 * 右侧边栏组件
 * 展示热榜、话题与回到顶部按钮，固定在视口内
 */

import { Link } from 'react-router-dom';
import { useMemo } from 'react';
import { TrendingUp, Flame } from 'lucide-react';
import { BackToTopButton } from '@/widgets/back-to-top-button';
import { CreatePostForm } from '@/widgets/create-post-form';
import { useAuthStore } from '@/features/auth';
import { useHotTopics } from '@/features/hot-topic';
import { useTrendingTopics } from '@/features/topic';
import { copywriting } from '@/shared/config/copywriting';

/**
 * 右侧边栏组件
 */
export function RightSidebar() {
  const { isAuthenticated } = useAuthStore();
  const { data: hotTopics = [], isLoading } = useHotTopics(10);
  const { data: trendingTopics = [], isLoading: isTopicsLoading } = useTrendingTopics(12);
  const displayTopics = useMemo(() => {
    return [...trendingTopics].sort(() => Math.random() - 0.5).slice(0, 3);
  }, [trendingTopics]);

  return (
    <aside className="fixed top-24 z-30 h-fit w-64 space-y-3 pb-3">
      {isAuthenticated && (
        <div className="rounded-lg bg-card p-3 text-card-foreground shadow-sm">
          <CreatePostForm />
        </div>
      )}

      <div className="rounded-lg bg-card p-3 text-card-foreground shadow-sm">
        <div className="mb-3 flex items-center gap-2">
          <Flame className="h-5 w-5 text-orange-500" />
          <h3 className="font-semibold">{copywriting('hot_topics.title', '大家都在聊')}</h3>
        </div>

        <div className="space-y-3">
          {isLoading && (
            <div className="py-2 text-sm text-muted-foreground">
              {copywriting('common.loading', '加载中...')}
            </div>
          )}
          {!isLoading &&
            hotTopics.slice(0, 8).map((topic, index) => (
              <Link
                key={topic.id}
                to={`/search?type=content&q=${encodeURIComponent(topic.search_query)}`}
                className="flex items-center gap-3 text-muted-foreground hover:text-primary"
                title={topic.summary || topic.title}
              >
                <span className="flex h-5 w-5 items-center justify-center rounded bg-muted/60 text-xs font-medium">
                  {index + 1}
                </span>
                <span className="flex-1 truncate text-sm">{topic.title}</span>
              </Link>
            ))}
          {!isLoading && hotTopics.length === 0 && (
            <div className="py-2 text-sm text-muted-foreground">
              {copywriting('hot_topics.empty_hot', '暂无热门内容')}
            </div>
          )}
        </div>

        {!isLoading && (
          <div className="mt-3 text-center">
            <Link to="/hot" className="text-xs text-muted-foreground hover:text-primary">
              {copywriting('hot_topics.view_more', '查看更多')}
            </Link>
          </div>
        )}
      </div>

      <div className="rounded-lg bg-card p-3 text-card-foreground shadow-sm">
        <div className="mb-3 flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-primary" />
          <h3 className="font-semibold">{copywriting('hot_topics.topics_title', '话题')}</h3>
        </div>

        <div className="space-y-2">
          {isTopicsLoading && (
            <div className="py-2 text-sm text-muted-foreground">
              {copywriting('common.loading', '加载中...')}
            </div>
          )}
          {!isTopicsLoading &&
            displayTopics.map(topic => (
              <Link
                key={topic.id}
                to={`/search?type=topic&q=${encodeURIComponent(topic.name)}`}
                className="flex items-center justify-between gap-3 text-muted-foreground hover:text-primary"
              >
                <span className="min-w-0 truncate text-sm">#{topic.name}#</span>
              </Link>
            ))}
          {!isTopicsLoading && displayTopics.length === 0 && (
            <div className="py-3 text-center text-sm text-muted-foreground">
              {copywriting('hot_topics.empty_topics', '暂无话题')}
            </div>
          )}
        </div>
      </div>

      <div className="flex">
        <BackToTopButton />
      </div>
    </aside>
  );
}
