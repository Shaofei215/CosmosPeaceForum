import { useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  FileText,
  Flame,
  LayoutDashboard,
  LogOut,
  Menu,
  Palette,
  Shield,
  UserCog,
  Users,
  X,
} from 'lucide-react';
import { useAdminAuthStore, useAdminLogout, type AdminPermission } from '@/features/admin';

const navItems = [
  {
    path: '/admin/dashboard',
    label: '仪表盘',
    icon: LayoutDashboard,
    permission: 'view_dashboard',
  },
  {
    path: '/admin/users',
    label: '用户管理',
    icon: Users,
    permission: 'manage_users',
  },
  {
    path: '/admin/content',
    label: '内容管理',
    icon: FileText,
    permission: 'manage_content',
  },
  {
    path: '/admin/hot-topics',
    label: '热点管理',
    icon: Flame,
    permission: 'manage_hot_topics',
  },
  {
    path: '/admin/theme',
    label: '主题管理',
    icon: Palette,
    permission: 'manage_theme',
  },
  {
    path: '/admin/admins',
    label: '管理员',
    icon: Shield,
    permission: 'manage_admins',
  },
  {
    path: '/admin/logs',
    label: '日志',
    icon: UserCog,
    permission: 'view_logs',
  },
];

export function AdminLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const location = useLocation();
  const navigate = useNavigate();
  const admin = useAdminAuthStore(state => state.admin);
  const logout = useAdminLogout();
  const visibleNavItems = navItems.filter(
    item => admin?.is_super_admin || admin?.permissions.includes(item.permission as AdminPermission)
  );

  const handleLogout = () => {
    logout();
    navigate('/admin/login', { replace: true });
  };

  return (
    <div className="management-compact flex h-screen bg-background">
      <aside
        className={`${
          sidebarOpen ? 'w-56' : 'w-14'
        } fixed z-10 flex h-full flex-col border-r border-border bg-card transition-all duration-300`}
      >
        <div className="flex h-12 items-center justify-between border-b border-border px-3">
          {sidebarOpen && (
            <img
              src="/biglogo.png"
              alt="平台管理后台"
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
            onClick={() => setSidebarOpen(value => !value)}
            className="rounded-md p-1 transition-colors hover:bg-muted"
            title={sidebarOpen ? '收起导航' : '展开导航'}
          >
            {sidebarOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>

        <nav className="flex-1 space-y-1 px-2 py-2">
          {visibleNavItems.map(item => {
            const active =
              location.pathname === item.path || location.pathname.startsWith(`${item.path}/`);
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm transition-colors ${
                  active
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
            onClick={handleLogout}
            className="flex w-full items-center justify-center gap-2 rounded-md px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-destructive"
            title="登出"
          >
            <LogOut size={16} />
            {sidebarOpen && <span>登出</span>}
          </button>
        </div>
      </aside>

      <main
        className={`flex-1 overflow-auto ${sidebarOpen ? 'ml-56' : 'ml-14'} transition-all duration-300`}
      >
        <div className="p-5">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
