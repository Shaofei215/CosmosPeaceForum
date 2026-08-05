/**
 * 左侧边栏组件
 * 展示当前用户个人信息与消息按钮，固定在视口内
 * 带透明模糊效果
 */

import { Link } from 'react-router-dom';
import { Coins, MessageCircle, User } from 'lucide-react';
import { useAuthStore } from '@/features/auth';
import { useUser } from '@/features/user';
import { useNotificationUnreadCount } from '@/features/notification';
import { Avatar, Button } from '@/shared/components/ui';
import { SidebarFooter } from './SidebarFooter';
import { copywriting } from '@/shared/config/copywriting';

/**
 * 左侧边栏组件
 */
export function LeftSidebar() {
  const { user, isAuthenticated } = useAuthStore();
  const { data: currentUserProfile } = useUser(user?.id ?? 0);
  const { data: unreadData } = useNotificationUnreadCount(isAuthenticated);
  const unreadCount = unreadData?.unread_count ?? 0;
  const displayedUser = currentUserProfile ?? user;

  return (
    <aside className="fixed top-24 z-30 h-fit max-h-[calc(100vh-6.75rem)] w-64 space-y-3 overflow-y-auto pb-3">
      {/* 用户信息卡片 - 白色+阴影 */}
      <div className="rounded-lg bg-card p-4 text-card-foreground shadow-sm">
        {isAuthenticated && user && displayedUser ? (
          <div className="space-y-4">
            {/* 用户头像 - 独立一行居中 */}
            <Link to={`/user/${user.id}`} className="flex justify-center group">
              <Avatar
                src={displayedUser.avatar_url}
                alt={displayedUser.username}
                size="xl"
                className="group-hover:ring-2 group-hover:ring-primary/20 transition-all"
              />
            </Link>

            {/* 用户名称 - 独立一行居中 */}
            <div className="block text-center">
              <p className="font-semibold text-foreground truncate">{displayedUser.username}</p>
              {displayedUser.bio && (
                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2 px-2">
                  {displayedUser.bio}
                </p>
              )}
            </div>

            {/* 用户统计 */}
            <div className="grid grid-cols-3 gap-2">
              <Link
                to={`/user/${user.id}/following`}
                className="text-center hover:bg-muted/30 rounded-lg p-1 transition-colors"
              >
                <p className="text-lg font-semibold">{displayedUser.following_count ?? 0}</p>
                <p className="text-xs text-muted-foreground">
                  {copywriting('common.follow', '关注')}
                </p>
              </Link>
              <Link
                to={`/user/${user.id}/followers`}
                className="text-center hover:bg-muted/30 rounded-lg p-1 transition-colors"
              >
                <p className="text-lg font-semibold">{displayedUser.followers_count ?? 0}</p>
                <p className="text-xs text-muted-foreground">
                  {copywriting('common.followers', '被关注')}
                </p>
              </Link>
              <div
                className="rounded-lg p-1 text-center"
                title={copywriting('profile.coin_balance_hint', '每日登录可领取硬币')}
              >
                <p className="flex items-center justify-center gap-1 text-lg font-semibold text-amber-500">
                  <Coins className="h-4 w-4" />
                  {user.coin_balance ?? 0}
                </p>
                <p className="text-xs text-muted-foreground">
                  {copywriting('common.coins', '硬币')}
                </p>
              </div>
            </div>

            {/* 消息按钮 */}
            <Button
              asChild
              variant="outline"
              className="w-full gap-2 rounded-md border-primary bg-card text-primary hover:bg-accent"
              size="sm"
            >
              <Link to="/notifications">
                <MessageCircle className="h-4 w-4" />
                {copywriting('common.messages', '消息')}
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
              <p className="text-sm text-muted-foreground mb-3">
                {copywriting('profile.login_to_view', '登录以查看个人信息')}
              </p>
              <Button
                asChild
                size="sm"
                className="w-full gap-2 rounded-md border-primary bg-primary text-primary-foreground hover:bg-primary/90 hover:text-primary-foreground"
              >
                <Link to="/login">{copywriting('common.login', '登录')}</Link>
              </Button>
            </div>
          </div>
        )}
      </div>
      <SidebarFooter />
    </aside>
  );
}
