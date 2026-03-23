/**
 * 右侧边栏组件
 * 展示热榜（暂时留空）与发帖框，跟随滚动
 * 带透明模糊效果
 */

import { TrendingUp, Flame } from 'lucide-react';
import { CreatePostForm } from '@/widgets/create-post-form';
import { useAuthStore } from '@/features/auth';

/**
 * 右侧边栏组件
 */
export function RightSidebar() {
  const { isAuthenticated } = useAuthStore();

  return (
    <aside className="sticky top-28 h-fit w-64 space-y-4">
      {/* 发帖框 - 仅登录用户可见 - 透明模糊 */}
      {isAuthenticated && (
        <div className="rounded-xl bg-card/40 backdrop-blur-md supports-[backdrop-filter]:bg-card/30 p-4">
          <CreatePostForm />
        </div>
      )}

      {/* 热榜区域 - 透明模糊 */}
      <div className="rounded-xl bg-card/40 backdrop-blur-md supports-[backdrop-filter]:bg-card/30 p-4">
        <div className="flex items-center gap-2 mb-4">
          <Flame className="h-5 w-5 text-orange-500" />
          <h3 className="font-semibold">热门榜单</h3>
        </div>

        {/* 热榜内容 - 暂时留空 */}
        <div className="space-y-3">
          <div className="flex items-center gap-3 text-muted-foreground">
            <span className="flex items-center justify-center w-5 h-5 rounded bg-muted/60 text-xs font-medium">
              1
            </span>
            <span className="text-sm flex-1 truncate">敬请期待...</span>
          </div>
          <div className="flex items-center gap-3 text-muted-foreground">
            <span className="flex items-center justify-center w-5 h-5 rounded bg-muted/60 text-xs font-medium">
              2
            </span>
            <span className="text-sm flex-1 truncate">敬请期待...</span>
          </div>
          <div className="flex items-center gap-3 text-muted-foreground">
            <span className="flex items-center justify-center w-5 h-5 rounded bg-muted/60 text-xs font-medium">
              3
            </span>
            <span className="text-sm flex-1 truncate">敬请期待...</span>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t border-border/50 text-center">
          <span className="text-xs text-muted-foreground">
            后端接口开发中...
          </span>
        </div>
      </div>

      {/* 趋势话题 - 暂时留空 - 透明模糊 */}
      <div className="rounded-xl bg-card/40 backdrop-blur-md supports-[backdrop-filter]:bg-card/30 p-4">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="h-5 w-5 text-primary" />
          <h3 className="font-semibold">趋势话题</h3>
        </div>

        <div className="space-y-3">
          <div className="text-sm text-muted-foreground text-center py-4">
            暂无热门话题
          </div>
        </div>
      </div>
    </aside>
  );
}
