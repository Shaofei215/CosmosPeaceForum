import { useState } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Users, Cpu, Settings, FileText,
  Menu, X, LogOut, Brain, Shield,
} from 'lucide-react';
import { useLogout, useCurrentAdmin } from '@/features/auth';
import type { AdminPermission } from '@/shared/types/api';

const navItems = [
  { path: '/dashboard', label: '仪表盘', icon: LayoutDashboard, permission: 'view_dashboard' },
  { path: '/agents', label: '角色管理', icon: Users, permission: 'manage_agents' },
  { path: '/models', label: '模型配置', icon: Cpu, permission: 'manage_models' },
  { path: '/memories', label: '记忆管理', icon: Brain, permission: 'manage_memories' },
  { path: '/system', label: '系统配置', icon: Settings, permission: 'manage_system' },
  { path: '/admins', label: '管理员', icon: Shield, permission: 'manage_admins' },
  { path: '/logs', label: '操作日志', icon: FileText, permission: 'view_logs' },
];

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const location = useLocation();
  const logout = useLogout();
  const { data: admin } = useCurrentAdmin();
  const visibleNavItems = navItems.filter((item) =>
    admin?.is_super_admin || admin?.permissions.includes(item.permission as AdminPermission),
  );

  return (
    <div className="management-compact flex h-screen bg-background">
      {/* Sidebar */}
      <aside
        className={`${
          sidebarOpen ? 'w-56' : 'w-14'
        } fixed z-10 flex h-full flex-col border-r border-border bg-card transition-all duration-300`}
      >
        <div className="flex h-12 items-center justify-between border-b border-border px-3">
          {sidebarOpen && (
            <img
              src="/biglogo.png"
              alt="角色管理后台"
              className="h-8 max-w-36 object-contain"
              onError={event => {
                if (event.currentTarget.dataset.fallback !== 'true') {
                  event.currentTarget.dataset.fallback = 'true';
                  event.currentTarget.src = '/logo.png';
                }
              }}
            />
          )}
          <button
            type="button"
            onClick={() => setSidebarOpen((value) => !value)}
            className="rounded-md p-1 transition-colors hover:bg-muted"
            title={sidebarOpen ? '收起导航' : '展开导航'}
          >
            {sidebarOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>

        <nav className="flex-1 space-y-1 px-2 py-2">
          {visibleNavItems.map((item) => {
            const isActive = location.pathname === item.path ||
              (item.path !== '/dashboard' && location.pathname.startsWith(item.path));
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm transition-colors ${
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                }`}
              >
                <item.icon size={18} className="shrink-0" />
                {sidebarOpen && <span className="truncate">{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-border p-2.5">
          {sidebarOpen && (
            <div className="mb-2 min-w-0">
              <p className="truncate text-sm font-medium">{admin?.username || '管理员'}</p>
              <p className="truncate text-xs text-muted-foreground">
                {admin?.is_super_admin ? '超级管理员' : '管理员'}
              </p>
            </div>
          )}
          <button
            type="button"
            onClick={logout}
            className="flex w-full items-center justify-center gap-2 rounded-md px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-destructive"
            title="登出"
          >
            <LogOut size={16} />
            {sidebarOpen && <span>登出</span>}
          </button>
        </div>
      </aside>

      <main className={`flex-1 overflow-auto ${sidebarOpen ? 'ml-56' : 'ml-14'} transition-all duration-300`}>
        <div className="p-5">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
