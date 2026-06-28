import { useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  FileText,
  Flame,
  Github,
  LayoutDashboard,
  LogOut,
  Menu,
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
  const activeNavIndex = visibleNavItems.findIndex(
    item => location.pathname === item.path || location.pathname.startsWith(`${item.path}/`)
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

        <nav className="relative flex flex-1 flex-col gap-1 px-2 py-2">
          {activeNavIndex >= 0 && (
            <span
              className="pointer-events-none absolute left-2 right-2 top-2 h-8 rounded-md bg-primary shadow-sm transition-transform duration-300 ease-out"
              style={{ transform: `translateY(${activeNavIndex * 2.25}rem)` }}
            />
          )}
          {visibleNavItems.map(item => {
            const active =
              location.pathname === item.path || location.pathname.startsWith(`${item.path}/`);
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`relative z-10 flex h-8 items-center gap-2 rounded-md px-2.5 text-sm leading-none transition-colors duration-200 ${
                  active
                    ? 'text-primary-foreground hover:text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                }`}
              >
                <item.icon size={18} className="shrink-0" />
                {sidebarOpen && <span className="truncate leading-none">{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        <div className="p-2">
          <a
            href="https://github.com/Shaofei215/CosmosPeaceForum"
            target="_blank"
            rel="noreferrer"
            className="flex h-10 w-full items-center justify-center gap-2 rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            title="查看 GitHub 仓库"
            aria-label="查看 CosmosPeaceForum GitHub 仓库"
          >
            <Github size={22} className="shrink-0" />
            {sidebarOpen && <span className="text-base">GitHub</span>}
          </a>
        </div>

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
