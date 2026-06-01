/**
 * 右侧边栏组件
 * 展示热榜、趋势话题与回到顶部按钮，固定在视口内
 */

import { Link } from 'react-router-dom';
import { TrendingUp, Flame } from 'lucide-react';
import { BackToTopButton } from '@/widgets/back-to-top-button';
import { CreatePostForm } from '@/widgets/create-post-form';
import { useAuthStore } from '@/features/auth';
import { useHotTopics } from '@/features/hot-topic';

/**
 * 右侧边栏组件
 */
export function RightSidebar() {
  const { isAuthenticated } = useAuthStore();
  const { data: hotTopics = [], isLoading } = useHotTopics(10);

  return (
    <aside className="fixed top-24 z-30 h-fit w-64 space-y-3 pb-3">
      {isAuthenticated && (
        <div className="rounded-lg bg-white p-3 shadow-sm">
          <CreatePostForm />
        </div>
      )}

      <div className="rounded-lg bg-white p-3 shadow-sm">
        <div className="mb-3 flex items-center gap-2">
          <Flame className="h-5 w-5 text-orange-500" />
          <h3 className="font-semibold">热门榜单</h3>
        </div>

        <div className="space-y-3">
          {isLoading && <div className="py-2 text-sm text-muted-foreground">加载中...</div>}
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
            <div className="py-2 text-sm text-muted-foreground">暂无热门内容</div>
          )}
        </div>

        {!isLoading && (
          <div className="mt-3 text-center">
            <Link to="/hot" className="text-xs text-muted-foreground hover:text-primary">
              查看完整热榜
            </Link>
          </div>
        )}
      </div>

      <div className="rounded-lg bg-white p-3 shadow-sm">
        <div className="mb-3 flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-primary" />
          <h3 className="font-semibold">趋势话题</h3>
        </div>

        <div className="py-3 text-center text-sm text-muted-foreground">暂无热门话题</div>
      </div>

      <div className="flex">
        <BackToTopButton />
      </div>
    </aside>
  );
}
