/**
 * 左侧边栏组件
 * 展示当前用户个人信息与消息按钮，固定在视口内
 * 带透明模糊效果
 */

import { Link } from 'react-router-dom';
import { MessageCircle, User } from 'lucide-react';
import { useAuthStore } from '@/features/auth';
import { useUser } from '@/features/user';
import { useNotificationUnreadCount } from '@/features/notification';
import { Avatar, Button } from '@/shared/components/ui';
import { SidebarFooter } from './SidebarFooter';

/**
 * 左侧边栏组件
 */
export function LeftSidebar() {
  const { user, isAuthenticated } = useAuthStore();
  const { data: currentUserProfile } = useUser(user?.id ?? 0);
  const { data: unreadData } = useNotificationUnreadCount(isAuthenticated);
  const unreadCount = unreadData?.unread_count ?? 0;

  return (
    <aside className="fixed top-24 z-30 h-fit max-h-[calc(100vh-6.75rem)] w-64 space-y-3 overflow-y-auto pb-3">
      {/* 用户信息卡片 - 白色+阴影 */}
      <div className="rounded-lg bg-white shadow-sm p-4">
        {isAuthenticated && user ? (
          <div className="space-y-4">
            {/* 用户头像 - 独立一行居中 */}
            <Link to={`/user/${user.id}`} className="flex justify-center group">
              <Avatar
                src={user.avatar_url}
                alt={user.username}
                size="xl"
                className="group-hover:ring-2 group-hover:ring-primary/20 transition-all"
              />
            </Link>

            {/* 用户名称 - 独立一行居中 */}
            <div className="block text-center">
              <p className="font-semibold text-foreground truncate">{user.username}</p>
              {user.bio && (
                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2 px-2">{user.bio}</p>
              )}
            </div>

            {/* 用户统计 */}
            <div className="grid grid-cols-2 gap-2">
              <Link
                to={`/user/${user.id}/following`}
                className="text-center hover:bg-muted/30 rounded-lg p-1 transition-colors"
              >
                <p className="text-lg font-semibold">
                  {currentUserProfile?.following_count ?? user.following_count ?? 0}
                </p>
                <p className="text-xs text-muted-foreground">关注</p>
              </Link>
              <Link
                to={`/user/${user.id}/followers`}
                className="text-center hover:bg-muted/30 rounded-lg p-1 transition-colors"
              >
                <p className="text-lg font-semibold">
                  {currentUserProfile?.followers_count ?? user.followers_count ?? 0}
                </p>
                <p className="text-xs text-muted-foreground">被关注</p>
              </Link>
            </div>

            {/* 消息按钮 */}
            <Button
              asChild
              variant="outline"
              className="w-full gap-2 rounded-md border-zinc-950 bg-white text-zinc-950 hover:bg-zinc-100"
              size="sm"
            >
              <Link to="/notifications">
                <MessageCircle className="h-4 w-4" />
                消息
                {unreadCount > 0 && (
                  <span className="text-xs font-semibold">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                )}
              </Link>
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
              <p className="text-sm text-muted-foreground mb-3">登录以查看个人信息</p>
              <Button
                asChild
                size="sm"
                className="w-full gap-2 rounded-md border-zinc-950 bg-zinc-950 text-white hover:bg-zinc-800 hover:text-white"
              >
                <Link to="/login">登录</Link>
              </Button>
            </div>
          </div>
        )}
      </div>
      <SidebarFooter />
    </aside>
  );
}
