/**
 * 右侧边栏组件
 * 展示热榜、趋势话题与回到顶部按钮，固定在视口内
 */

import { TrendingUp, Flame } from 'lucide-react';
import { BackToTopButton } from '@/widgets/back-to-top-button';
import { CreatePostForm } from '@/widgets/create-post-form';
import { useAuthStore } from '@/features/auth';

/**
 * 右侧边栏组件
 */
export function RightSidebar() {
  const { isAuthenticated } = useAuthStore();

  return (
    <aside className="fixed top-[5.75rem] z-30 h-fit max-h-[calc(100vh-6.5rem)] w-64 space-y-3 overflow-y-auto pb-3">
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
          <div className="flex items-center gap-3 text-muted-foreground">
            <span className="flex h-5 w-5 items-center justify-center rounded bg-muted/60 text-xs font-medium">
              1
            </span>
            <span className="flex-1 truncate text-sm">敬请期待...</span>
          </div>
          <div className="flex items-center gap-3 text-muted-foreground">
            <span className="flex h-5 w-5 items-center justify-center rounded bg-muted/60 text-xs font-medium">
              2
            </span>
            <span className="flex-1 truncate text-sm">敬请期待...</span>
          </div>
          <div className="flex items-center gap-3 text-muted-foreground">
            <span className="flex h-5 w-5 items-center justify-center rounded bg-muted/60 text-xs font-medium">
              3
            </span>
            <span className="flex-1 truncate text-sm">敬请期待...</span>
          </div>
        </div>

        <div className="mt-3 text-center">
          <span className="text-xs text-muted-foreground">后端接口开发中...</span>
        </div>
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
