/**
 * 左侧边栏组件
 * 展示当前用户个人信息与消息按钮，跟随滚动
 * 带透明模糊效果
 */

import { Link } from 'react-router-dom';
import { MessageCircle, User } from 'lucide-react';
import { useAuthStore } from '@/features/auth';
import { Avatar, Button } from '@/shared/components/ui';

/**
 * 左侧边栏组件
 */
export function LeftSidebar() {
  const { user, isAuthenticated } = useAuthStore();

  return (
    <aside className="sticky top-28 h-fit w-64 space-y-4">
      {/* 用户信息卡片 - 透明模糊 */}
      <div className="rounded-xl bg-card/40 backdrop-blur-md supports-[backdrop-filter]:bg-card/30 p-4">
        {isAuthenticated && user ? (
          <div className="space-y-4">
            {/* 用户头像 - 独立一行居中 */}
            <Link
              to={`/user/${user.id}`}
              className="flex justify-center group"
            >
              <Avatar
                src={user.avatar_url}
                alt={user.username}
                size="xl"
                className="group-hover:ring-2 group-hover:ring-primary/20 transition-all"
              />
            </Link>

            {/* 用户名称 - 独立一行居中 */}
            <div className="block text-center">
              <p className="font-semibold text-foreground truncate">
                {user.username}
              </p>
              {user.bio && (
                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2 px-2">
                  {user.bio}
                </p>
              )}
            </div>

            {/* 用户统计 */}
            <div className="grid grid-cols-2 gap-2 pt-3 border-t border-border/50">
              <div className="text-center">
                <p className="text-lg font-semibold">0</p>
                <p className="text-xs text-muted-foreground">关注</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-semibold">0</p>
                <p className="text-xs text-muted-foreground">粉丝</p>
              </div>
            </div>

            {/* 消息按钮 */}
            <Button
              variant="default"
              className="w-full gap-2"
              size="sm"
            >
              <MessageCircle className="h-4 w-4" />
              消息
            </Button>
          </div>
        ) : (
          <div className="space-y-4 text-center">
            <div className="flex justify-center">
              <div className="h-16 w-16 rounded-full bg-muted/60 flex items-center justify-center">
                <User className="h-8 w-8 text-muted-foreground" />
              </div>
            </div>
            <div>
              <p className="text-sm text-muted-foreground mb-3">
                登录以查看个人信息
              </p>
              <Link to="/login">
                <Button size="sm" className="w-full">
                  登录
                </Button>
              </Link>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
